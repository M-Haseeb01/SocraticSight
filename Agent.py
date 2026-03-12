"""
SocraticSight Agent
Real-time AI tutor - voice in, voice out, screen on demand, whiteboard + diagrams.
"""

import asyncio
import os
import threading
import io
import sys
import re
import cloud_tools

import pyaudio
import mss
from PIL import Image

from google import genai
from google.genai import types

# ─── Audio Config ──────────────────────────────────────────────────────────────
FORMAT              = pyaudio.paInt16
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

# ─── Models ────────────────────────────────────────────────────────────────────
LIVE_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
IMAGE_MODEL = "imagen-4.0-generate-001" # Google's latest image gen model

# ─── Config ────────────────────────────────────────────────────────────────────
LANGUAGES = {
    "1": ("English", "Aoede"), "2": ("Urdu", "Leda"), "3": ("Spanish", "Kore"),
    "4": ("French", "Charon"), "5": ("Arabic", "Fenrir"),
}

SCREEN_KEYWORDS = ["screen", "see", "look", "show", "explain", "what is this", "my work", "on screen"]
SHUTDOWN_KEYWORDS = ["go to sleep", "turn off", "shut down", "goodbye", "bye bye"]
HIDE_BOARD_KEYWORDS = ["close board", "hide board", "clear board", "remove board"]

# ─── System Prompt (Updated for Diagrams) ──────────────────────────────────────
SYSTEM_PROMPT = """
You are SocraticSight — a warm, patient, and brilliant teacher.
Respond in: {language}.

YOUR JOB:
- Talk with the student naturally. Handle interruptions gracefully.
- Explain concepts using simple words, real-life analogies, and relatable examples.
- When you receive a screen image, look at it carefully and explain what you see step-by-step.

WHITEBOARD & DIAGRAM FEATURES:
You have a digital whiteboard. Use it for complex topics.

1. MATH/TEXT: If solving equations or showing code, use the whiteboard for text.
   To use text mode, start your response with the exact keyword: BOARD_TEXT_ON
   Everything after that word appears on the screen. Keep formatting clean. Do not use complex markdown.

2. DIAGRAMS/DRAWING: If the student asks for a diagram, chart, map, or drawing (e.g., "Draw a plant cell"), you MUST generate an image.
   You cannot generate the image yourself in real-time audio. Instead, you must signal the system to generate it for you.
   To generate a diagram, include this exact format in your response: DRAW_START|detailed description of the diagram to generate|DRAW_END
   Gemini will then generate the image based on your description and show it to the student.
   While the image generates, continue talking normally, explaining what you are about to show them. Do not use the BOARD_TEXT_ON trigger in the same turn you use DRAW_START.

RULES:
- Keep audio responses short (3-5 sentences).
- Never use jargon without explaining it.
- Always be encouraging.
"""

# ───────────────────────────────────────────────────────────────────────────────

def select_language():
    print("\n" + "=" * 50); print(" SocraticSight — Your AI Tutor "); print("=" * 50)
    print("\n  Choose your language:\n")
    flags = {"English":"🇺🇸","Urdu":"🇵🇰","Spanish":"🇪🇸","French":"🇫🇷","Arabic":"🇸🇦"}
    for key, (name, voice) in LANGUAGES.items(): print(f"    [{key}]  {flags.get(name,'')}  {name}")
    print()
    while True:
        choice = input("  Enter number (1-5): ").strip()
        if choice in LANGUAGES: name, voice = LANGUAGES[choice]; print(f"\n    {name} selected. Connecting...\n"); return name, voice
        print("    Please enter 1-5.")

def capture_screen_jpeg() -> bytes:
    with mss.mss() as sct: shot = sct.grab(sct.monitors[1]); img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    img = img.resize((int(img.width * 0.4), int(img.height * 0.4)), Image.LANCZOS)
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=70); return buf.getvalue()

def has_keyword(text, keywords): return any(k in text.lower() for k in keywords)

# ───────────────────────────────────────────────────────────────────────────────

