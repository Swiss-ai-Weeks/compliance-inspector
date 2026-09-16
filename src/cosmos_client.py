# NVIDIA Cosmos NIM Inference Client

import os
import json
from openai import OpenAI

NIM_BASE_URL = os.getenv("NIM_BASE_URL", "http://localhost:8000/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY") or os.getenv("NGC_API_KEY")
MODEL_NAME = os.getenv("NIM_MODEL_NAME", "nvidia/cosmos3-nano-reasoner")

client = OpenAI(base_url=NIM_BASE_URL, api_key=NVIDIA_API_KEY)


def analyze_actions(frames: list[dict], sop_data: dict) -> dict:
    """
    Dispatches extracted frames and SOP rules to Cosmos NIM.
    Returns detected action intervals.
    """
    system_prompt = (
        "You are an industrial compliance inspector. Examine the sequential video frames "
        "sampled at 1-second intervals and detect whether standard operating procedure (SOP) "
        "steps took place, and at what timestamps.\n\n"
        "Rules:\n"
        "1. Only set detected=true if visual evidence confirms the step was completed.\n"
        "2. Accurately estimate start_sec and end_sec.\n"
        "3. Adhere strictly to the requested JSON schema."
    )

    user_prompt = (
        f"SOP Checklist:\n{json.dumps(sop_data, indent=2)}\n\n"
        "Analyze the attached frames and return strictly JSON adhering to:\n"
        "{\n"
        '  "observed_actions": [\n'
        "    {\n"
        '      "step_id": 1,\n'
        '      "detected": true,\n'
        '      "start_sec": 4,\n'
        '      "end_sec": 18,\n'
        '      "visual_evidence": "Operator inserts dowel"\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    content_payload = [{"type": "text", "text": user_prompt}]
    for item in frames:
        content_payload.append({
            "type": "text",
            "text": f"[Frame Timestamp: {item['timestamp_sec']}s]"
        })
        content_payload.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{item['base64']}",
                "detail": "low"
            }
        })

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_payload}
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)