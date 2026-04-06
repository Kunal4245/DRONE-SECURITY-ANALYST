# Testing Documentation Artifact

## Objective

This artifact explains how the Drone Security Analyst system was validated for correctness, stability, and security-response behavior.

Validation focused on three goals:

- verify core frame indexing and query functionality
- verify behavior for dynamic inputs (different frame content, time windows, and video sources)
- verify emergency response escalation (High and Critical risk scenarios)

## Validation Approach

The system was tested using a mixed strategy:

1. Unit-style and integration-style automated tests in `tests/test_agent.py`
2. API-level checks through backend endpoints
3. Manual end-to-end validation through the frontend dashboard

## Functional Test Coverage

| Test Case | Purpose | Expected Result |
|---|---|---|
| Frame indexed correctly | Validate DB insert and retrieval | Stored values match inserted frame payload |
| Object query (`truck`) | Validate object-based search | Matching frames returned; unrelated frames excluded |
| Night activity alert | Validate rule engine behavior | `NIGHT_ACTIVITY` and `LOITERING` flags are triggered appropriately |
| Video frame extraction | Validate dynamic frame generation from video | Frames extracted, metadata populated, image files saved |
| VLM description generation | Validate vision stage output | Non-empty, meaningful image description |
| Perimeter breach classification | Validate emergency severity | Breach scenario escalates to `Critical` |
| Daily/video summary generation | Validate reporting feature | Non-empty concise security briefing |
| Follow-up chat relevance | Validate question-answering behavior | Answers reflect indexed event context |

## Dynamic Input Scenarios

Dynamic inputs were validated by changing one or more dimensions of surveillance data and checking output consistency.

### Scenario Set A: Time Variation

- Daytime frames with routine activity
- Late-night frames (22:00 to 06:00)
- Post-midnight suspicious behavior

Expected behavior:

- normal daytime scenes trend toward Low risk
- suspicious nighttime scenes are escalated to High or above

### Scenario Set B: Content Variation

- empty scenes (no activity)
- known vehicles and routine entries
- unknown person near gate/perimeter
- repeated vehicle appearances
- door access attempts without badge

Expected behavior:

- low/no activity should remain Low risk
- suspicious or repeated patterns should move to Medium/High

### Scenario Set C: Source Variation

- predefined telemetry simulation frames
- extracted frames from uploaded/available video files

Expected behavior:

- pipeline remains stable regardless of source
- output schema remains consistent across all frame origins

## Emergency Response Validation

Emergency response logic was validated with focused threat scenarios.

| Emergency Scenario | Detection Signal | Expected Risk |
|---|---|---|
| Perimeter breach | person climbing or breaching fence | `Critical` |
| Unauthorized access attempt | no-badge door access behavior | `High` or `Critical` |
| Night loitering near main gate | loitering + night window | `High` |
| Suspicious perimeter presence | person near perimeter without authorization | `Medium` or higher |

Additional expectation:

- emergency-class events must appear immediately in real-time stream and alert panel

## API and UI Validation Steps

### API-Level Checks

- `/api/status` confirms service and model metadata availability
- `/api/frames` confirms indexed event retrieval
- `/api/query` confirms filtering by object/risk/time
- `/api/summary` confirms generated narrative output
- `/api/chat` confirms question-answer continuity
- `/ws/simulation` and `/ws/process-video` confirm frame-by-frame streaming behavior

### UI-Level Checks

- event log updates after each frame analysis
- alert cards appear for Medium/High/Critical outputs
- frame details and detected objects render correctly
- filters reduce table rows based on search input
- chat and summary panels return contextually valid output

## Reliability Notes

- Deterministic rule checks provide a safety floor for critical events.
- AI outputs are validated and normalized before persistence.
- If optional external dependencies (e.g., API key) are missing, non-AI tests still validate core behavior.

## Execution Command

Run validation suite:

```bash
pytest tests -v
```

If `GROQ_API_KEY` is unavailable, API-dependent tests are skipped while core deterministic tests continue to validate indexing and rule logic.
