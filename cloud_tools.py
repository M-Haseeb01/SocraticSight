"""
cloud_tools.py
Handles Vertex AI Image Generation and Cloud Storage uploads.
"""

import asyncio
import os
from google import genai
from google.genai import types
from google.cloud import storage

# ─── CONFIGURATION (FILL THESE IN!) ────────────────────────────────────────────
GCP_PROJECT_ID = "YOUR-PROJECT-ID"        
GCS_BUCKET_NAME = "YOUR-BUCKET-NAME"      
LOCATION = "us-central1"
# ───────────────────────────────────────────────────────────────────────────────

async def generate_diagram_on_cloud(prompt: str, save_path: str = "diagram.png") -> str:
    """
    Calls Google Cloud Vertex AI (Imagen) to generate a diagram.
    """
    print("  [CLOUD MODULE TRIGGERED: VERTEX AI IMAGEN]")
    print(f"  ➜ Routing prompt to Google Cloud: '{prompt}'")
    
    try:
        # Create a dedicated client that routes strictly to Google Cloud Vertex AI
        vertex_client = genai.Client(
            vertexai=True, 
            project=GCP_PROJECT_ID,
            location=LOCATION
        )

        enhanced_prompt = f"A clear, simple, educational diagram of {prompt}. White background, clean lines, professional textbook style."
        loop = asyncio.get_event_loop()
        
        print("  ➜ Generating image on Vertex AI...")
        response = await loop.run_in_executor(None, lambda: vertex_client.models.generate_images(
            model="imagen-3.0-generate-001",
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="4:3"
            )
        ))

        if response.generated_images:
            img_blob = response.generated_images[0].image
            with open(save_path, "wb") as f:
                f.write(img_blob.image_bytes)
            print(f"  [SUCCESS] Diagram securely generated via Google Cloud!")
        else:
            print("  [ERROR] Image generation failed (No images returned).")
            
    except Exception as e:
        print(f"  [ERROR] Vertex AI error: {e}")

    print("☁️ " * 20 + "\n")
    return save_path


async def save_session_to_cloud(transcript: str, image_path: str = "diagram.png"):
    """
    Summarizes the session using Vertex AI and uploads the summary and diagram to Cloud Storage.
    """
   
    print("  [CLOUD MODULE TRIGGERED: CLOUD STORAGE]")
    print("  Summarizing session transcript...")
    
    try:
        # 1. Summarize the long transcript using Vertex AI Gemini
        vertex_client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=LOCATION)
        summary_prompt = f"Please provide a short, concise, bullet-point summary of the following tutoring session:\n\n{transcript}"
        
        loop = asyncio.get_event_loop()
        summary_response = await loop.run_in_executor(
            None, 
            lambda: vertex_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=summary_prompt
            )
        )
        
        summary_text = summary_response.text
        summary_file = "session_summary.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary_text)
        
        print("   Uploading files to Google Cloud Storage...")
        
        # 2. Upload to Google Cloud Storage Bucket
        storage_client = storage.Client(project=GCP_PROJECT_ID)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        
        # Upload the text summary
        blob_summary = bucket.blob("study_notes/session_summary.txt")
        blob_summary.upload_from_filename(summary_file)
        print(f"   Uploaded {summary_file} to GCS bucket: {GCS_BUCKET_NAME}")
        
        # Upload the diagram (if one was generated during the session)
        if os.path.exists(image_path):
            blob_image = bucket.blob(f"study_notes/{image_path}")
            blob_image.upload_from_filename(image_path)
            print(f"   Uploaded {image_path} to GCS bucket: {GCS_BUCKET_NAME}")
        
    except Exception as e:
        print(f"   [ERROR] Cloud Storage error: {e}")
        
    print("☁️ " * 20 + "\n")