"""
QA Test Cases — Drone Security Analyst Agent

Tests cover:
1. Frame indexing correctness
2. Object-based querying
3. Night activity alert rules
4. Video frame extraction (OpenCV)
5. VLM description generation (requires Groq API)
6. Perimeter breach detection (requires Groq API)
7. Video summary generation (requires Groq API)
8. Chat follow-up questions (requires Groq API)
"""

import os
import sys
import json
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import indexer
import alert_engine
import telemetry
import video_processor

# Check if Groq API key is available
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
HAS_API_KEY = GROQ_API_KEY and GROQ_API_KEY != "your_groq_api_key_here"

# Check if test videos exist
VIDEOS_DIR = os.path.join(os.path.dirname(__file__), '..', 'videos')
HAS_VIDEOS = os.path.exists(VIDEOS_DIR) and any(
    f.endswith('.mp4') for f in os.listdir(VIDEOS_DIR)
) if os.path.exists(VIDEOS_DIR) else False


# ──────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Use a temporary database for each test."""
    test_db = str(tmp_path / "test_frames.db")
    indexer.DB_PATH = test_db
    indexer.init_db()
    alert_engine.reset_vehicle_log()
    yield


# ──────────────────────────────────────────────────────────
# TEST 1: Frame Indexed Correctly
# ──────────────────────────────────────────────────────────

def test_frame_indexed_correctly():
    """Insert a frame into the database, query it back, and verify all fields match."""
    frame_data = {
        "frame_id": 1,
        "timestamp": "2024-01-15 06:00:00",
        "location": "Main Gate",
        "description": "Silver sedan entering through main gate, driver visible",
        "detected_objects": ["sedan", "driver", "main gate"],
        "risk_level": "Low",
        "alert_message": "",
        "event_summary": "Vehicle entering property through the main gate during morning hours",
        "image_path": "video1/frame_001.jpg",
        "vlm_description": "Aerial view showing a silver sedan approaching the main gate of a property",
        "video_source": "test_video.mp4",
    }

    indexer.insert_frame(frame_data)
    result = indexer.get_frame_by_id(1)

    assert result is not None, "Frame should exist in database"
    assert result["frame_id"] == 1
    assert result["timestamp"] == "2024-01-15 06:00:00"
    assert result["location"] == "Main Gate"
    assert "sedan" in result["detected_objects"]
    assert result["risk_level"] == "Low"
    assert result["image_path"] == "video1/frame_001.jpg"
    assert result["vlm_description"] != ""
    assert result["video_source"] == "test_video.mp4"


# ──────────────────────────────────────────────────────────
# TEST 2: Truck Query
# ──────────────────────────────────────────────────────────

def test_truck_query():
    """Insert frames with 'truck' in detected_objects, query by 'truck', verify results."""
    frame_with_truck = {
        "frame_id": 3,
        "timestamp": "2024-01-15 10:00:00",
        "location": "Perimeter North",
        "description": "Delivery truck parked outside perimeter fence",
        "detected_objects": ["truck", "courier", "fence"],
        "risk_level": "Low",
        "alert_message": "",
        "event_summary": "Delivery truck at perimeter",
    }

    frame_without_truck = {
        "frame_id": 4,
        "timestamp": "2024-01-15 12:00:00",
        "location": "Parking Lot",
        "description": "Two employees walking toward main building",
        "detected_objects": ["person", "employee", "badge"],
        "risk_level": "Low",
        "alert_message": "",
        "event_summary": "Employees entering building",
    }

    indexer.insert_frame(frame_with_truck)
    indexer.insert_frame(frame_without_truck)

    results = indexer.query_by_object("truck")

    assert len(results) >= 1, "Should find at least one truck frame"
    assert any(r["frame_id"] == 3 for r in results), "Frame 3 should be in truck results"
    assert not any(r["frame_id"] == 4 for r in results), "Frame 4 should NOT be in truck results"


# ──────────────────────────────────────────────────────────
# TEST 3: Night Alert Triggered
# ──────────────────────────────────────────────────────────

def test_night_alert_triggered():
    """Pass a 23:00 frame to alert_engine, verify it flags NIGHT_ACTIVITY."""
    night_frame = {
        "frame_id": 9,
        "timestamp": "2024-01-15 22:15:00",
        "location": "Main Gate",
        "altitude": 12.0,
        "description": "Person in hoodie loitering near main gate, pacing back and forth",
    }

    flags = alert_engine.evaluate_rules(night_frame)

    assert "NIGHT_ACTIVITY" in flags, f"Expected NIGHT_ACTIVITY flag, got: {flags}"
    assert "LOITERING" in flags, f"Expected LOITERING flag, got: {flags}"

    risk = alert_engine.get_suggested_risk_level(flags)
    assert risk in ("High", "Critical"), f"Night + loitering should be High/Critical, got: {risk}"


