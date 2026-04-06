"""
FastAPI Server — Drone Security Analyst Agent

Provides REST API endpoints and WebSocket streaming for the drone
surveillance analysis system. Supports real video processing with VLM.

Endpoints:
    GET  /api/status              - System health check
    GET  /api/videos              - List available drone videos
    GET  /api/frames              - Get all indexed frames
    POST /api/process-video       - Process a drone video file
    POST /api/analyze/{frame_id}  - Analyze a specific frame
    POST /api/run-simulation      - Run demo with pre-defined frames
    GET  /api/query               - Query by object, risk, or time range
    GET  /api/summary             - Generate video/daily summary
    POST /api/chat                - Chat with the AI agent
    WS   /ws/process-video        - Stream video analysis results live
    WS   /ws/simulation           - Stream demo simulation results live
"""

import os
import json
import asyncio
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

import telemetry
import indexer
import alert_engine
import agent
import video_processor
import vlm

# Load environment
load_dotenv()


# ──────────────────────────────────────────────────────────
# APPLICATION LIFESPAN
# ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    indexer.init_db()
    print("✅ Database initialized")
    print(f"📡 Demo telemetry loaded: {telemetry.get_frame_count()} frames")
    videos = video_processor.list_available_videos()
    print(f"📹 Videos available: {len(videos)}")
    for v in videos:
        print(f"   - {v['filename']} ({v.get('duration_seconds', 0):.1f}s)")
    yield
    print("🛑 Server shutting down")


# ──────────────────────────────────────────────────────────
# APP INITIALIZATION
# ──────────────────────────────────────────────────────────

