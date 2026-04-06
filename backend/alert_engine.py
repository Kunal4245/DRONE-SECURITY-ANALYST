"""
Rule-Based Alert Engine

Applies deterministic security rules BEFORE AI analysis to flag potential
threats. These flags enrich the AI agent's prompt with pre-identified risks,
improving the quality and consistency of AI-generated alerts.

Rules:
- Night activity: events between 22:00-06:00
- Perimeter breach: climbing or breaching perimeter fence
- Repeated vehicle: same vehicle seen multiple times
- Unauthorized access: attempting to open doors without badge
- Loitering: person pacing or lingering in one area
"""

from datetime import datetime
from typing import Optional


# Track vehicles seen across frames for repeat detection
_vehicle_log: dict[str, int] = {}


def reset_vehicle_log():
    """Reset the vehicle tracking log. Call before a new simulation run."""
    global _vehicle_log
    _vehicle_log = {}


def _parse_hour(timestamp: str) -> Optional[int]:
    """Extract the hour from a timestamp string."""
    try:
        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        return dt.hour
    except (ValueError, TypeError):
        return None


def _is_night_time(hour: int) -> bool:
    """Check if the hour falls within the night window (22:00-06:00)."""
    return hour >= 22 or hour < 6


def _check_night_activity(frame: dict) -> Optional[str]:
    """Flag frames occurring during night hours (22:00-06:00)."""
    hour = _parse_hour(frame.get("timestamp", ""))
    if hour is not None and _is_night_time(hour):
        return "NIGHT_ACTIVITY"
    return None


def _check_perimeter_breach(frame: dict) -> Optional[str]:
    """Flag perimeter-related security events (climbing, breaching)."""
    location = frame.get("location", "").lower()
    description = frame.get("description", "").lower()

    if "perimeter" in location:
        breach_keywords = ["climb", "breach", "cut", "break", "jump", "scale"]
        if any(kw in description for kw in breach_keywords):
            return "PERIMETER_BREACH"
        # Person near perimeter without badge is also suspicious
        if "person" in description or "unknown" in description:
            return "PERIMETER_SUSPICIOUS"
    return None


def _check_repeated_vehicle(frame: dict) -> Optional[str]:
    """Track vehicles and flag those seen more than once."""
    global _vehicle_log
    description = frame.get("description", "").lower()

    # Extract vehicle identifiers from description
    vehicle_keywords = ["sedan", "truck", "f150", "suv", "van", "car", "vehicle"]
    for keyword in vehicle_keywords:
        if keyword in description:
            # Use a combination of keyword + any color/make for tracking
            vehicle_id = keyword
            # Try to extract color for more specific tracking
            colors = ["blue", "red", "white", "black", "silver", "green", "gray"]
            for color in colors:
                if color in description:
                    vehicle_id = f"{color}_{keyword}"
                    break

            _vehicle_log[vehicle_id] = _vehicle_log.get(vehicle_id, 0) + 1
            if _vehicle_log[vehicle_id] > 1:
                return "REPEATED_VEHICLE"
    return None


def _check_unauthorized_access(frame: dict) -> Optional[str]:
    """Flag unauthorized access attempts (no badge, attempting to open doors)."""
    description = frame.get("description", "").lower()

    unauthorized_keywords = [
        "attempting to open",
        "no badge",
        "unauthorized",
        "forced entry",
        "break in",
        "picking lock",
    ]
    if any(kw in description for kw in unauthorized_keywords):
        return "UNAUTHORIZED_ACCESS"
    return None


def _check_loitering(frame: dict) -> Optional[str]:
    """Flag loitering behavior (person pacing, lingering)."""
    description = frame.get("description", "").lower()

    loitering_keywords = ["loitering", "pacing", "lingering", "waiting", "standing around"]
    if any(kw in description for kw in loitering_keywords):
        return "LOITERING"
    return None


def evaluate_rules(frame: dict) -> list[str]:
    """
    Apply all security rules to a frame and return a list of triggered flags.
    
    Args:
        frame: Dictionary with timestamp, location, description fields.
    
    Returns:
        List of string flags (e.g., ["NIGHT_ACTIVITY", "LOITERING"])
    """
    flags = []

    checks = [
        _check_night_activity,
        _check_perimeter_breach,
        _check_repeated_vehicle,
        _check_unauthorized_access,
        _check_loitering,
    ]

    for check in checks:
        result = check(frame)
        if result:
            flags.append(result)

    return flags


def get_suggested_risk_level(flags: list[str]) -> str:
    """
    Suggest a minimum risk level based on triggered rule flags.
    The AI agent may upgrade this based on its own analysis.
    
    Args:
        flags: List of triggered rule flags.
    
    Returns:
        Suggested risk level string.
    """
    if "PERIMETER_BREACH" in flags:
        return "Critical"
    if "UNAUTHORIZED_ACCESS" in flags and "NIGHT_ACTIVITY" in flags:
        return "Critical"
    if "UNAUTHORIZED_ACCESS" in flags:
        return "High"
    if "NIGHT_ACTIVITY" in flags and "LOITERING" in flags:
        return "High"
    if "NIGHT_ACTIVITY" in flags:
        return "High"
    if "LOITERING" in flags:
        return "Medium"
    if "REPEATED_VEHICLE" in flags:
        return "Medium"
    if "PERIMETER_SUSPICIOUS" in flags:
        return "Medium"
    return "Low"