# ──────────────────────────────────────────────────────────
# TEST 4: Video Frame Extraction (OpenCV)
# ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_VIDEOS, reason="No test videos available")
def test_video_frame_extraction():
    """Extract frames from a video file and verify output structure."""
    videos = video_processor.list_available_videos()
    assert len(videos) > 0, "Should find at least one video"

    video = videos[0]
    frames = video_processor.extract_frames(
        video["path"],
        interval_seconds=5.0,
        max_frames=3,
    )

    assert len(frames) > 0, "Should extract at least one frame"
    assert len(frames) <= 3, "Should not exceed max_frames"

    frame = frames[0]
    assert "frame_id" in frame
    assert "timestamp" in frame
    assert "image_path" in frame
    assert "location" in frame
    assert "drone_lat" in frame
    assert "altitude" in frame
    assert os.path.exists(frame["image_path"]), f"Image file should exist: {frame['image_path']}"


# ──────────────────────────────────────────────────────────
# TEST 5: VLM Description (Requires API)
# ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_API_KEY or not HAS_VIDEOS, reason="GROQ_API_KEY or videos not available")
def test_vlm_description():
    """Send an extracted frame image to VLM and verify non-empty description."""
    import vlm

    videos = video_processor.list_available_videos()
    frames = video_processor.extract_frames(
        videos[0]["path"],
        interval_seconds=10.0,
        max_frames=1,
    )

    assert len(frames) > 0, "Should extract at least one frame"

    description = vlm.analyze_image(frames[0]["image_path"], frames[0])

    assert description is not None, "VLM description should not be None"
    assert isinstance(description, str), "VLM description should be a string"
    assert len(description) > 20, f"VLM description should be substantial, got {len(description)} chars"
    assert "[VLM analysis unavailable" not in description, "VLM should not return error"


# ──────────────────────────────────────────────────────────
# TEST 6: Perimeter Breach → Critical (Requires API)
# ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_API_KEY, reason="GROQ_API_KEY not available")
def test_perimeter_breach_critical():
    """Verify frame 13 (perimeter breach) gets 'Critical' risk level from AI analysis."""
    import agent

    frame = telemetry.get_frame(13)
    assert frame is not None, "Frame 13 should exist in telemetry"

    result = agent.analyze_single_frame(frame)

    assert result is not None, "Analysis result should not be None"
    assert "error" not in result, f"Analysis should not error: {result}"
    assert result.get("risk_level") == "Critical", \
        f"Frame 13 (perimeter breach) should be Critical, got: {result.get('risk_level')}"


# ──────────────────────────────────────────────────────────
# TEST 7: Video Summary Not Empty (Requires API)
# ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_API_KEY, reason="GROQ_API_KEY not available")
def test_video_summary_not_empty():
    """Call generate_daily_summary and verify it returns a non-empty string."""
    test_frames = [
        {
            "frame_id": 1,
            "timestamp": "2024-01-15 06:00:00",
            "location": "Main Gate",
            "description": "Vehicle entering",
            "detected_objects": ["sedan"],
            "risk_level": "Low",
            "alert_message": "",
            "event_summary": "Silver sedan entering through main gate",
            "vlm_description": "Aerial view of a silver vehicle approaching a gate",
            "video_source": "test_video.mp4",
        },
        {
            "frame_id": 9,
            "timestamp": "2024-01-15 22:15:00",
            "location": "Main Gate",
            "description": "Person loitering at night",
            "detected_objects": ["person", "hoodie"],
            "risk_level": "High",
            "alert_message": "Person loitering at main gate after hours",
            "event_summary": "Suspicious individual loitering at main gate at night",
            "vlm_description": "Person in dark clothing standing near gate at night",
            "video_source": "test_video.mp4",
        },
    ]
    for f in test_frames:
        indexer.insert_frame(f)

    import agent
    summary = agent.generate_daily_summary.invoke("")

    assert summary is not None, "Summary should not be None"
    assert isinstance(summary, str), "Summary should be a string"
    assert len(summary) > 50, f"Summary should be substantial, got {len(summary)} chars"


# ──────────────────────────────────────────────────────────
# TEST 8: Chat Follow-up (Requires API)
# ──────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_API_KEY, reason="GROQ_API_KEY not available")
def test_chat_followup():
    """Ask 'Were there any midnight incidents?' and verify response relevance."""
    midnight_frame = {
        "frame_id": 11,
        "timestamp": "2024-01-16 00:01:00",
        "location": "Main Gate",
        "description": "Same hooded person still loitering at main gate",
        "detected_objects": ["person", "hoodie", "phone"],
        "risk_level": "High",
        "alert_message": "Person loitering at main gate after midnight",
        "event_summary": "Hooded person loitering at main gate past midnight",
        "vlm_description": "Person in dark hoodie standing at main gate, using phone",
        "video_source": "test_video.mp4",
    }
    indexer.insert_frame(midnight_frame)

    import agent
    agent.reset_memory()
    response = agent.chat("Were there any midnight incidents?")

    assert response is not None, "Response should not be None"
    assert isinstance(response, str), "Response should be a string"
    assert len(response) > 20, "Response should be substantive"

    response_lower = response.lower()
    relevant_terms = ["main gate", "loitering", "midnight", "person", "hoodie", "hooded", "night"]
    found_relevant = any(term in response_lower for term in relevant_terms)
    assert found_relevant, \
        f"Response should mention relevant details. Got: {response[:200]}"
