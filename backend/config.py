"""Settings, read from the environment once at import.

Two different models are used for two different jobs:

* VIDEO_MODEL  - the local Cosmos NIM, which watches video clips.
* AUTHOR_MODEL - a hosted NVIDIA NIM, which reads the manual PDF and writes the step list.

They can point at the same endpoint; they usually do not.
"""

import os
from pathlib import Path

# ---- Cosmos NIM: watches the video ------------------------------------------------
NIM_BASE_URL = os.environ.get("NIM_BASE_URL", "http://localhost:8000/v1")
NIM_MODEL = os.environ.get("NIM_MODEL", "nvidia/cosmos3-nano-reasoner")
NIM_API_KEY = os.environ.get("NIM_API_KEY", "not-needed")

# ---- Hosted NIM: reads the manual -------------------------------------------------
# Falls back to the video NIM so the app still runs with no hosted key; sop_author
# reports the degraded quality rather than failing.
AUTHOR_BASE_URL = os.environ.get("AUTHOR_BASE_URL", "https://integrate.api.nvidia.com/v1")
AUTHOR_MODEL = os.environ.get("AUTHOR_MODEL", "meta/llama-3.2-90b-vision-instruct")
AUTHOR_API_KEY = os.environ.get("AUTHOR_API_KEY", os.environ.get("NVIDIA_API_KEY", ""))
HAVE_AUTHOR_KEY = bool(AUTHOR_API_KEY)

# ---- Chunking ---------------------------------------------------------------------
# CHUNK_SECONDS/CHUNK_OVERLAP also set the timestamp resolution: a chunk starts every
# (CHUNK_SECONDS - CHUNK_OVERLAP) seconds, so predicted times land on that grid.
CHUNK_SECONDS = float(os.environ.get("CHUNK_SECONDS", 10))
CHUNK_OVERLAP = float(os.environ.get("CHUNK_OVERLAP", 2))
CHUNK_HEIGHT = int(os.environ.get("CHUNK_HEIGHT", 480))

# ---- Detection / alignment --------------------------------------------------------
# "choice": one forced-choice question per chunk (which step is this?).
# "grid":   one independent 0-10 question per chunk x step.
DETECT_MODE = os.environ.get("DETECT_MODE", "grid")
MAX_PARALLEL_REQUESTS = int(os.environ.get("MAX_PARALLEL_REQUESTS", 16))
# Score below which a chunk is better explained as "nothing relevant happening".
IDLE_SCORE = float(os.environ.get("IDLE_SCORE", 4.0))
# Cost of declaring a step skipped, in the same units as the 0-10 scores.
SKIP_PENALTY = float(os.environ.get("SKIP_PENALTY", 6.0))
# A step needs at least this aligned score to count as observed at all.
MIN_STEP_SCORE = float(os.environ.get("MIN_STEP_SCORE", 5.0))
# A step the staircase could not place is reported out-of-order only if some clip shows it at
# least this strongly. Kept well above MIN_STEP_SCORE: a yes-biased model gives almost every
# step a middling score somewhere, and those must read as "not seen", not "out of order".
OUT_OF_ORDER_SCORE = float(os.environ.get("OUT_OF_ORDER_SCORE", 8.0))

# ---- Paths ------------------------------------------------------------------------
REPO_DIR = Path(__file__).resolve().parent.parent
PRODUCTS_DIR = Path(os.environ.get("PRODUCTS_DIR", REPO_DIR / "products"))
OUTPUTS_DIR = Path(os.environ.get("OUTPUTS_DIR", REPO_DIR / "outputs"))
STATIC_DIR = Path(os.environ.get("STATIC_DIR", REPO_DIR / "backend" / "static"))
ALIGN_MODE = os.environ.get("ALIGN_MODE", "global")
