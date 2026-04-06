# Testing and Validation — Drone Security Analyst Agent

## Goal

The goal of validation was to prove that the project behaves correctly in both deterministic demo mode and AI-assisted video mode. The tests focus on three levels:

1. data integrity in SQLite
2. rule-based security escalation
3. end-to-end AI behavior for summaries and chat

## What Was Validated

### 1. Database and Indexing
The system was validated to ensure each analyzed frame is stored and retrievable with the expected metadata.

Checked behaviors:

- frame insertion and replacement work
- detected objects are stored as JSON and parsed back into lists
- queries by object, risk, and time range return the right rows
- the frame count matches the number of processed events

### 2. Rule Engine
The deterministic alert engine was validated independently from the LLM.

Scenarios covered:

- night-time activity produces at least High risk
- loitering is flagged as Medium or above
- perimeter breach escalates to Critical
- repeated vehicle sightings are detected across frames
- unauthorized access attempts are elevated appropriately

### 3. AI Pipeline
The AI-backed parts of the system were validated with API-enabled tests.

Scenarios covered:

- VLM returns a non-empty scene description for a real extracted frame
- frame 13-style breach scenarios are classified as Critical
- summary generation produces a substantial security briefing
- chat responses stay relevant to the latest events and memory context

## Automated Test Cases

| Test | Purpose | Expected Outcome |
|---|---|---|
| `test_frame_indexed_correctly` | Verify frame persistence | Stored record matches the inserted payload |
| `test_truck_query` | Verify object search | Truck-related rows are returned, unrelated rows are not |
| `test_night_alert_triggered` | Verify night and loitering rules | `NIGHT_ACTIVITY` and `LOITERING` are both flagged |
| `test_video_frame_extraction` | Verify OpenCV extraction path | Frames are extracted and saved as images |
| `test_vlm_description` | Verify VLM integration | Description is non-empty and not an error fallback |
| `test_perimeter_breach_critical` | Verify emergency escalation | Breach frame is classified as Critical |
| `test_video_summary_not_empty` | Verify summary generation | Summary is long enough to be useful |
| `test_chat_followup` | Verify conversational follow-up | Response references the relevant midnight event |

## Dynamic Input Scenarios

Dynamic inputs were validated by checking how the system reacts when the input source changes from one frame to the next.

### Video and Frame Variability

- different timestamps across a 24-hour window
- different locations such as gate, garage, parking lot, and perimeter
- different altitude values to simulate patrol movement
- multiple objects in the same frame, such as vehicles plus people
- empty or low-activity scenes that should remain low risk

### Chat Variability

The chat endpoint was tested with follow-up prompts that depend on context and recent indexed events, including:

- "Were there any midnight incidents?"
- "Show all truck events"
- "What happened at the perimeter?"
- "How many critical alerts were there?"

The expected behavior is that the agent uses memory and the query tool rather than answering generically.

## Emergency Response Scenarios

These scenarios were used to confirm that urgent situations are escalated immediately.

| Scenario | Input Pattern | Expected Risk |
|---|---|---|
| Perimeter breach | fence climbing or a breach description | Critical |
| Unauthorized access | no badge plus door attempt | High or Critical |
| Night loitering | person pacing near gate after 22:00 | High |
| Repeated vehicle visit | same vehicle appears again later in the day | Medium |
| Suspicious perimeter presence | person near perimeter fence without badge | Medium |

## Manual Validation Checklist

In addition to automated tests, the system was checked manually through the dashboard:

- the page loads and fetches available videos
- simulation mode streams frames in order
- alerts appear in the left panel for medium and above events
- the event log fills as frames are processed
- the summary modal opens and shows a readable briefing
- filtered searches reduce the visible rows in the event table
- previously indexed frames repopulate the dashboard on reload

## Running Validation Locally

```bash
pytest tests -v
```

If `GROQ_API_KEY` is not available, the API-backed tests are skipped automatically and the deterministic tests still provide coverage for indexing and alert logic.

## Validation Result

The overall validation strategy confirms that the project is stable in three important ways:

- the storage layer is consistent
- the alert rules are deterministic
- the AI outputs are consumable by the dashboard and chat interface
