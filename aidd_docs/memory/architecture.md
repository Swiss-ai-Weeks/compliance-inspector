# Architecture

- **Paradigm**: Microservices (API Backend + UI Frontend)
- **Backend**: FastAPI (Python), Orchestrator, Async Buffer Queue for video chunks
- **Frontend**: Streamlit (Python)
- **Video Processing**: OpenCV / NVIDIA VSS (Sliding window overlap)
- **Data Models**: Pydantic
- **AI Integration (On-Premise via RTX 6000)**:
  - NVIDIA Cosmos NIM (Local Docker container): Multi-choice prompting (A/B/C/D/E) for step detection
  - NVIDIA Nemotron Vision (Local/API): PDF extraction to JSON SOP
  - NVIDIA NeMo Guardrails: (Bonus) Formatting strict LLM outputs to prevent backend crashes
- **Resilience Mechanisms**:
  - *Out of order*: Recovery Mode with chronological batch scanning
  - *Network Failures*: Async Buffer with retry logic
  - *Overlaps*: TRANSITION/IDLE states
  - *Occlusion/Interruption*: "MISSED / WARNING" state fallback
