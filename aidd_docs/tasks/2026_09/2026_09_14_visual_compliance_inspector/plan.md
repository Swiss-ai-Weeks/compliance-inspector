---
objective: "A functional prototype of the Visual Compliance Inspector using NVIDIA Cosmos NIM and a sliding window state machine, with a UI for demonstration."
status: pending
---

<!-- Fill or omit these sections; never add, rename, or reorder one. -->

# Plan: Visual Compliance Inspector (Hackathon)

## Overview

| Field      | Value                   |
| ---------- | ----------------------- |
| **Goal**   | Verify operator procedures in video using AI and a state machine. |
| **Source** | hackathon_brief.md      |
| **Stack**  | FastAPI (Backend), Streamlit (Frontend), Pydantic, OpenCV/VSS, NVIDIA NIMs |

## Phases

| #   | Phase        | File                         |
| --- | ------------ | ---------------------------- |
| 1   | Core Engine & Cosmos Integration | [`phase-1.md`](./phase-1.md) |
| 2   | Video Pipeline & Sliding Window | [`phase-2.md`](./phase-2.md) |
| 3   | PDF Procedure Extractor | [`phase-3.md`](./phase-3.md) |
| 4   | Demo App (Split-screen UI) | [`phase-4.md`](./phase-4.md) |

## Resources

| Source | Verified          |
| ------ | ----------------- |
| hackathon_brief.md | Defined the 7-day MVP and architecture. |

## Decisions

| Decision   | Why   |
| ---------- | ----- |
| Sliding Window + State Machine | Cosmos NIM cannot reliably process whole long videos at once. Chunking + overlapping chunks (0-10s, 5-15s) with an orchestrator tracking "IN_PROGRESS" state is required. |
| Modular extraction | Decoupling the procedure definition (JSON) from the video engine allows parallel development for a team of 4. |
