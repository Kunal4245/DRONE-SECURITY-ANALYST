"""
Simulated Drone Telemetry & Frame Generator

Provides 15 pre-defined simulation frames representing a 24-hour drone
surveillance session over a fixed property. Each frame includes telemetry
data (GPS, altitude) and a text description of what the drone camera sees.
"""

from typing import Optional

# GPS coordinates for each location on the property
LOCATION_COORDS = {
    "Main Gate": (37.7749, -122.4194),
    "Garage": (37.7751, -122.4190),
    "Perimeter North": (37.7755, -122.4194),
    "Perimeter East": (37.7749, -122.4188),
    "Parking Lot": (37.7747, -122.4192),
}

# 15 pre-defined simulation frames covering a 24-hour surveillance window
FRAMES = [
    {
        "frame_id": 1,
        "timestamp": "2024-01-15 06:00:00",
        "location": "Main Gate",
        "altitude": 15.0,
        "description": "Silver sedan entering through main gate, driver visible",
    },
    {
        "frame_id": 2,
        "timestamp": "2024-01-15 08:30:00",
        "location": "Garage",
        "altitude": 12.0,
        "description": "Blue Ford F150 parked near garage, no activity",
    },
    {
        "frame_id": 3,
        "timestamp": "2024-01-15 10:00:00",
        "location": "Perimeter North",
        "altitude": 20.0,
        "description": "Delivery truck parked outside perimeter fence, courier visible",
    },
    {
        "frame_id": 4,
        "timestamp": "2024-01-15 12:00:00",
        "location": "Parking Lot",
        "altitude": 18.0,
        "description": "Two employees walking toward main building with badges visible",
    },
    {
        "frame_id": 5,
        "timestamp": "2024-01-15 14:00:00",
        "location": "Main Gate",
        "altitude": 15.0,
        "description": "Blue Ford F150 attempting to exit, gate sensor triggered",
    },
    {
        "frame_id": 6,
        "timestamp": "2024-01-15 16:30:00",
        "location": "Perimeter East",
        "altitude": 22.0,
        "description": "Unknown person in dark clothing near perimeter fence, no badge",
    },
    {
        "frame_id": 7,
        "timestamp": "2024-01-15 18:00:00",
        "location": "Parking Lot",
        "altitude": 15.0,
        "description": "Parking lot empty, all vehicles have exited",
    },
    {
        "frame_id": 8,
        "timestamp": "2024-01-15 20:00:00",
        "location": "Main Gate",
        "altitude": 15.0,
        "description": "Security guard doing routine patrol at main gate",
    },
    {
        "frame_id": 9,
        "timestamp": "2024-01-15 22:15:00",
        "location": "Main Gate",
        "altitude": 12.0,
        "description": "Person in hoodie loitering near main gate, pacing back and forth",
    },
    {
        "frame_id": 10,
        "timestamp": "2024-01-15 23:45:00",
        "location": "Garage",
        "altitude": 10.0,
        "description": "Unidentified person attempting to open garage side door, no badge",
    },
    {
        "frame_id": 11,
        "timestamp": "2024-01-16 00:01:00",
        "location": "Main Gate",
        "altitude": 12.0,
        "description": "Same hooded person still loitering at main gate, now using phone",
    },
    {
        "frame_id": 12,
        "timestamp": "2024-01-16 00:30:00",
        "location": "Perimeter North",
        "altitude": 25.0,
        "description": "Person attempting to climb perimeter fence on north side",
    },
    {
        "frame_id": 13,
        "timestamp": "2024-01-16 01:00:00",
        "location": "Perimeter North",
        "altitude": 25.0,
        "description": "Person has breached perimeter fence, now inside property boundary",
    },
    {
        "frame_id": 14,
        "timestamp": "2024-01-16 02:30:00",
        "location": "Perimeter North",
        "altitude": 20.0,
        "description": "No activity detected, perimeter clear",
    },
    {
        "frame_id": 15,
        "timestamp": "2024-01-16 06:00:00",
        "location": "Main Gate",
        "altitude": 15.0,
        "description": "Blue Ford F150 entering property again, second visit today",
    },
]


def get_frame(frame_id: int) -> Optional[dict]:
    """Get a single frame by ID. Returns None if not found."""
    for frame in FRAMES:
        if frame["frame_id"] == frame_id:
            # Enrich with GPS coordinates
            lat, lon = LOCATION_COORDS.get(frame["location"], (0.0, 0.0))
            return {**frame, "drone_lat": lat, "drone_lon": lon}
    return None


def get_all_frames() -> list[dict]:
    """Get all 15 simulation frames, enriched with GPS coordinates."""
    enriched = []
    for frame in FRAMES:
        lat, lon = LOCATION_COORDS.get(frame["location"], (0.0, 0.0))
        enriched.append({**frame, "drone_lat": lat, "drone_lon": lon})
    return enriched


def get_frame_count() -> int:
    """Return total number of simulation frames."""
    return len(FRAMES)
