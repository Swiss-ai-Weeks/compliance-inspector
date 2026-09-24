'''
This is a minimum implementation for UI usage if later needed. This has been set to preserve the app.py file in the app's logic, and
allow for an extended execution at a later time. Currently, the demo at "interactive_demo.py" is actually doing the heavy lifting, running
the tool's logic in the command line.
'''

import streamlit as st
import os
import time

# Import functions from our main backend file
# This allows the web UI to use the exact same logic as the terminal CLI
from interactive_demo import (
    _discover_videos, 
    load_sop, 
    extract_frames_with_progress, 
    run_cosmos_reasoning, 
    run_audit
)

st.set_page_config(page_title="Visual Compliance Inspector", layout="wide")

st.title("Visual Compliance Inspector")
st.markdown("Automated SOP Enforcement via NVIDIA Cosmos NIM and NemoClaw")

# 1. Discover videos using the backend function
videos = _discover_videos()

if not videos:
    st.error("No videos found in `data/videos/`. Add .mp4 files and retry.")
    st.stop()

# 2. Sidebar for settings
with st.sidebar:
    st.header("Inspection Settings")
    
    # Map label to video dict for the selectbox
    video_options = {v["label"]: v for v in videos}
    selected_label = st.selectbox("Select Video to Audit", options=list(video_options.keys()))
    selected_video = video_options[selected_label]
    
    mode = st.radio("Execution Mode", ["Live API (Cosmos)", "Mock / Offline"])
    is_mock = (mode == "Mock / Offline")
    
    run_button = st.button("Run Audit", type="primary", use_container_width=True)

# 3. Main UI Layout
col1, col2 = st.columns([0.5, 0.5])

with col1:
    st.subheader("Inspection Feed")
    st.video(selected_video["path"])
    
    # Show SOP info
    st.subheader("Context")
    if not selected_video["sop_path"]:
        st.error(f"No SOP found for model '{selected_video['model']}'.")
    else:
        sop = load_sop(selected_video["sop_path"])
        task_name = sop.get("task_name", selected_video["label"])
        st.info(f"**Target SOP:** {task_name} ({len(sop.get('expected_steps', []))} steps)")

with col2:
    st.subheader("Audit Trail")
    
    if run_button:
        if not selected_video["sop_path"]:
            st.error("Cannot run audit without an SOP.")
        else:
            sop = load_sop(selected_video["sop_path"])
            
            # Use Streamlit spinners to indicate progress
            # Note: The rich console outputs from the imported functions 
            # will still print to the terminal running `streamlit run`, which is great for logs!
            
            with st.spinner("Extracting frames from video..."):
                frames = extract_frames_with_progress(
                    selected_video["path"], 
                    num_frames=20 if is_mock else None, 
                    sample_fps=1
                )
            
            with st.spinner("Cosmos Vision LLM analyzing sequence..."):
                obs = run_cosmos_reasoning(frames, sop, is_mock=is_mock)
                
            with st.spinner("Generating compliance report..."):
                report = run_audit(sop, obs)
            
            # Display Results
            status_color = "green" if report["overall_status"] == "PASS" else "red"
            st.markdown(f"### Final Verdict: :{status_color}[{report['overall_status']}]")
            st.divider()
            
            for step in report["audit_trail"]:
                if step["status"] == "COMPLETED":
                    st.success(f"**Step {step['step_id']}: {step['name']}**\n\nDetected: `{step['window']}`")
                elif step["status"] == "MISSED":
                    st.error(f"**Step {step['step_id']}: {step['name']}**\n\nStatus: `MISSED`")
                elif step["status"] == "OUT_OF_ORDER":
                    st.warning(f"**Step {step['step_id']}: {step['name']}**\n\nStatus: `OUT_OF_ORDER` (Detected at `{step['window']}`)")
                
                with st.expander("View evidence"):
                    st.write(step["evidence"])
    else:
        st.info("Select a video and click **Run audit** to start the analysis pipeline.")