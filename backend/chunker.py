"""Cut a video into short overlapping clips.

This is where timestamps come from. With CHUNK_SECONDS=10 and CHUNK_OVERLAP=2 a chunk
starts every 8 s (0-10, 8-18, 16-26, ...), so predicted times are accurate to about 8 s.

Ported from compliance_check.ipynb cell 11.
"""

import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import imageio_ffmpeg

from . import config

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


@dataclass
class Chunk:
    index: int
    start: float
    end: float
    path: str

    @property
    def label(self) -> str:
        return f"{mmss(self.start)}-{mmss(self.end)}"

    def as_dict(self) -> dict:
        return {**asdict(self), "label": self.label}


def mmss(seconds) -> str:
    """83.5 -> '01:23'. Returns '-' for missing values so tables stay readable."""
    if seconds is None:
        return "-"
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def probe(video_path) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    meta = {
        "fps": fps,
        "duration": frames / fps if fps else 0.0,
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    return meta


def windows(duration: float, chunk_seconds: float, overlap: float) -> list[tuple[float, float]]:
    stride = chunk_seconds - overlap
    out, start = [], 0.0
    while start < duration:
        end = min(start + chunk_seconds, duration)
        if end - start >= 2 or not out:  # skip a uselessly short tail
            out.append((start, end))
        if end >= duration:
            break
        start += stride
    return out


def cut(video_path, chunk_dir, *, duration=None, chunk_seconds=None, overlap=None,
        height=None, recut=False) -> list[Chunk]:
    """Cut `video_path` into clips under `chunk_dir`. Existing clips are reused."""
    chunk_seconds = chunk_seconds or config.CHUNK_SECONDS
    overlap = overlap if overlap is not None else config.CHUNK_OVERLAP
    height = height or config.CHUNK_HEIGHT

    chunk_dir = Path(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    if duration is None:
        duration = probe(video_path)["duration"]

    chunks = []
    for i, (start, end) in enumerate(windows(duration, chunk_seconds, overlap)):
        out = chunk_dir / f"chunk_{i:03d}_{int(start):04d}s-{int(end):04d}s.mp4"
        if recut or not out.exists():
            # Re-encoded (not stream-copied) so the clip starts exactly at its timestamp.
            subprocess.run(
                [FFMPEG, "-y", "-loglevel", "error",
                 "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}",
                 "-i", str(video_path), "-vf", f"scale=-2:{height}", "-an",
                 "-c:v", "libx264", "-preset", "veryfast", str(out)],
                check=True,
            )
        chunks.append(Chunk(index=i, start=start, end=end, path=str(out)))
    return chunks


def frame_at(video_path, seconds: float, out_path) -> Path:
    """Grab a single frame, used by the object-state probes in detect.py."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.exists():
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f"Could not read frame at {seconds}s of {video_path}")
        cv2.imwrite(str(out_path), frame)
    return out_path
