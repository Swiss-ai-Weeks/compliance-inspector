# Project Brief

- **Goal**: Verify operator procedures in video using AI and a state machine.
- **Domain**: Visual Compliance Inspector (Industrial SOP enforcement)
- **Target Audience**: Factory supervisors, quality control managers, HPE & NVIDIA Hackathon Jury
- **Timeline**: 7-day Hackathon (MVP)

## Core Mechanics
- The operator is filmed assembling a component.
- A sliding window sends short, overlapping video chunks to the backend.
- The state machine compares Cosmos NIM detections to the expected JSON procedure.
- If an action is missed, skipped, or out-of-order, the system flags a Warning but continues checking.
- The UI (Streamlit) updates a live checklist and issues a final compliance report.
