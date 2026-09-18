"""The web server: routes requests to the job store, serves media and the built frontend.

    uvicorn backend.main:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sse_starlette.sse import EventSourceResponse

from . import config, cosmos, jobs

MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024
UPLOAD_DIR = jobs.JOBS_DIR / "_uploads"

app = FastAPI(title="Visual Compliance Inspector")
store = jobs.JobStore()


# ---- health + products ---------------------------------------------------------------

@app.get("/api/health")
def health():
    try:
        models = cosmos.served_models(cosmos.video_client().with_options(timeout=5, max_retries=0))
        nim = {"ok": config.NIM_MODEL in models, "models": models}
    except Exception as exc:
        nim = {"ok": False, "error": str(exc)}
    return {"nim": nim, "video_model": config.NIM_MODEL, "detect_mode": config.DETECT_MODE,
            "author_model": config.AUTHOR_MODEL if config.HAVE_AUTHOR_KEY else None,
            "author_hosted": config.HAVE_AUTHOR_KEY}


@app.get("/api/products")
def products():
    return jobs.list_products()


# ---- jobs ------------------------------------------------------------------------------

async def _save_upload(upload: UploadFile | None, suffix: str) -> Path | None:
    if upload is None or not upload.filename:
        return None
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=suffix)
    written = 0
    with open(fd, "wb") as fh:
        while block := await upload.read(1 << 20):
            written += len(block)
            if written > MAX_UPLOAD_BYTES:
                fh.close()
                Path(name).unlink(missing_ok=True)
                raise HTTPException(413, "Upload too large")
            fh.write(block)
    return Path(name)


@app.post("/api/jobs")
async def create_job(
    product: str | None = Form(None),
    video_url: str | None = Form(None),
    manual_url: str | None = Form(None),
    video_file: UploadFile | None = File(None),
    manual_file: UploadFile | None = File(None),
):
    if product:
        try:
            jobs._product_dir(product)
        except ValueError as exc:
            raise HTTPException(404, str(exc))
        return store.create(product=product)

    has_video = bool(video_url) or bool(video_file and video_file.filename)
    has_manual = bool(manual_url) or bool(manual_file and manual_file.filename)
    if not (has_video and has_manual):
        raise HTTPException(422, "Provide a video (URL or file) and a manual PDF (URL or file)")

    # Reject private or malformed URLs now, rather than failing silently in the background.
    from .ingest import check_public_url
    for url in (video_url, manual_url):
        if url:
            try:
                check_public_url(url)
            except ValueError as exc:
                raise HTTPException(422, str(exc))

    video_path = await _save_upload(video_file, ".mp4")
    manual_path = await _save_upload(manual_file, ".pdf")
    if manual_path and manual_path.read_bytes()[:5] != b"%PDF-":
        manual_path.unlink(missing_ok=True)
        if video_path:
            video_path.unlink(missing_ok=True)
        raise HTTPException(422, "The manual upload is not a PDF")

    return store.create(video_url=None if video_path else video_url,
                        manual_url=None if manual_path else manual_url,
                        video_upload=video_path, manual_upload=manual_path)


@app.get("/api/jobs")
def list_jobs():
    return store.list()


def _job_or_404(job_id: str) -> dict:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return job


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _job_or_404(job_id)


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    _job_or_404(job_id)
    queue = store.subscribe(job_id)

    async def stream():
        try:
            # Subscribe first, then snapshot: nothing that happens in between is missed, and
            # a late or reconnecting browser starts from the complete current state.
            yield {"event": "message", "data": json.dumps({"type": "snapshot", "job": store.get(job_id)})}
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    continue  # sse-starlette sends its own keep-alive pings
                yield {"event": "message", "data": json.dumps(event)}
        finally:
            store.unsubscribe(job_id, queue)

    return EventSourceResponse(stream(), ping=15)


class StepIn(BaseModel):
    step_id: int = Field(ge=1, le=999)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    visual_cues: list[str] = Field(default_factory=list, max_length=12)
    completion_state: str = Field("", max_length=500)
    state_is_monotone: bool = True
    manual_reference: str | None = None


class SopIn(BaseModel):
    task_name: str = Field("", max_length=200)
    expected_steps: list[StepIn] = Field(min_length=1, max_length=200)
    step_pages: dict[str, int] = Field(default_factory=dict)

    @field_validator("expected_steps")
    @classmethod
    def unique_ids(cls, steps):
        ids = [s.step_id for s in steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step_id values must be unique")
        return steps


@app.get("/api/jobs/{job_id}/sop")
def get_sop(job_id: str):
    job = _job_or_404(job_id)
    return {"sop": job["sop"], "step_pages": job["step_pages"], "author_model": job["author_model"],
            "warnings": job["warnings"], "page_count": job["page_count"]}


@app.put("/api/jobs/{job_id}/sop")
def confirm_sop(job_id: str, body: SopIn):
    """Save the reviewed steps and start the analysis."""
    job = _job_or_404(job_id)
    pages = {k: v for k, v in body.step_pages.items() if 1 <= v <= max(job["page_count"], 1)}
    sop = {"task_name": body.task_name or (job["sop"] or {}).get("task_name", ""),
           "total_manual_steps": len(body.expected_steps),
           "expected_steps": [s.model_dump() for s in body.expected_steps]}
    try:
        return store.start_analysis(job_id, sop, pages)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


# ---- media -----------------------------------------------------------------------------

@app.get("/api/jobs/{job_id}/media/video")
def job_video(job_id: str):
    _job_or_404(job_id)
    path = store.dir(job_id) / "video.mp4"
    if not path.exists():
        raise HTTPException(404, "Video not downloaded yet")
    return FileResponse(path, media_type="video/mp4")  # supports Range, so the player can seek


@app.get("/api/jobs/{job_id}/media/page/{number}")
def job_page(job_id: str, number: int):
    job = _job_or_404(job_id)
    if not 1 <= number <= job["page_count"]:
        raise HTTPException(404, "No such page")
    return FileResponse(store.dir(job_id) / "pages" / f"page_{number:02d}.png", media_type="image/png")


# ---- frontend --------------------------------------------------------------------------

if config.STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=config.STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        # Client-side routes all serve the app shell; real files are served as themselves.
        candidate = (config.STATIC_DIR / path).resolve()
        if path and candidate.is_file() and config.STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(config.STATIC_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_frontend():
        return JSONResponse({"detail": "Frontend not built. Run `npm run build` in frontend/."})
