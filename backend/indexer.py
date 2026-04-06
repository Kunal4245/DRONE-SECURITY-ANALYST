"""
SQLite Frame Indexing System

Provides persistent storage and querying for analyzed drone surveillance frames.
Stores frame metadata, AI-generated analysis results, detected objects, risk levels,
and alert messages in a local SQLite database.
"""

import sqlite3
import json
import os
from typing import Optional

# Database file path — stored in backend directory
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames.db")


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database and create the frame_events table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS frame_events (
            frame_id INTEGER PRIMARY KEY,
            timestamp TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            detected_objects TEXT DEFAULT '[]',
            risk_level TEXT DEFAULT 'Low',
            alert_message TEXT DEFAULT '',
            event_summary TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            vlm_description TEXT DEFAULT '',
            video_source TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def insert_frame(frame_data: dict):
    """
    Insert or replace an analyzed frame into the database.
    
    Args:
        frame_data: Dictionary containing frame_id, timestamp, location,
                    description, detected_objects, risk_level, alert_message,
                    event_summary.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Ensure detected_objects is stored as JSON string
    detected_objects = frame_data.get("detected_objects", [])
    if isinstance(detected_objects, list):
        detected_objects = json.dumps(detected_objects)

    cursor.execute("""
        INSERT OR REPLACE INTO frame_events 
        (frame_id, timestamp, location, description, detected_objects, 
         risk_level, alert_message, event_summary, image_path, vlm_description, video_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        frame_data.get("frame_id"),
        frame_data.get("timestamp", ""),
        frame_data.get("location", ""),
        frame_data.get("description", ""),
        detected_objects,
        frame_data.get("risk_level", "Low"),
        frame_data.get("alert_message", ""),
        frame_data.get("event_summary", ""),
        frame_data.get("image_path", ""),
        frame_data.get("vlm_description", ""),
        frame_data.get("video_source", ""),
    ))
    conn.commit()
    conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a SQLite Row to a plain dictionary with parsed JSON fields."""
    d = dict(row)
    # Parse detected_objects from JSON string to list
    try:
        d["detected_objects"] = json.loads(d.get("detected_objects", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["detected_objects"] = []
    return d


def query_by_object(keyword: str) -> list[dict]:
    """
    Search frames where detected_objects contains the given keyword.
    Uses case-insensitive LIKE search on the JSON string.
    
    Args:
        keyword: Object name to search for (e.g., "truck", "person")
    
    Returns:
        List of matching frame dictionaries.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM frame_events WHERE LOWER(detected_objects) LIKE LOWER(?)",
        (f"%{keyword}%",)
    )
    results = [_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def query_by_time_range(start: str, end: str) -> list[dict]:
    """
    Filter frames by timestamp range (inclusive).
    
    Args:
        start: Start timestamp (e.g., "2024-01-15 22:00:00")
        end: End timestamp (e.g., "2024-01-16 06:00:00")
    
    Returns:
        List of matching frame dictionaries.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM frame_events WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
        (start, end)
    )
    results = [_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def query_by_risk(risk_level: str) -> list[dict]:
    """
    Filter frames by risk level.
    
    Args:
        risk_level: One of "Low", "Medium", "High", "Critical"
    
    Returns:
        List of matching frame dictionaries.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM frame_events WHERE LOWER(risk_level) = LOWER(?)",
        (risk_level,)
    )
    results = [_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_all_frames() -> list[dict]:
    """Return all indexed frames ordered by timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM frame_events ORDER BY timestamp")
    results = [_row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_frame_by_id(frame_id: int) -> Optional[dict]:
    """Get a single indexed frame by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM frame_events WHERE frame_id = ?", (frame_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def clear_all_frames():
    """Delete all frames from the database. Used before re-running simulation."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM frame_events")
    conn.commit()
    conn.close()


def get_frame_count() -> int:
    """Return the number of indexed frames."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM frame_events")
    count = cursor.fetchone()[0]
    conn.close()
    return count
