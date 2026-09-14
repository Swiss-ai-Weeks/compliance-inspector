import streamlit as st
import json
import time
import os
import tempfile
from src.video_processor import VideoProcessor
from src.nim_client import NIMClient
from src.compliance_engine import ComplianceEngine

st.set_page_config(page_title="Visual Compliance Inspector", layout="wide")

st.title("👁️ Visual Compliance Inspector")
st.markdown("Analyzing video footage to ensure Standard Operating Procedures (SOP) are followed correctly.")

# Load SOP
@st.cache_data
def load_sop(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

sop_data = load_sop("sop.json")

# Initialize Session State
if 'compliance_state' not in st.session_state:
    st.session_state.engine = ComplianceEngine(sop_data)
    st.session_state.compliance_state = st.session_state.engine.state
    st.session_state.is_processing = False
    
# Layout
col1, col2 = st.columns([2, 1])

with col2:
    st.header("📋 Procedure Checklist")
    status_placeholder = st.empty()
    
    def render_checklist():
        html = "<ul>"
        for step in st.session_state.compliance_state:
            color = "gray"
            icon = "⏳"
            if step["status"] == "Completed":
                color = "green"
                icon = "✅"
            elif step["status"] == "In Progress":
                color = "orange"
                icon = "🔄"
            elif step["status"] == "Missed":
                color = "red"
                icon = "❌"
                
            html += f"<li style='color:{color}; margin-bottom:10px;'><strong>{icon} {step['id'].upper()}</strong>: {step['description']} <br><small>Status: {step['status']}</small></li>"
        html += "</ul>"
        status_placeholder.markdown(html, unsafe_allow_html=True)
        
    render_checklist()

with col1:
    st.header("📹 Video Feed")
    video_file = st.file_uploader("Upload Video", type=['mp4', 'mov', 'avi'])
    
    if video_file is not None:
        # Save temp file for OpenCV
        tfile = tempfile.NamedTemporaryFile(delete=False) 
        tfile.write(video_file.read())
        video_path = tfile.name
        
        st.video(video_file)
        
        if st.button("Start Inspection"):
            st.session_state.is_processing = True
            
            # Setup Pipeline
            vp = VideoProcessor(video_path, extraction_fps=0.5) # Extract 1 frame every 2 seconds
            nim = NIMClient() # Make sure NIM_API_KEY is in your environment
            expected_actions = st.session_state.engine.get_expected_actions()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            current_frame_idx = 0
            while st.session_state.is_processing:
                frames_b64, next_idx = vp.extract_frames_base64(start_frame=current_frame_idx, num_frames=3)
                if not frames_b64:
                    st.success("Inspection Complete!")
                    st.session_state.is_processing = False
                    break
                    
                status_text.text(f"Analyzing video at frame {current_frame_idx}...")
                current_time_sec = current_frame_idx / vp.fps
                
                # Mock analysis for local testing without API key (uncomment to test offline)
                # detected_action = "None"
                # if 50 < current_frame_idx < 100: detected_action = expected_actions[0]
                # if 150 < current_frame_idx < 200: detected_action = expected_actions[2] # Simulate missed step 2
                
                # Real API call
                detected_action = nim.analyze_action(frames_b64, expected_actions)
                
                st.session_state.compliance_state = st.session_state.engine.update(detected_action, current_time_sec)
                
                # Update UI
                render_checklist()
                current_frame_idx = next_idx
                
                # Simple progress
                # Note: This is an estimation since we read sequentially.
                progress = min(current_frame_idx / vp.cap.get(7), 1.0) if vp.cap.get(7) > 0 else 0
                progress_bar.progress(progress)
                
            vp.release()
            os.unlink(video_path)
