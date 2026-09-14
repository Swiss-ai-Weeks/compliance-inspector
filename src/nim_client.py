import os
from openai import OpenAI
from typing import List, Optional

class NIMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        """
        Initializes the NVIDIA Cosmos NIM client.
        NIMs often provide an OpenAI-compatible API.
        """
        self.api_key = api_key or os.environ.get("NIM_API_KEY", "dummy_key")
        self.base_url = base_url or os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.model = model or os.environ.get("NIM_MODEL", "cosmos3-nano-reasoner") # Updated model name
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    def analyze_action(self, frames_b64: List[str], expected_actions: List[str]) -> str:
        """
        Sends a sequence of frames to the multimodal NIM to identify the current action.
        """
        if not frames_b64:
            return "No frames to analyze."
            
        # Format the prompt
        actions_str = ", ".join([f"'{a}'" for a in expected_actions])
        system_prompt = (
            "You are an AI visual inspector analyzing a video feed of a worker. "
            "You will be given a sequence of frames representing the last few seconds of video. "
            f"Your task is to identify if the worker is currently performing any of the following actions: {actions_str}. "
            "Respond ONLY with the exact name of the action from the list if it is happening, "
            "or 'None' if they are doing something else or transitioning."
        )
        
        # Prepare the content with text and multiple images (if the NIM supports multi-image inputs)
        content = [{"type": "text", "text": system_prompt}]
        for b64 in frames_b64:
             content.append({
                 "type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
             })

        try:
            # Note: The exact structure might need tweaking based on the specific NIM documentation.
            # This follows standard OpenAI multimodal structure.
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=50,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling NIM: {e}")
            return "Error"
