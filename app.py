import streamlit as st
import json
import os

st.set_page_config(page_title="Visual compliance inspector", layout="wide")

st.title("Visual compliance inspector")
st.markdown("Automated SOP Enforcement via NVIDIA Cosmos NIM")

# DEFINING paths - HACHATON project:
VIDEO_PATH = "data/videos/video_Bench_tjusig_full_compliant.mp4"
REPORT_PATH = "output/compliance_report.json"

col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.subheader("Inspection feed")
    if os.path.exists(VIDEO_PATH):
        st.video(VIDEO_PATH)
    else:
        st.error(f"Video file not found: {VIDEO_PATH}")

with col2:
    st.subheader("Audit trail")
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, "r") as f:
            report = json.load(f)

        status_color = "green" if report["overall_status"] == "PASS" else "red"
        st.markdown(f"### Final verdict: :{status_color}[{report['overall_status']}]")
        st.divider()

        for step in report["audit_trail"]:
            if step["status"] == "COMPLETED!":
                st.success(f"GOOD: **Step {step['step_id']}: {step['name']}**\n\nDetected: `{step['window']}`")
            elif step["status"] == "[X] MISSED":
                st.error(f"ERROR: **Step {step['step_id']}: {step['name']}**\n\nStatus: `MISSED`")
            elif step["status"] == "[!] OUT_OF_ORDER":
                st.warning(f"WARNING: **Step {step['step_id']}: {step['name']}**\n\nStatus: `OUT_OF_ORDER` (Detected at `{step['window']}`)")
            
            with st.expander("View Evidence"):
                st.write(step["evidence"])
    else:
        st.info("Run the audit engine to generate the compliance report.")