app = FastAPI(
    title="🛸 Drone Security Analyst Agent",
    description="AI-powered drone surveillance video analysis system with VLM",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────
# REQUEST/RESPONSE MODELS
# ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ProcessVideoRequest(BaseModel):
    filename: str
    interval_seconds: float = 2.0
    max_frames: int = 15


# ──────────────────────────────────────────────────────────
# REST API ENDPOINTS
# ──────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Get system status."""
    videos = video_processor.list_available_videos()
    frame_count = indexer.get_frame_count()
    return {
        "status": "online",
        "models": {
            "vlm": "meta-llama/llama-4-scout-17b-16e-instruct",
            "text": "llama-3.3-70b-versatile",
        },
        "provider": "Groq",
        "indexed_frames": frame_count,
        "available_videos": len(videos),
        "demo_frames": telemetry.get_frame_count(),
    }


@app.get("/api/videos")
async def list_videos():
    """List all available drone video files."""
    videos = video_processor.list_available_videos()
    return {"count": len(videos), "videos": videos}


@app.get("/api/frames")
async def get_frames():
    """Return all indexed frames as JSON."""
    frames = indexer.get_all_frames()
    return {"count": len(frames), "frames": frames}


@app.post("/api/process-video")
async def process_video(request: ProcessVideoRequest):
    """Process a drone video file — extract frames, analyze with VLM + AI agent."""
    # Find the video
    videos = video_processor.list_available_videos()
    video = next((v for v in videos if v["filename"] == request.filename), None)

    if not video:
        return JSONResponse(
            status_code=404,
            content={"error": f"Video '{request.filename}' not found"}
        )

    # Clear previous results
    indexer.clear_all_frames()
    alert_engine.reset_vehicle_log()
    agent.reset_memory()

    # Delete old database file and reinitialize
    if os.path.exists(indexer.DB_PATH):
        os.remove(indexer.DB_PATH)
    indexer.init_db()

    # Extract frames from video
    frames = video_processor.extract_frames(
        video["path"],
        interval_seconds=request.interval_seconds,
        max_frames=request.max_frames,
    )

    results = []
    for frame in frames:
        # Step 1: VLM analyzes the image
        vlm_description = vlm.analyze_image(frame["image_path"], frame)
        frame["vlm_description"] = vlm_description
        frame["description"] = vlm_description

        # Step 2: AI agent does security analysis
        result = agent.analyze_single_frame(frame)
        result["image_url"] = f"/extracted_frames/{frame['image_filename']}"
        results.append(result)

    return {
        "status": "complete",
        "video": request.filename,
        "frames_processed": len(results),
        "results": results,
    }


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Upload a drone video file for processing."""
    videos_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "videos")
    os.makedirs(videos_dir, exist_ok=True)

    filepath = os.path.join(videos_dir, file.filename)
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    info = video_processor.get_video_info(filepath)
    return {"filename": file.filename, "path": filepath, **info}


@app.post("/api/analyze/{frame_id}")
async def analyze_frame_endpoint(frame_id: int):
    """Analyze a specific frame using the AI agent."""
    # Try from demo telemetry first
    frame = telemetry.get_frame(frame_id)
    if not frame:
        return JSONResponse(
            status_code=404,
            content={"error": f"Frame {frame_id} not found"}
        )

    result = agent.analyze_single_frame(frame)
    return {"frame_id": frame_id, "analysis": result}


@app.post("/api/run-simulation")
async def run_simulation():
    """Process demo frames sequentially (fallback/demo mode)."""
    indexer.clear_all_frames()
    alert_engine.reset_vehicle_log()
    agent.reset_memory()

    # Delete old database file and reinitialize
    if os.path.exists(indexer.DB_PATH):
        os.remove(indexer.DB_PATH)
    indexer.init_db()

    results = []
    frames = telemetry.get_all_frames()

    for frame in frames:
        result = agent.analyze_single_frame(frame)
        results.append(result)

    return {
        "status": "complete",
        "frames_processed": len(results),
        "results": results
    }


@app.get("/api/query")
async def query_frames(
    object: str = Query(None, description="Object keyword to search"),
    risk: str = Query(None, description="Risk level filter"),
    start: str = Query(None, description="Start timestamp"),
    end: str = Query(None, description="End timestamp"),
):
    """Query indexed frames by object, risk level, or time range."""
    if object:
        results = indexer.query_by_object(object)
        return {"query_type": "object", "keyword": object, "count": len(results), "results": results}
    elif risk:
        results = indexer.query_by_risk(risk)
        return {"query_type": "risk", "level": risk, "count": len(results), "results": results}
    elif start and end:
        results = indexer.query_by_time_range(start, end)
        return {"query_type": "time_range", "start": start, "end": end, "count": len(results), "results": results}
    else:
        results = indexer.get_all_frames()
        return {"query_type": "all", "count": len(results), "results": results}


@app.get("/api/summary")
async def get_summary():
    """Generate a video/daily security summary using AI."""
    summary = agent.generate_daily_summary.invoke("")
    return {"summary": summary}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Chat with the AI agent for follow-up questions."""
    response = agent.chat(request.message)
    return {"message": request.message, "response": response}


@app.get("/api/telemetry")
async def get_telemetry():
    """Get raw demo telemetry data."""
    frames = telemetry.get_all_frames()
    return {"count": len(frames), "frames": frames}


# ──────────────────────────────────────────────────────────
# WEBSOCKET — REAL-TIME VIDEO PROCESSING
# ──────────────────────────────────────────────────────────

@app.websocket("/ws/process-video")
async def websocket_process_video(websocket: WebSocket):
    """Stream video analysis results frame-by-frame in real-time."""
    await websocket.accept()

    try:
        # Wait for client to send video selection
        data = await websocket.receive_json()
        filename = data.get("filename", "")
        interval = data.get("interval_seconds", 2.0)
        max_frames = data.get("max_frames", 15)

        # Find the video
        videos = video_processor.list_available_videos()
        video = next((v for v in videos if v["filename"] == filename), None)

        if not video:
            await websocket.send_json({
                "type": "error",
                "message": f"Video '{filename}' not found"
            })
            return

        # Clear previous results
        indexer.clear_all_frames()
        alert_engine.reset_vehicle_log()
        agent.reset_memory()

        # Delete old database file and reinitialize
        if os.path.exists(indexer.DB_PATH):
            os.remove(indexer.DB_PATH)
        indexer.init_db()

        # Extract frames
        frames = await asyncio.to_thread(
            video_processor.extract_frames,
            video["path"],
            interval_seconds=interval,
            max_frames=max_frames,
        )

        total = len(frames)

        await websocket.send_json({
            "type": "simulation_start",
            "total_frames": total,
            "video": filename,
            "message": f"🛸 Processing drone video: {filename} ({total} frames extracted)"
        })

        for i, frame in enumerate(frames):
            # Send processing status
            await websocket.send_json({
                "type": "frame_processing",
                "frame_id": frame["frame_id"],
                "progress": f"{i + 1}/{total}",
                "message": f"🔍 VLM analyzing frame {frame['frame_id']}..."
            })

            # Step 1: VLM describes the image
            vlm_description = await asyncio.to_thread(
                vlm.analyze_image, frame["image_path"], frame
            )
            frame["vlm_description"] = vlm_description
            frame["description"] = vlm_description

            # Send VLM result
            await websocket.send_json({
                "type": "vlm_result",
                "frame_id": frame["frame_id"],
                "vlm_description": vlm_description,
                "message": f"👁️ VLM: {vlm_description[:100]}..."
            })

            # Step 2: AI agent security analysis
            result = await asyncio.to_thread(agent.analyze_single_frame, frame)

            # Build frame result message
            frame_result = {
                "type": "frame_result",
                "frame_id": frame["frame_id"],
                "timestamp": frame["timestamp"],
                "location": frame["location"],
                "altitude": frame["altitude"],
                "drone_lat": frame["drone_lat"],
                "drone_lon": frame["drone_lon"],
                "description": vlm_description,
                "vlm_description": vlm_description,
                "image_url": f"/extracted_frames/{frame['image_filename']}",
                "video_source": frame.get("video_source", ""),
                "analysis": result,
                "progress": f"{i + 1}/{total}",
            }

            await websocket.send_json(frame_result)
            await asyncio.sleep(0.5)

        # Completion
        await websocket.send_json({
            "type": "simulation_complete",
            "total_frames": total,
            "video": filename,
            "message": f"✅ Video analysis complete! {total} frames from {filename} analyzed."
        })

    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error: {str(e)}"
            })
        except Exception:
            pass


