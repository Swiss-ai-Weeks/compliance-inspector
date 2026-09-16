# Temporal video frame extraction

import os
import sys
import base64
import json
import cv2

def extract_frames(video_path: str, target_fps: float = 1.0, max_dimension: int = 640) -> list[dict]:
    # Extract frames at target_fps, downscales them, and converts to base64.

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(round(native_fps / target_fps)))

    frames = []
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            timestamp_sec = int(round(frame_idx / native_fps))

            # Downscale preserving aspect ratio to save VRAM/token limits
            h, w = frame.shape[:2]
            scale = max_dimension / max(h, w)
            if scale < 1.0:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            b64_str = base64.b64encode(buffer).decode("utf-8")

            frames.append({
                "timestamp_sec": timestamp_sec,
                "base64": b64_str
            })

        frame_idx += 1

    cap.release()
    return frames

# Standalone execution for testing Track A (Ingestion) independently
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 src/ingestion.py <video_path.mp4> <output_frames.json>")
        sys.exit(1)
        
    video_input = sys.argv[1]
    json_output = sys.argv[2]
    
    print(f"Extracting frames from {video_input}...")
    extracted = extract_frames(video_input)
    
    # Exclude base64 strings from terminal output to avoid flooding stdout
    summary = [{"timestamp_sec": f["timestamp_sec"], "base64": f"{f['base64'][:20]}..."} for f in extracted]
    print(f"Extracted {len(extracted)} frames:\n{json.dumps(summary, indent=2)}")
    
    with open(json_output, "w") as f:
        json.dump(extracted, f)
    print(f"\nFull payload written to {json_output}")