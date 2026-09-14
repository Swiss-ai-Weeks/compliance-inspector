# Visual Compliance Inspector

## Vision
To build a system that watches a video of a real-world process (such as a worker assembling an IKEA shelf or performing a maintenance task) and determines whether the required steps were completed correctly.

## Architecture
- **Eye (Video Processor):** Captures frames from video over time to build temporal context.
- **Brain (Cosmos NIM):** Analyzes the sequence of frames to understand what action is currently taking place.
- **Inspector (Compliance Engine):** Compares the understood actions against a predefined Standard Operating Procedure (SOP) to track completion status and flag errors.
- **Interface (Streamlit):** Provides a visual dashboard showing video playback alongside real-time compliance status.