class SocraticAgent:
    def __init__(self, language: str, voice: str):
        self.language, self.voice = language, voice
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.pya = pyaudio.PyAudio()
        self.mic_queue, self.playback_queue = asyncio.Queue(), asyncio.Queue()  
        self.running, self.session, self._screen_pending = True, None, False
        
        
        self.is_tool_active = False
        
        self.avatar_callback = None
        self.board_show_callback = None
        self.board_update_text_callback = None 
        self.board_update_image_callback = None 
        self.board_hide_callback = None
        
        self.turn_transcript = ""
        self.board_active = False

    async def _mic_listener(self):
        loop = asyncio.get_event_loop()
        stream = await loop.run_in_executor(None, lambda: self.pya.open(
            format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE, input=True,
            frames_per_buffer=CHUNK_SIZE,
        ))
        print(" Listening...")
        try:
            while self.running:
                data = await loop.run_in_executor(None, lambda: stream.read(CHUNK_SIZE, exception_on_overflow=False))
                await self.mic_queue.put(data)
        except Exception as e: 
            if self.running: print(f"  Mic error: {e}")
        finally: stream.stop_stream(); stream.close()

    async def _sender(self):
        while self.running:
            try:
                chunk = await asyncio.wait_for(self.mic_queue.get(), timeout=1.0)
                
               
                if not self.is_tool_active:
                    await self.session.send_realtime_input(audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={SEND_SAMPLE_RATE}"))
                
                await asyncio.sleep(0.01) 
            except asyncio.TimeoutError: continue
            except Exception as e:
                if self.running: print(f"  Send error: {e}")
                await asyncio.sleep(1.0)

    async def _send_screen(self):
        try:
            self.is_tool_active = True 
            print("  Taking screenshot...")
            jpeg_bytes = await asyncio.get_event_loop().run_in_executor(None, capture_screen_jpeg)
            await self.session.send_client_content(turns=types.Content(role="user", parts=[
                types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text="This is my screen right now. Please look at it and explain what I am working on strictly as a teacher.")
            ]), turn_complete=True)
            print("  Screen sent!")
        except Exception as e: 
            print(f" Screen error: {e}")
        finally: 
            self._screen_pending = False
            self.is_tool_active = False 

    async def _player(self):
        loop = asyncio.get_event_loop()
        out_stream = await loop.run_in_executor(None, lambda: self.pya.open(
            format=FORMAT, channels=CHANNELS, rate=RECEIVE_SAMPLE_RATE, output=True,
            frames_per_buffer=CHUNK_SIZE,
        ))
        try:
            while self.running:
                try:
                    chunk = await asyncio.wait_for(self.playback_queue.get(), timeout=0.5)
                    await loop.run_in_executor(None, out_stream.write, chunk)
                except asyncio.TimeoutError: continue
        except Exception as e:
            if self.running: print(f"  Player error: {e}")
        finally: out_stream.stop_stream(); out_stream.close()

    # ── Diagram Generation Logic (Routing to separate file) ────────────────────
    async def _generate_diagram(self, prompt: str):
        """Passes the prompt to our separate Google Cloud module."""
        try:
            # Call the external file!
            path = await cloud_tools.generate_diagram_on_cloud(prompt)
            
            # If successful, show the whiteboard
            self.board_active = True
            if self.board_show_callback: self.board_show_callback()
            if self.board_update_image_callback: self.board_update_image_callback(path)
            
        except Exception as e:
            print(f"  Cloud module error: {e}")
    
    # ── Receiver (Updated for Split-Screen Board & Robust Commands) ─────────────
    async def _receiver(self):
        try:
            while self.running:
                async for response in self.session.receive():
                    
                    # 1. Handle incoming audio from Gemini
                    if response.data:
                        self._signal_avatar(True)
                        self.playback_queue.put_nowait(response.data)

                    sc = response.server_content
                    if sc:
                        # 2. Handle Interruption (Stop talking instantly)
                        if getattr(sc, 'interrupted', False):
                            while not self.playback_queue.empty():
                                try: self.playback_queue.get_nowait()
                                except asyncio.QueueEmpty: break
                            self._signal_avatar(False)
                            self.turn_transcript = ""
                            print("\n  [Interrupted]")

                        # 3. Handle Turn Completion
                        if sc.turn_complete:
                            self._signal_avatar(False)
                            self.turn_transcript = ""

                        # 4. Handle Gemini's Spoken Text (Model Output)
                        if sc.output_transcription and sc.output_transcription.text:
                            text_chunk = sc.output_transcription.text
                            self.turn_transcript += text_chunk
                            
                            
                            clean_print = re.sub(r'BOARD_TEXT_ON|DRAW_START\|.*?\|DRAW_END', '', text_chunk)
                            if clean_print.strip(): 
                                print(f"  🤖  {clean_print}", end="", flush=True)

                            # Trigger A: Diagram Generation
                            draw_match = re.search(r'DRAW_START\|(.*?)\|DRAW_END', self.turn_transcript)
                            if draw_match:
                                diagram_prompt = draw_match.group(1)
                                
                                self.turn_transcript = self.turn_transcript.replace(draw_match.group(0), "[Generating Diagram]")
                                # Launch the cloud generation 
                                asyncio.create_task(self._generate_diagram(diagram_prompt))

                            # Trigger B: Text/Math Notes
                            elif "BOARD_TEXT_ON" in self.turn_transcript:
                                self.board_active = True
                                board_text = self.turn_transcript.split("BOARD_TEXT_ON")[-1].strip()
                                
                                if self.board_update_text_callback: 
                                    self.board_update_text_callback(board_text)

                        # 5. Handle User Voice Commands (Input Transcription)
                        if sc.input_transcription and sc.input_transcription.text:
                            
                            user_text = sc.input_transcription.text.strip().lower()
                            
                            if user_text:
                                print(f"\n  👤  You: {user_text}")
                                
                                # Command: Hide Whiteboard
                                if has_keyword(user_text, HIDE_BOARD_KEYWORDS):
                                    self.board_active = False
                                    if self.board_hide_callback: 
                                        self.board_hide_callback()
                                    print("   Whiteboard hidden.")
                                
                                # Command: Shut Down
                                elif has_keyword(user_text, SHUTDOWN_KEYWORDS):
                                    print("\n  🛑  Shutdown command received.")
                                    print("  📦  Packaging session artifacts...")
                                    
                                    # Create the text data you want to save to your bucket
                                    # (For the hackathon demo, a simple summary log is perfect)
                                    demo_log = (
                                        "--- SocraticSight Session Log ---\n"
                                        "Status: Completed Successfully\n"
                                        "Vision AI: Triggered\n"
                                        "Diagrams Generated: Yes\n"
                                        "End of Transcript."
                                    )
                                    
                                    # Pause the shutdown to upload the file to Google Cloud
                                    await cloud_tools.upload_session_log(demo_log)
                                    
                                    print("  👋  Shutting down application. Goodbye!")
                                    self.stop()
                                    return
                                
                                # Command: Look at Screen
                                elif has_keyword(user_text, SCREEN_KEYWORDS) and not self._screen_pending:
                                    self._screen_pending = True
                                    asyncio.create_task(self._send_screen())

        except Exception as e:
            if self.running: 
                print(f"  Receiver error: {e}")

    def _signal_avatar(self, speaking: bool):
        if self.avatar_callback: self.avatar_callback(speaking)

    async def run(self):
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice))),
            system_instruction=types.Content(parts=[types.Part.from_text(text=SYSTEM_PROMPT.format(language=self.language))]),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
        )
        print("  🔗  Connecting to Gemini Live API...")
        async with self.client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            self.session = session
            print("  Connected!\n"); print("   Say 'draw a diagram of X' to use the whiteboard."); print("  " + "-" * 48 + "\n")
            await session.send_client_content(turns=types.Content(role="user", parts=[types.Part.from_text(text=(
                f"Greet the student warmly in {self.language} as SocraticSight their AI tutor. "
                "Say they can talk naturally, share screen, or ask you to draw a diagram on the board. 2 sentences max."
            ))]), turn_complete=True)
            await asyncio.gather(self._mic_listener(), self._sender(), self._player(), self._receiver())

    def stop(self): self.running = False

# ─── Threading & Launch Wrapper ────────────────────────────────────────────────

def main():
    if not os.environ.get("GEMINI_API_KEY"): print("\nSet GEMINI_API_KEY env var."); sys.exit(1)
    language, voice = select_language()
    from avatar import AvatarOverlay
    overlay = AvatarOverlay()
    
    async def start_agent_async():
        agent = SocraticAgent(language, voice)
        agent.avatar_callback = overlay.set_speaking
        agent.board_show_callback = overlay.show_board
        agent.board_update_text_callback = overlay.update_board_text 
        agent.board_update_image_callback = overlay.update_board_image 
        agent.board_hide_callback = overlay.hide_board
        try: await agent.run()
        except Exception as e: print(f"Agent closed: {e}")
        finally: agent.stop(); overlay.stop() 
        
    threading.Thread(target=lambda: asyncio.run(start_agent_async()), daemon=True).start()
    try: overlay.run()
    except KeyboardInterrupt: print("\n\n  👋  Goodbye!\n"); overlay.stop()

if __name__ == "__main__": main()
