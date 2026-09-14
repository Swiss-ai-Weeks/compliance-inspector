# Project Brief: Visual Compliance Inspector

## Overview
- **Project**: Visual Compliance Inspector
- **Event**: Swiss AI Weeks / HPE Hackathon
- **Difficulty**: Medium
- **Upstream Repository**: <https://github.com/Swiss-ai-Weeks/compliance-inspector>
- **Target Model**: `cosmos3-nano-reasoner` (NVIDIA Cosmos NIM)
- **Core Technologies**: VSS (Video Storage Server), NVIDIA Cosmos NIM, OpenCV, Streamlit

## Problem Statement
Can AI tell whether a procedure was actually followed?
Industrial maintenance and manual assembly processes require strict adherence to Standard Operating Procedures (SOPs). Existing computer vision systems focus on single-frame object detection or image classification, failing to comprehend chronological sequences of actions.

## Objective
Build a video-based compliance inspector that analyzes footage of a worker or industrial process over time to verify procedure adherence:
1. Identify which steps of the procedure were completed correctly.
2. Identify which steps were missed or skipped.
3. Determine timestamps (start and end) for every relevant event.
4. Provide temporal reasoning across frames rather than isolated snapshot analysis.

## Datasets
- **HATREC Video Dataset**: <https://www.kaggle.com/datasets/ayoznur/hatrec-video-dataset>
- **Assembly101**: <https://assembly-101.github.io/>
- **IKEA Manuals at Work**: <https://github.com/yunongLiu1/IKEA-Manuals-at-Work>
  - Local sample: `video_ikea/video_Shelf_laiva_28FOnQ-9yy8_28FOnQ-9yy8.mp4`

## Infrastructure Context
- **GPU Inference Host**: Dedicated machine equipped with GPU for hosting/running the `cosmos3-nano-reasoner` NIM.
- **Access**: Configured via SSH.
- **Collaboration**: Shared notepad with other participants for notes and shared endpoints.

## Success Criteria
- [ ] End-to-end temporal evaluation on sample video (IKEA shelf assembly / maintenance footage).
- [ ] Real-time or batch compliance state extraction (`Pending`, `In Progress`, `Completed`, `Missed`).
- [ ] Detection of out-of-order execution or skipped steps.
- [ ] Timeline visualization displaying video along with step verification timestamps.
