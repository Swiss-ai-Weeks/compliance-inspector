# Codebase Map

The top-level areas and what each holds. A map to navigate, not the full tree.

| Path | Holds |
| --- | --- |
| `backend/` | FastAPI app and the analysis pipeline, one responsibility per file (see below) |
| `frontend/` | React + Vite app. `npm run build` emits into `backend/static/` |
| `tools/evaluate.py` | scores the pipeline against human timestamps; the accuracy gate |
| `products/` | demo inputs: steps, manual PDF, ground truth. Videos gitignored |
| `outputs/` | generated: jobs, clips, reports, eval runs. Gitignored, safe to delete |
| `docs/` | NIM deployment runbook |
| `Dockerfile`, `docker-compose.yml` | app image, and app + NIM stack |
| `app.py`, `src/` | legacy Streamlit starter, superseded |
| `aidd_docs/` | this memory bank |

## backend/

| File | In => out |
| --- | --- |
| `main.py` | HTTP routes, uploads, media with Range support, serves the built UI |
| `jobs.py` | job lifecycle, persistence, SSE pub/sub |
| `ingest.py` | URLs/uploads => files on disk, PDF => page PNGs. Owns the public-URL check |
| `sop_author.py` | page PNGs => draft `sop.json` + `step_pages` |
| `chunker.py` | video => overlapping clips; single frames |
| `cosmos.py` | the only NIM client: media encoding, guided JSON, retries |
| `detect.py` | clips x steps => score grid; frames => state transition times |
| `align.py` | score grid => one span per step (monotone DP) |
| `report.py` | spans + state times => statuses, coverage, compliance |
| `pipeline.py` | runs chunker => detect => align => report; shared by jobs and the evaluator |
| `config.py` | all environment settings |

## Entry points

| Entry | Command |
| --- | --- |
| Web app | `uvicorn backend.main:app --port 8080` |
| Frontend dev | `cd frontend && npm run dev` |
| Evaluation | `python -m tools.evaluate bench_tjusig [--mode grid\|choice] [--no-state] [--reuse]` |
