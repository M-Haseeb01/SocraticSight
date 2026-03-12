"""
SocraticSight Avatar Overlay
A small always-on-top window that shows an animated robot avatar.
Includes TWO floating, draggable digital Whiteboards with 3D borders.
"""

import tkinter as tk
import threading
import time
import math
import os
import sys
from PIL import Image, ImageDraw, ImageTk


if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
# ───────────────────────────────────────────────────────────────────────────────

# ─── Avatar Window Config (Wider Base) ───
WINDOW_W    = 266  
WINDOW_H    = 265  
FPS         = 20
BG_COLOR    = "#0D1117"   

# Animation Durations (in frames)
BOOT_FRAMES = 25
SHUT_FRAMES = 25

def _make_avatar_frame(
    size: int = 200, mode: str = "idle", tick: int = 0, blink: bool = False, progress: float = 1.0
) -> Image.Image:
    """Draws the procedural futuristic robot face (Wider and Taller)."""
    img = Image.new("RGBA", (size, size), (13, 17, 23, 0))
    d   = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2 + 10

    # Colors & Glow
    chassis_color = (30, 41, 59)      
    screen_off, screen_on = (10, 15, 25), (15, 23, 42)      
    accent_color  = (56, 189, 248)    
    speaking = (mode == "speaking")
    
    if mode == "booting":
        glow_alpha = int(160 * progress)
    elif mode == "shutting_down":
        glow_alpha = int(160 * (1.0 - progress))
    else:
        glow_alpha = 160 if speaking else 60
        
    glow_color = (56, 189, 248, glow_alpha) if speaking else (74, 222, 128, glow_alpha)

    # 1. Antenna 
    d.line([cx, cy - 50, cx, cy - 85], fill=chassis_color, width=4)
    bulb_y, bulb_r = cy - 85, 4
    if speaking and tick % 6 < 3: bulb_r = 7
    if mode == "shutting_down": bulb_r = max(0, int(4 * (1 - progress)))
    if mode == "booting": bulb_r = max(0, int(4 * progress))
    if bulb_r > 0:
        d.ellipse([cx - bulb_r, bulb_y - bulb_r, cx + bulb_r, bulb_y + bulb_r], fill=glow_color)

    # 2. Head Chassis (Increased Width)
    head_w, head_h = 75, 56 
    glow_pad = 4 if speaking else 2
    d.rounded_rectangle([cx - head_w - glow_pad, cy - head_h - glow_pad, cx + head_w + glow_pad, cy + head_h + glow_pad], radius=18, fill=glow_color)
    d.rounded_rectangle([cx - head_w, cy - head_h, cx + head_w, cy + head_h], radius=15, fill=chassis_color, outline=(71, 85, 105), width=2)

    # 3. Screen Base & CRT Boot Logic (Increased Width)
    screen_w, screen_h = 60, 44 
    draw_face = False
    if mode == "booting":
        d.rounded_rectangle([cx - screen_w, cy - screen_h, cx + screen_w, cy + screen_h], radius=10, fill=screen_off)
        if progress < 0.3:
            aw, ah, crt_color = int(screen_w * (progress / 0.3)), 1, (255, 255, 255)
        elif progress < 0.7:
            aw, ah = screen_w, int(1 + (screen_h - 1) * ((progress - 0.3) / 0.4))
            crt_color = screen_on
        else:
            aw, ah, crt_color, draw_face = screen_w, screen_h, screen_on, True
        if aw > 0 and ah > 0:
            d.rectangle([cx - aw, cy - ah, cx + aw, cy + ah], fill=crt_color)
    else:
        d.rounded_rectangle([cx - screen_w, cy - screen_h, cx + screen_w, cy + screen_h], radius=10, fill=screen_on)
        draw_face = True

    # 4. Face Elements (Spread out to match new width)
    if draw_face:
        eye_y, eye_off, eye_h = cy - 14, 26, 10
        if mode == "shutting_down": eye_h = max(0, int(10 * (1.0 - progress)))
        elif blink: eye_h = 0
            
        for ex in [cx - eye_off, cx + eye_off]:
            if eye_h == 0:
                d.line([ex - 12, eye_y, ex + 12, eye_y], fill=accent_color, width=4)
            else:
                d.rounded_rectangle([ex - 8, eye_y - eye_h, ex + 8, eye_y + eye_h], radius=4, fill=accent_color)
                
        if not blink and not speaking:
            cheek_alpha = int(120 * (1.0 - progress)) if mode == "shutting_down" else 120
            if cheek_alpha > 0:
                c_color = (244, 114, 182, cheek_alpha)
                d.ellipse([cx - 52, cy - 2, cx - 38, cy + 4], fill=c_color)
                d.ellipse([cx + 38, cy - 2, cx + 52, cy + 4], fill=c_color)
                
        mouth_y = cy + 18
        if mode == "shutting_down":
            mw = max(2, int(10 * (1.0 - progress)))
            d.rounded_rectangle([cx - mw, mouth_y - 2, cx + mw, mouth_y + 2], radius=2, fill=accent_color)
        elif speaking:
            for i, dx in enumerate([-16, 0, 16]):
                h = abs(math.sin(tick * 0.4 + i)) * 12 + 3
                d.rounded_rectangle([cx + dx - 4, mouth_y - h, cx + dx + 4, mouth_y + h], radius=2, fill=accent_color)
        else:
            d.rounded_rectangle([cx - 12, mouth_y - 2, cx + 12, mouth_y + 2], radius=2, fill=accent_color)
            
    return img

