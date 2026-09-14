import cv2
import base64
import os
from typing import List, Tuple

class VideoProcessor:
    def __init__(self, video_path: str, extraction_fps: float = 1.0):
        """
        Initializes the Video Processor.
        :param video_path: Path to the video file.
        :param extraction_fps: Frames to extract per second of video.
        """
        self.video_path = video_path
        self.extraction_fps = extraction_fps
        self.cap = cv2.VideoCapture(video_path)
        
        if not self.cap.isOpened():
            raise ValueError(f"Error opening video file: {video_path}")
            
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
             self.fps = 30.0 # Fallback
             
        # Calculate how many original frames to skip to match extraction_fps
        self.frame_skip = int(self.fps / self.extraction_fps)
        if self.frame_skip == 0:
            self.frame_skip = 1

    def extract_frames_base64(self, start_frame: int = 0, num_frames: int = 5) -> Tuple[List[str], int]:
        """
        Extracts a sequence of frames and encodes them as base64.
        Useful for sending to multimodal LLMs.
        Returns a tuple of (list of base64 strings, next_frame_index).
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        frames_b64 = []
        current_frame = start_frame
        extracted_count = 0
        
        while extracted_count < num_frames:
            ret, frame = self.cap.read()
            if not ret:
                break # End of video
                
            # Only keep frames based on our extraction_fps
            if current_frame % self.frame_skip == 0:
                # Resize to save bandwidth (e.g., 512x512 max)
                frame_resized = self._resize_frame(frame, max_dim=512)
                _, buffer = cv2.imencode('.jpg', frame_resized)
                b64_str = base64.b64encode(buffer).decode('utf-8')
                frames_b64.append(b64_str)
                extracted_count += 1
                
            current_frame += 1
            
        return frames_b64, current_frame

    def _resize_frame(self, frame, max_dim=512):
        h, w = frame.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            return cv2.resize(frame, (new_w, new_h))
        return frame
        
    def release(self):
        self.cap.release()
