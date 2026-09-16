# Deterministic sequence validator

import json
import sys

def generate_compliance_report(sop_path: str, observations_path: str, output_path: str):
    with open(sop_path, "r") as f:
        sop = json.load(f)
    
    # Handle both real Cosmos API output and the mock schema structure
    with open(observations_path, "r") as f:
        obs_data = json.load(f)
        # If using the mock with video keys, grab the first video's data for the audit
        if "observed_actions" not in obs_data:
            first_key = list(obs_data.keys())[0]
            observations = obs_data[first_key]["observed_actions"]
        else:
            observations = obs_data["observed_actions"]

    audit_trail = []
    overall_status = "PASS"
    last_valid_end_time = -1

    expected_steps = {step["step_id"]: step["name"] for step in sop["expected_steps"]}

    for obs in observations:
        step_id = obs["step_id"]
        step_name = expected_steps.get(step_id, f"Step {step_id}")
        detected = obs.get("detected", False)
        start_sec = obs.get("start_sec")
        end_sec = obs.get("end_sec")

        if not detected:
            status = "MISSED"
            overall_status = "FAIL"
        else:
            if start_sec is not None and start_sec < last_valid_end_time:
                status = "OUT_OF_ORDER"
                overall_status = "FAIL"
            else:
                status = "COMPLETED"
                last_valid_end_time = end_sec if end_sec is not None else last_valid_end_time

        audit_trail.append({
            "step_id": step_id,
            "name": step_name,
            "status": status,
            "window": f"{start_sec}s - {end_sec}s" if detected else None,
            "evidence": obs.get("visual_evidence", "None")
        })

    report = {
        "overall_status": overall_status,
        "audit_trail": audit_trail
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 src/audit_engine.py <sop.json> <observed.json> <output.json>")
        sys.exit(1)
    generate_compliance_report(sys.argv[1], sys.argv[2], sys.argv[3])