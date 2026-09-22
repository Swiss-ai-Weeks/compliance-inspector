---
objective: "Implement a real-time capable greedy alignment algorithm for the Visual Compliance Inspector."
status: implemented
---

# Plan: Greedy Alignment Algorithm

## Overview

| Field      | Value                   |
| ---------- | ----------------------- |
| **Goal**   | Implement a noise-tolerant greedy state machine for real-time video processing. |
| **Source** | Hackathon Brainstorm Session |

## Phases

| #   | Phase        | File                         |
| --- | ------------ | ---------------------------- |
| 1   | Greedy Logic | [`phase-1.md`](./phase-1.md) |
| 2   | Integration  | [`phase-2.md`](./phase-2.md) |

## Decisions

| Decision   | Why   |
| ---------- | ----- |
| Hysteresis (Grace Period) | Prevents the algorithm from prematurely closing a step when the AI temporarily loses sight of the action (noise). |
| Inertia & Suspension | Prevents catastrophic AI ties. If 2 steps score high: favor the active one. If neither is active, wait for the next chunk. |
| Locking (No Backtracking) | Prevents timeline corruption. Once a step is closed, it is locked. The UI and pipeline expect exactly 1 span per step. |
