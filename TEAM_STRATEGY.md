# Visual Compliance Inspector - Hackathon Strategy & Architecture

Welcome team! For day 1, while I was setting up our beast of a machine (the NVIDIA RTX 6000), I did a solo brainstorming session to map out our game plan, architecture, and core logic. 

Here is the complete blueprint of what we are building over the next 7 days, how we'll build it, and the strategies we'll employ.

## 1. The Goal (Our MVP)
We are building an **Autonomous Video Analysis System** ("Compliance Agent") that verifies if an operator strictly follows an assembly or maintenance procedure.
* **Target Dataset:** Simple assembly tasks (e.g., *IKEA-Manuals-at-Work* or *Assembly101*).
* **The Demo (User Experience):** A web interface showing the video synchronized with a smart checklist. The system will autonomously check off steps (e.g., `[✓] Step 1 completed (00:15)`, `[✗] Step 2 missed`) and provide a final compliance verdict.

## 2. System Architecture (Microservices)
To ensure our solution is "Enterprise-Grade" (ready for Cloud/Edge deployment) and respects industrial confidentiality, we are using a microservices architecture:

* **Hardware:** NVIDIA RTX PRO Server 6000 (96 GB VRAM) running Docker NIM containers locally. **Zero video data goes to the public cloud.**
* **Backend:** **FastAPI (Python)**. This is the core engine hosting the business logic, the state machine, and API calls.
* **Frontend:** **Streamlit**. A lightweight web UI communicating with the backend via HTTP.
* **Core Stack:** Python, OpenCV/VSS for video processing, Pydantic for data validation, and NVIDIA NIM (OpenAI format compatible APIs).

## 3. The Core Strategy: Intelligent State Machine & Sliding Windows
Running LLMs on full, continuous video is too heavy and error-prone. Instead, we are using a **"Sliding Window + Intelligent State Machine"** approach:

### The Video Pipeline
* The video stream is sliced into **5 to 10-second chunks**.
* Chunks will have a slight **overlap** to ensure we don't miss context happening right at the cut.

### The Orchestrator (State Machine)
The FastAPI backend runs a state machine to track the operator's progress. To manage unpredictable human behavior (pauses, out-of-order actions) without exploding API costs, it operates in two modes:

1. **Standard Mode:**
   * The orchestrator asks the **NVIDIA Cosmos NIM** to analyze the current video chunk and choose between: the *next 3 expected steps*, a *Pause*, or a *Transition*.
   * If a *Pause* or *Transition* is detected, the system waits patiently. This prevents double-counting actions due to our video overlaps.
2. **Global Search (Recovery) Mode:**
   * If Cosmos detects an "Unknown Action", the orchestrator pauses standard tracking.
   * It scans all procedure steps in batches of 3, in **strict chronological order**.
   * It stops at the first match to avoid conflicting repeated actions, logs the matched step, and emits a *Warning* (since the operator deviated from the standard flow).

### Output Formatting & Reliability
* **Validation:** We will use **NVIDIA NeMo Guardrails** (or Pydantic/Regex as a fallback) to force the LLM to output strictly formatted JSON/Enum responses. This keeps the state machine perfectly synced.
* **Resilience:** The orchestrator features an **Async Buffer**. If the API times out, video chunks aren't lost; they queue up and retry, guaranteeing 100% traceability.

## 4. Execution Plan & Next Steps
Since the RTX 6000 is now up and running, here is how we can divide the work:

* **Video Processing Pipeline:** Implementing OpenCV chunking with overlaps and the async buffer.
* **Backend & State Machine:** Building the FastAPI server, integrating the Cosmos NIM API, and coding the Standard/Recovery modes.
* **Frontend (Streamlit):** Building the UI with video playback and the dynamic checklist.
* **Bonus (If time permits):** Automated PDF Import. A module that reads a PDF manual using a Vision LLM, then uses a NeMo AI self-correction pass to ensure each extracted step is unique and highly contextualized (e.g., "Screw the 1st leg" instead of just "Screw"), outputting a perfect JSON for our orchestrator.

## 5. The Long-Term Vision (For the Jury Pitch)
Keep these points in mind for our final presentation. This MVP is the foundation for a much larger industrial system:
1. **Real-time Intervention:** Alerting operators *before* they make irreversible errors.
2. **Factory Integration (RAG):** Plugging into factory documentation where AI-generated procedures are validated by Human Methods Engineers.
3. **Physical AI Supervision:** Auditing autonomous robots (NVIDIA Isaac) on assembly lines.
4. **Fine Quality Control:** Moving beyond *detecting* an action to *evaluating* the quality/defects of the execution.
