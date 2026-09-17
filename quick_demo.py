import os
import cv2
import base64
import json
from openai import OpenAI

# 1. Load SOP rules
sop_path = "data/sops/sop_tjusig.json"
sop_text = ""
if os.path.exists(sop_path):
    with open(sop_path, "r") as f:
        sop_text = f.read()

# 2. Extract and downsample 8 frames from the compliant video
video_path = "data/videos/video_Bench_tjusig_full_compliant.mp4"
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    raise FileNotFoundError(f"Cannot open video at {video_path}")

total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
indices = [int(i * total_frames / 8) for i in range(8)]
image_contents = []

print(f"Sampling 8 frames from total {total_frames} frames...")
for idx in indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if ret:
        # Resize to 512x512 to prevent HTTP 413 / timeout errors
        frame = cv2.resize(frame, (512, 512))
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(buf).decode("utf-8")
        image_contents.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })
cap.release()

# 3. Call NVIDIA hosted inference endpoint
client = OpenAI(
    base_url=os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
    api_key=os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY")
)

prompt = (
    "You are an industrial assembly compliance inspector. "
    "Review these sequential frames from an assembly task against the standard operating procedure (SOP). "
    f"SOP Guidelines: {sop_text}\n\n"
    "State whether each required step is observed and determine if the final assembly is COMPLIANT or NON-COMPLIANT."
)

print("Sending reasoning payload to NVIDIA Cosmos...")
response = client.chat.completions.create(
    model=os.getenv("NIM_MODEL_NAME", "nvidia/cosmos3-nano-reasoner"),
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}] + image_contents
        }
    ],
    max_tokens=512,
    temperature=0.2
)

print("\n================ COMPLIANCE AUDIT REPORT ================\n")
print(response.choices[0].message.content)
print("\n=========================================================\n")