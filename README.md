# Visual Compliance Inspector

![Enterprise Ready](https://img.shields.io/badge/Enterprise-Ready-blue) ![NVIDIA NIM](https://img.shields.io/badge/Powered%20by-NVIDIA%20Cosmos%20NIM-76B900)

**Visual Compliance Inspector** is an AI-powered system that validates manual assembly processes on factory floors against their official Standard Operating Procedures (SOPs).

Built for the **Swiss AI Weeks Hackathon**, this project solves the scalability challenge of manual QA inspection by automatically generating a compliance timeline from raw video feeds and PDF procedures.

## 🚀 Key Features

### 🎥 Watch the Demo
<video src="./WebDemo.mp4" width="100%" controls></video>

* **AI Video Understanding:** Leverages **NVIDIA Cosmos NIM** (`cosmos3-nano-reasoner`) to understand complex manual assembly actions in 10-second sliding windows.
* **Dual Alignment Engines:** 
  * **Global Audit (Grid Mode):** Uses dynamic programming to guarantee a mathematically perfect offline timeline across the entire video.
  * **Live Copilot (Greedy Mode):** Simulates real-time edge processing with a rigid sliding window, blocking AI hallucinations on the fly.
* **Enterprise Ready (Privacy First):** Designed for local GPU inference. Sensitive industrial videos never have to leave the factory floor.
* **Modular Architecture:** Clear separation between video processing, AI reasoning, and the timeline frontend.

## 🧠 How it Works

Instead of naive frame-by-frame matching (which fails due to human unpredictability), the system uses **Dynamic Timeline Alignment**:
1. **Extract:** Parses the SOP PDF to extract expected steps and states.
2. **Chunk:** Splits the raw assembly video into overlapping 10-second clips.
3. **Score:** NVIDIA Cosmos NIM analyzes each clip against the expected SOP actions.
4. **Align:** The mathematical engine filters out noise and builds a chronological compliance timeline.
5. **Render:** The React frontend visualizes precisely which steps were verified, missed, or performed out of order.

## 🛠️ Installation

### Prerequisites
* Python 3.10+
* Node.js & npm (for frontend)
* NVIDIA API Key (for Cosmos NIM)

### Backend Setup
1. Clone the repository and navigate to the root directory.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### Frontend Setup
```powershell
cd frontend
npm install
```

## ⚙️ Usage

### 1. Configure Environment Variables
You can configure the backend by setting environment variables in your terminal before launching:

```powershell
# NVIDIA NIM Settings
$env:NIM_BASE_URL="http://localhost:8000/v1"
$env:NIM_MODEL="nvidia/cosmos3-nano-reasoner"
$env:NIM_API_KEY="your-nvidia-api-key"
$env:AUTHOR_API_KEY="your-nvidia-api-key"

# Alignment Engine Configuration
# "grid" for Global Audit (Perfect offline sync)
# "choice" for Live Copilot (Real-time sliding window)
$env:DETECT_MODE="grid" 
$env:ALIGN_MODE="global" # or "greedy" for real-time
```

### 2. Launch the Application

**Start the Backend:**
```powershell
# Ensure your virtual environment is active
uvicorn backend.main:app --reload --port 8080
```

**Start the Frontend (in a new terminal):**
```powershell
cd frontend
npm run dev
```

## 🔮 Roadmap
While the current implementation uses the `cosmos3-nano` model to prove the architecture, the pipeline is fully ready to scale. With a production-grade vision model and robust document understanding, this architecture can bridge the gap between physical factory operations and digital compliance systems.

---
*Created for the Swiss AI Weeks Hackathon.*