@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    """Stream demo simulation (text-based frames) in real-time."""
    await websocket.accept()

    try:
        indexer.clear_all_frames()
        alert_engine.reset_vehicle_log()
        agent.reset_memory()

        # Delete old database file and reinitialize
        if os.path.exists(indexer.DB_PATH):
            os.remove(indexer.DB_PATH)
        indexer.init_db()

        frames = telemetry.get_all_frames()
        total = len(frames)

        await websocket.send_json({
            "type": "simulation_start",
            "total_frames": total,
            "message": "🛸 Starting demo simulation with pre-defined frames..."
        })

        for i, frame in enumerate(frames):
            await websocket.send_json({
                "type": "frame_processing",
                "frame_id": frame["frame_id"],
                "progress": f"{i + 1}/{total}",
                "message": f"Analyzing frame {frame['frame_id']}..."
            })

            result = await asyncio.to_thread(agent.analyze_single_frame, frame)

            frame_result = {
                "type": "frame_result",
                "frame_id": frame["frame_id"],
                "timestamp": frame["timestamp"],
                "location": frame["location"],
                "altitude": frame["altitude"],
                "drone_lat": frame["drone_lat"],
                "drone_lon": frame["drone_lon"],
                "description": frame["description"],
                "analysis": result,
                "progress": f"{i + 1}/{total}",
            }

            await websocket.send_json(frame_result)
            await asyncio.sleep(1.0)

        await websocket.send_json({
            "type": "simulation_complete",
            "total_frames": total,
            "message": "✅ Demo simulation complete!"
        })

    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Error during simulation: {str(e)}"
            })
        except Exception:
            pass


# ──────────────────────────────────────────────────────────
# STATIC FILE SERVING
# ──────────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
EXTRACTED_FRAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted_frames")

# Ensure extracted frames directory exists
os.makedirs(EXTRACTED_FRAMES_DIR, exist_ok=True)

# Serve extracted frame images
app.mount("/extracted_frames", StaticFiles(directory=EXTRACTED_FRAMES_DIR), name="extracted_frames")

# Serve frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main dashboard HTML."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Place index.html in ../frontend/"}


# ──────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=False)
