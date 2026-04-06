"""
Vision Language Model (VLM) Module

Uses Groq's Llama 4 Scout (meta-llama/llama-4-scout-17b-16e-instruct) to
analyze drone surveillance images. The VLM receives a frame image and generates
a detailed text description of what it sees — people, vehicles, activities,
and potential security concerns.

This is the "eyes" of the system — it converts visual data into text that
the security analysis agent can reason about.
"""

import os
import base64
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
VLM_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Security-focused VLM prompt
VLM_SYSTEM_PROMPT = """You are a drone surveillance camera AI analyzing aerial footage 
of a property. Describe what you see in this drone camera frame in detail.

Focus on:
- People: count, clothing, behavior (walking, standing, running, loitering, climbing)
- Vehicles: type, color, make if identifiable, parked or moving
- Activities: any suspicious behavior, unauthorized access attempts, deliveries
- Environment: time of day (light/dark), weather conditions
- Security concerns: anyone near fences, gates, doors; unattended objects

Be specific and factual. Describe positions relative to structures (gate, fence, 
parking lot, building). Mention if anyone appears to have or lack identification/badges.

Respond with a concise 2-3 sentence description."""


def analyze_image(image_path: str, telemetry: dict = None) -> str:
    """
    Analyze a drone surveillance frame using the VLM.
    
    Args:
        image_path: Path to the JPEG frame image.
        telemetry: Optional dict with location, altitude, timestamp for context.
    
    Returns:
        Text description of what the VLM sees in the image.
    """
    try:
        # Read and encode image
        base64_image = _image_to_base64(image_path)

        # Build context from telemetry if available
        context = ""
        if telemetry:
            context = (
                f"\nDrone telemetry context: Location={telemetry.get('location', 'Unknown')}, "
                f"Altitude={telemetry.get('altitude', 'N/A')}m, "
                f"Time={telemetry.get('timestamp', 'Unknown')}"
            )

        # Call Groq VLM API
        response = client.chat.completions.create(
            model=VLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": VLM_SYSTEM_PROMPT + context,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=512,
            temperature=0.2,
        )

        description = response.choices[0].message.content.strip()
        return description

    except Exception as e:
        error_msg = str(e)
        print(f"VLM Error: {error_msg}")
        # Return a fallback description
        return f"[VLM analysis unavailable: {error_msg}] Frame captured at {telemetry.get('location', 'unknown location') if telemetry else 'unknown location'}"


def analyze_image_from_base64(base64_image: str, telemetry: dict = None) -> str:
    """
    Analyze a base64-encoded image using the VLM.
    
    Args:
        base64_image: Base64-encoded JPEG string.
        telemetry: Optional telemetry context.
    
    Returns:
        Text description from the VLM.
    """
    try:
        context = ""
        if telemetry:
            context = (
                f"\nDrone telemetry: Location={telemetry.get('location', 'Unknown')}, "
                f"Altitude={telemetry.get('altitude', 'N/A')}m, "
                f"Time={telemetry.get('timestamp', 'Unknown')}"
            )

        response = client.chat.completions.create(
            model=VLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VLM_SYSTEM_PROMPT + context},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            max_tokens=512,
            temperature=0.2,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"[VLM analysis unavailable: {str(e)}]"


def _image_to_base64(image_path: str) -> str:
    """Read an image file and return as base64 string."""
    import cv2

    frame = cv2.imread(image_path)
    if frame is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Resize if too large (Groq limit: 4MB for base64)
    h, w = frame.shape[:2]
    if w > 1024:
        scale = 1024 / w
        frame = cv2.resize(frame, (1024, int(h * scale)))

    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buffer).decode("utf-8")


def test_vlm_connection() -> bool:
    """Test if the VLM API is accessible."""
    try:
        response = client.chat.completions.create(
            model=VLM_MODEL,
            messages=[{"role": "user", "content": "Say 'VLM OK' if you can read this."}],
            max_tokens=10,
        )
        return "OK" in response.choices[0].message.content
    except Exception:
        return False
