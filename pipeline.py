import os
import json
from src.ingestion import extract_frames
from src.cosmos_client import analyze_actions
from src.audit_engine import generate_compliance_report

def run_pipeline():
    # Defining file paths
    video_path = "data/videos/video_Bench_tjusig_full_compliant.mp4"
    sop_path = "data/sops/sop_tjusig.json"
    frames_output_path = "output/frames.json"
    observations_output_path = "output/observed_actions.json"
    report_output_path = "output/compliance_report.json"

    # Ensuring output directory exists
    os.makedirs("output", exist_ok=True)

    print(f"Step 1: Extracting frames from {video_path}...")
    # Adding a check to fail gracefully if the video doesn't exist
    if not os.path.exists(video_path):
        print(f"[!] Error: Video not found at {video_path}")
        return

    frames = extract_frames(video_path)
    
    # Saving frames to disk just for debugging/logging
    with open(frames_output_path, "w") as f:
        json.dump(frames, f)
    print(f"OK: Extracted {len(frames)} frames.")

    print(f"\n[Thinking] Step 2: Sending frames to Cosmos reasoner...")
    with open(sop_path, "r") as f:
        sop_data = json.load(f)
    
    # This calls the local Cosmos container
    observations = analyze_actions(frames, sop_data)
    
    # Saving the raw model observations
    with open(observations_output_path, "w") as f:
        json.dump(observations, f, indent=2)
    print(f"OK: Cosmos analysis complete. Saved to {observations_output_path}")

    print(f"\nThinking: Step 3: Running audit engine...")
    # The audit engine expects file paths
    generate_compliance_report(sop_path, observations_output_path, report_output_path)
    print(f"OK: Audit report generated at {report_output_path}")

    print("\nOK: Pipeline finished! You can now run: streamlit run app.py")

if __name__ == "__main__":
    run_pipeline()