class AvatarOverlay:
    def __init__(self):
        self._speaking, self._running, self._mode, self._mode_tick = False, False, "booting", 0
        self._root, self._label, self._status_lbl = None, None, None
        self._lock = threading.Lock()
        self._tick, self._blink_counter = 0, 0
        self._drag_x, self._drag_y = 0, 0
        
        # Dual Whiteboard components
        self._image_board = None
        self._text_board = None
        self._board_text_widget = None
        self._board_image_label = None
        self._current_board_image = None 

    def set_speaking(self, state: bool):
        with self._lock: self._speaking = state

    def stop(self):
        with self._lock:
            if self._mode != "shutting_down":
                self._mode, self._mode_tick = "shutting_down", 0
            self.hide_board()

    def _get_screen_dimensions(self):
        try:
            root = tk.Tk()
            w, h = root.winfo_screenwidth(), root.winfo_screenheight()
            root.destroy()
            return w, h
        except Exception:
            return 1920, 1080

    def run(self):
        self._running, self._root = True, tk.Tk()
        self._root.title("SocraticSight")
        sw, sh = self._get_screen_dimensions()
        
        # Lock avatar to bottom right safely
        self._root.geometry(f"{WINDOW_W}x{WINDOW_H}+{sw - WINDOW_W - 20}+{sh - WINDOW_H - 60}")
        self._root.wm_attributes("-topmost", True, "-alpha", 0.95)
        self._root.configure(bg=BG_COLOR)
        self._root.overrideredirect(True)
        self._root.bind("<ButtonPress-1>", self._drag_start)
        self._root.bind("<B1-Motion>", self._drag_motion)
        
        self._label = tk.Label(self._root, bg=BG_COLOR)
        self._label.pack(pady=(10, 2))
        
        tk.Label(self._root, text="✦ SocraticSight", fg="#63B3ED", bg=BG_COLOR, font=("Helvetica", 10, "bold")).pack()
        
        self._status_lbl = tk.Label(self._root, text="● Booting...", fg="#FBBF24", bg=BG_COLOR, font=("Helvetica", 8))
        self._status_lbl.pack()
        
        self._setup_boards(sw, sh)
        self._animate()
        self._root.mainloop()

    # ── Two Separate Windows Logic with 3D Borders ────────────────────────────
    def _setup_boards(self, sw, sh):
        # --- 1. IMAGE BOARD ---
        self._image_board = tk.Toplevel(self._root)
        iw, ih = 550, 500  
        pos_x_img = (sw // 2) - iw - 20
        pos_y_img = (sh - ih) // 2
        
        self._image_board.geometry(f"{iw}x{ih}+{pos_x_img}+{pos_y_img}")
        self._image_board.wm_attributes("-topmost", True, "-alpha", 0.98)
        self._image_board.overrideredirect(True) 
        
        # 3D Outer Border Framework
        img_outer = tk.Frame(self._image_board, bg="#0284C7", bd=4, relief="ridge")
        img_outer.pack(fill=tk.BOTH, expand=True)
        
        img_hdr = tk.Frame(img_outer, bg="#1E293B", height=38)
        img_hdr.pack(fill=tk.X)
        img_hdr.pack_propagate(False)
        
        lbl_img = tk.Label(img_hdr, text=" 🖼️ AI Diagrams", bg="#1E293B", fg="#38BDF8", font=("Helvetica", 11, "bold"))
        lbl_img.pack(side=tk.LEFT, padx=10)
        btn_img = tk.Button(img_hdr, text="✕", bg="#1E293B", fg="#F87171", bd=0, font=("Helvetica", 12, "bold"), command=self._hide_image_board, cursor="hand2")
        btn_img.pack(side=tk.RIGHT, padx=10)
        
        img_hdr.bind("<ButtonPress-1>", self._img_drag_start)
        img_hdr.bind("<B1-Motion>", self._img_drag_motion)
        lbl_img.bind("<ButtonPress-1>", self._img_drag_start)
        lbl_img.bind("<B1-Motion>", self._img_drag_motion)

        img_main = tk.Frame(img_outer, bg="#0F172A")
        img_main.pack(fill=tk.BOTH, expand=True)

        self._board_image_label = tk.Label(img_main, bg="#0F172A", text="[ Diagram Generated Here ]", fg="#475569", font=("Helvetica", 10))
        self._board_image_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._image_board.withdraw()

        # --- 2. TEXT/MATH BOARD ---
        self._text_board = tk.Toplevel(self._root)
        tw, th = 600, 500  
        pos_x_txt = (sw // 2) + 20
        pos_y_txt = (sh - th) // 2
        
        self._text_board.geometry(f"{tw}x{th}+{pos_x_txt}+{pos_y_txt}")
        self._text_board.wm_attributes("-topmost", True, "-alpha", 0.98)
        self._text_board.overrideredirect(True) 
        
        # 3D Outer Border Framework
        txt_outer = tk.Frame(self._text_board, bg="#0284C7", bd=4, relief="ridge")
        txt_outer.pack(fill=tk.BOTH, expand=True)
        
        txt_hdr = tk.Frame(txt_outer, bg="#1E293B", height=38)
        txt_hdr.pack(fill=tk.X)
        txt_hdr.pack_propagate(False)
        
        lbl_txt = tk.Label(txt_hdr, text=" 📝 AI Notes & Math", bg="#1E293B", fg="#38BDF8", font=("Helvetica", 11, "bold"))
        lbl_txt.pack(side=tk.LEFT, padx=10)
        btn_txt = tk.Button(txt_hdr, text="✕", bg="#1E293B", fg="#F87171", bd=0, font=("Helvetica", 12, "bold"), command=self._hide_text_board, cursor="hand2")
        btn_txt.pack(side=tk.RIGHT, padx=10)
        
        txt_hdr.bind("<ButtonPress-1>", self._txt_drag_start)
        txt_hdr.bind("<B1-Motion>", self._txt_drag_motion)
        lbl_txt.bind("<ButtonPress-1>", self._txt_drag_start)
        lbl_txt.bind("<B1-Motion>", self._txt_drag_motion)

        txt_main = tk.Frame(txt_outer, bg="#0F172A")
        txt_main.pack(fill=tk.BOTH, expand=True)

        self._board_text_widget = tk.Text(txt_main, bg="#0F172A", fg="#F8FAFC", font=("Consolas", 13), wrap=tk.WORD, bd=0, padx=20, pady=20, state=tk.DISABLED)
        self._board_text_widget.pack(fill=tk.BOTH, expand=True)
        
        self._text_board.withdraw()

    # --- Drag Logic for Image Board ---
    def _img_drag_start(self, event): self._img_x, self._img_y = event.x, event.y
    def _img_drag_motion(self, event):
        x = self._image_board.winfo_x() + event.x - self._img_x
        y = self._image_board.winfo_y() + event.y - self._img_y
        self._image_board.geometry(f"+{x}+{y}")

    # --- Drag Logic for Text Board ---
    def _txt_drag_start(self, event): self._txt_x, self._txt_y = event.x, event.y
    def _txt_drag_motion(self, event):
        x = self._text_board.winfo_x() + event.x - self._txt_x
        y = self._text_board.winfo_y() + event.y - self._txt_y
        self._text_board.geometry(f"+{x}+{y}")

    # --- Visibility Controls ---
    def show_board(self): 
        pass 
        
    def hide_board(self): 
        self._hide_image_board()
        self._hide_text_board()

    def _hide_image_board(self):
        if self._root: self._root.after(0, self._image_board.withdraw)

    def _hide_text_board(self):
        if self._root: self._root.after(0, self._text_board.withdraw)

    def update_board_text(self, text: str):
        if not self._root: return
        def _update():
            self._board_text_widget.config(state=tk.NORMAL)
            self._board_text_widget.delete(1.0, tk.END)
            self._board_text_widget.insert(tk.END, text)
            self._board_text_widget.see(tk.END)
            self._board_text_widget.config(state=tk.DISABLED)
            self._text_board.deiconify()
            self._text_board.lift()
        self._root.after(0, _update)

    def update_board_image(self, image_path: str):
        if not self._root or not os.path.exists(image_path): return
        def _update():
            try:
                img = Image.open(image_path)
                # Max image size scaled up to match new window width
                img.thumbnail((530, 450), Image.Resampling.LANCZOS)
                self._current_board_image = ImageTk.PhotoImage(img)
                self._board_image_label.configure(image=self._current_board_image, text="")
                self._image_board.deiconify()
                self._image_board.lift()
            except Exception as e:
                print(f"Error displaying image: {e}")
        self._root.after(0, _update)

    # ── Core Animation Logic ────────────────────────────────────────────────────
    def _animate(self):
        if not self._running:
            return
            
        self._tick += 1
        self._blink_counter += 1
        
        with self._lock:
            mode = self._mode
            speaking = self._speaking
            
        progress = 1.0
        
        if mode == "booting":
            self._mode_tick += 1
            progress = min(1.0, self._mode_tick / BOOT_FRAMES)
            if progress >= 1.0:
                with self._lock:
                    self._mode = "speaking" if speaking else "idle"
                    mode = self._mode
        elif mode == "shutting_down":
            self._mode_tick += 1
            progress = min(1.0, self._mode_tick / SHUT_FRAMES)
            if progress >= 1.0:
                self._running = False
                self._root.quit()
                return
        else:
            with self._lock:
                self._mode = "speaking" if speaking else "idle"
                mode = self._mode

        txt, clr = "● Listening...", "#4ADE80"
        if mode == "booting": txt, clr = "● Booting...", "#FBBF24"
        elif mode == "shutting_down": txt, clr = "● Sleeping... Bye!", "#F87171"
        elif mode == "speaking": txt, clr = "● Speaking...", "#63B3ED"
            
        self._status_lbl.configure(text=txt, fg=clr)

        blink = ((self._blink_counter % 80) in range(2, 5))
        
        frame = _make_avatar_frame(size=190, mode=mode, tick=self._tick, blink=blink, progress=progress)
        photo = ImageTk.PhotoImage(frame)
        self._label.configure(image=photo)
        self._label.image = photo
        
        self._root.after(int(1000 / FPS), self._animate)

    def _drag_start(self, event):
        self._drag_x, self._drag_y = event.x, event.y
        
    def _drag_motion(self, event):
        x = self._root.winfo_x() + event.x - self._drag_x
        y = self._root.winfo_y() + event.y - self._drag_y
        self._root.geometry(f"+{x}+{y}")