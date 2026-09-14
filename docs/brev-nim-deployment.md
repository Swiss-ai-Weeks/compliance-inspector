# Deploying the Cosmos Reasoner NIM on a Brev RTX PRO 6000

Runbook for self-hosting the NVIDIA Cosmos Reasoner NIM that backs the Visual
Compliance Inspector, and for pointing `app.py` at it.

Target host: a Brev GPU instance with one **NVIDIA RTX PRO 6000 Blackwell**
(97 GB VRAM). The `nano` model size needs ~34 GB in BF16, so it fits with
generous headroom.

## 1. Prerequisites

| Requirement | Notes |
| --- | --- |
| NVIDIA driver + CUDA | Preinstalled on Brev GPU images. Verify with `nvidia-smi`. |
| Docker with GPU support | Preinstalled. Verify with `docker info \| grep -i runtime`. |
| **NGC Personal API Key** | Must be a *Personal API Key* with **Catalog** access (`https://org.ngc.nvidia.com/setup/personal-keys`). A legacy/other-type key authenticates to `nvcr.io` but fails later — see [Troubleshooting](#5-troubleshooting). |
| Free disk | ~60 GB for the image plus cached weights. |

### Dependency pin

`requirements.txt` pins `openai==1.14.3` but leaves `httpx` unpinned. Current
`httpx` (>= 0.28) removed the `proxies` argument that this `openai` release
passes, so a fresh install fails at client construction with:

```
TypeError: Client.__init__() got an unexpected keyword argument 'proxies'
```

Constrain `httpx` when installing:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt 'httpx<0.28'
```

(Adding `httpx<0.28` to `requirements.txt` would fix this at the source.)

Export the key once, in every shell that runs the commands below:

```bash
export NGC_API_KEY='nvapi-...'
```

## 2. Pull and start the NIM

```bash
# Authenticate to NVIDIA's registry. The username is the literal string
# $oauthtoken — quote it so the shell does not expand it.
echo "$NGC_API_KEY" | docker login nvcr.io --username '$oauthtoken' --password-stdin

# Persist downloaded weights across container restarts.
mkdir -p ~/nim-cache/cosmos3-reasoner

docker run -d --name cosmos3-reasoner \
  --gpus all --ipc host --shm-size=32GB \
  -e NGC_API_KEY \
  -e NIM_MODEL_SIZE=nano \
  -v ~/nim-cache/cosmos3-reasoner:/opt/nim/.cache \
  -p 8000:8000 \
  nvcr.io/nim/nvidia/cosmos3-reasoner:latest
```

One image serves every size; `NIM_MODEL_SIZE` selects which weights are
fetched. `nano` is the size this project targets.

The first start downloads tens of GB of weights and takes a while. Follow it:

```bash
docker logs -f cosmos3-reasoner
```

## 3. Verify

Wait for readiness, then confirm the served model id:

```bash
# Readiness — returns HTTP 200 once weights are loaded.
until curl -sf http://localhost:8000/v1/health/ready >/dev/null; do sleep 10; done
echo "NIM ready"

# The exact model id the NIM serves.
curl -s http://localhost:8000/v1/models | python3 -m json.tool
```

Smoke-test the OpenAI-compatible chat endpoint:

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
        "model": "nvidia/cosmos3-nano-reasoner",
        "messages": [{"role": "user", "content": "Reply with the word READY."}],
        "max_tokens": 16
      }' | python3 -m json.tool
```

## 4. Point the app at the NIM

`src/nim_client.py` reads three environment variables. Its built-in default
model id is `cosmos3-nano-reasoner`, **missing the `nvidia/` org prefix**, so
`NIM_MODEL` must be set explicitly or requests 404.

Neither `app.py` nor `src/nim_client.py` calls `load_dotenv()`, so a `.env`
file is not picked up on its own — export the values into the shell that
launches Streamlit:

```bash
export NIM_BASE_URL=http://localhost:8000/v1
export NIM_MODEL=nvidia/cosmos3-nano-reasoner
export NIM_API_KEY=not-needed     # self-hosted NIM ignores it; SDK needs non-empty

streamlit run app.py
```

See `.env.example` for the same values in file form.

On Brev, reach the UI by forwarding the Streamlit port from your workstation:

```bash
ssh -L 8501:localhost:8501 <brev-host>
```

### Test video

The repo ships no video (`*.mp4` is gitignored). The IKEA-Manuals-at-Work
assembly videos come from the Stanford Digital Repository, per that project's
README. A clip matching `sop.json` (a LAIVA shelf) can be fetched directly:

```bash
mkdir -p videos
curl -L -o videos/laiva_6FyfVUy2AMA.mp4 \
  "https://stacks.stanford.edu/file/druid:sg200ps4374/video/Shelf/laiva/6FyfVUy2AMA/6FyfVUy2AMA.mp4"
```

Upload it through the Streamlit file uploader and press **Start Inspection**.

## 5. Troubleshooting

**`400 Bad Request ... profile file maps`** on container start — the NGC key is
the wrong type. `docker login` succeeded (any valid key can pull the image),
but the container cannot resolve a model profile. Generate a **Personal API
Key** with **Catalog** access and retry.

**The checklist never advances and no error is shown** — most often
`NIM_MODEL` is missing the `nvidia/` prefix. `NIMClient.analyze_action` catches
every exception, prints to stderr and returns the string `"Error"`, which
`ComplianceEngine.update` treats as a no-op; the Streamlit UI therefore looks
idle rather than failing. Check the terminal running Streamlit for
`Error calling NIM: Error code: 404 ...`, and compare your `NIM_MODEL` against:

```bash
curl -s http://localhost:8000/v1/models
```

**Container exits immediately** — check `docker logs cosmos3-reasoner`. Out-of-
memory on a smaller GPU means `NIM_MODEL_SIZE=nano` is still too large for the
card; the RTX PRO 6000's 97 GB is ample.

**Weights re-download on every start** — the `-v ~/nim-cache/...` bind mount is
missing or not writable.
