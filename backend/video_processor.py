"""
Video Processor — OpenCV Frame Extraction

Extracts key frames from drone surveillance video files at configurable
intervals. Each extracted frame is saved as a JPEG image and paired with
simulated telemetry data (timestamp, GPS, altitude).
"""

import cv2
import os
import json
from datetime import datetime, timedelta
from typing import Optional

# Directory for extracted frames
FRAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_frames")


def ensure_frames_dir():
    """Create the extracted frames directory if it doesn't exist."""
    os.makedirs(FRAMES_DIR, exist_ok=True)


def get_video_info(video_path: str) -> dict:
    """
    Get metadata about a video file.
    
    Returns:
        Dictionary with fps, total_frames, duration_seconds, width, height.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": f"Cannot open video: {video_path}"}

    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    info["duration_seconds"] = info["total_frames"] / info["fps"] if info["fps"] > 0 else 0
    cap.release()
    return info


def extract_frames(
    video_path: str,
    interval_seconds: float = 2.0,
    max_frames: int = 20,
    base_timestamp: Optional[str] = None,
    video_id: Optional[str] = None,
) -> list[dict]:
    """
    Extract key frames from a video at regular intervals.
    
    Args:
        video_path: Path to the video file.
        interval_seconds: Extract one frame every N seconds.
        max_frames: Maximum number of frames to extract.
        base_timestamp: Starting timestamp (default: current time).
        video_id: Identifier for this video (used in filenames).
    
    Returns:
        List of frame dictionaries with:
        - frame_id, timestamp, image_path, image_filename,
          video_source, frame_number, drone_lat, drone_lon, altitude, location
    """
    ensure_frames_dir()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = int(fps * interval_seconds)

    # Generate a video_id from filename if not provided
    if not video_id:
        video_id = os.path.splitext(os.path.basename(video_path))[0]
        # Clean up the id
        video_id = video_id.replace(" ", "_")[:30]

    # Create a subdirectory for this video's frames
    video_frames_dir = os.path.join(FRAMES_DIR, video_id)
    os.makedirs(video_frames_dir, exist_ok=True)

    # Base timestamp for generating frame timestamps
    if base_timestamp:
        base_time = datetime.strptime(base_timestamp, "%Y-%m-%d %H:%M:%S")
    else:
        base_time = datetime.now().replace(microsecond=0)

    # Simulated patrol locations (cycle through these)
    patrol_locations = [
        {"location": "Main Gate", "lat": 37.7749, "lon": -122.4194},
        {"location": "Perimeter North", "lat": 37.7755, "lon": -122.4194},
        {"location": "Parking Lot", "lat": 37.7747, "lon": -122.4192},
        {"location": "Garage", "lat": 37.7751, "lon": -122.4190},
        {"location": "Perimeter East", "lat": 37.7749, "lon": -122.4188},
        {"location": "Building Entrance", "lat": 37.7750, "lon": -122.4191},
    ]

    # Simulated altitudes (drone varies height during patrol)
    altitudes = [15.0, 18.0, 20.0, 12.0, 22.0, 15.0, 25.0, 18.0]

    extracted_frames = []
    frame_count = 0
    frame_number = 0

    while True:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        if not ret or frame_count >= max_frames:
            break

        # Save frame as JPEG
        image_filename = f"frame_{frame_count + 1:03d}.jpg"
        image_path = os.path.join(video_frames_dir, image_filename)

        # Resize if too large (keep under 4MB for Groq API)
        h, w = frame.shape[:2]
        if w > 1280:
            scale = 1280 / w
            frame = cv2.resize(frame, (1280, int(h * scale)))

        cv2.imwrite(image_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Generate telemetry for this frame
        patrol = patrol_locations[frame_count % len(patrol_locations)]
        frame_timestamp = base_time + timedelta(seconds=frame_count * interval_seconds)

        frame_data = {
            "frame_id": frame_count + 1,
            "timestamp": frame_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "image_path": image_path,
            "image_filename": f"{video_id}/{image_filename}",
            "video_source": os.path.basename(video_path),
            "video_frame_number": frame_number,
            "location": patrol["location"],
            "drone_lat": patrol["lat"],
            "drone_lon": patrol["lon"],
            "altitude": altitudes[frame_count % len(altitudes)],
            "description": "",  # Will be filled by VLM
        }

        extracted_frames.append(frame_data)
        frame_count += 1
        frame_number += frame_interval

    cap.release()
    return extracted_frames


def list_available_videos(videos_dir: str = None) -> list[dict]:
    """
    List all video files in the videos directory.
    
    Returns:
        List of dicts with filename, path, and video info.
    """
    if videos_dir is None:
        videos_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "videos"
        )

    if not os.path.exists(videos_dir):
        return []

    videos = []
    video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    for filename in os.listdir(videos_dir):
        ext = os.path.splitext(filename)[1].lower()
        if ext in video_extensions:
            filepath = os.path.join(videos_dir, filename)
            info = get_video_info(filepath)
            videos.append({
                "filename": filename,
                "path": filepath,
                **info,
            })

    return videos


def get_frame_as_base64(image_path: str) -> str:
    """Read an image file and return as base64-encoded JPEG string."""
    import base64

    # Read and optionally resize the image
    frame = cv2.imread(image_path)
    if frame is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Ensure image is under 4MB for Groq API
    h, w = frame.shape[:2]
    if w > 1024:
        scale = 1024 / w
        frame = cv2.resize(frame, (1024, int(h * scale)))

    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(buffer).decode("utf-8")
