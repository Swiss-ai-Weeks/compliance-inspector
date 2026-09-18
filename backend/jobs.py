"""Run jobs in the background and tell the browser how they are going.

Analysing a video takes minutes, far too long for one web request to wait on. So a job is
created and returned immediately, runs on a worker thread, and pushes events to anyone
subscribed. State is a JSON file per job under outputs/jobs/<id>/, so every artifact stays
inspectable and a restart does not lose finished work.

A job has two phases, with a deliberate pause between them:

    ingesting -> authoring -> awaiting_review  (a person checks the steps)  -> analyzing -> done
                                                                                      \\-> error

Preloaded products skip authoring: they already have a reviewed sop.json.
"""

import asyncio
import json
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import chunker, config, detect, ingest, pipeline, sop_author

INGESTING = "ingesting"
AUTHORING = "authoring"
AWAITING_REVIEW = "awaiting_review"
ANALYZING = "analyzing"
DONE = "done"
ERROR = "error"
IN_FLIGHT = {INGESTING, AUTHORING, ANALYZING}

JOBS_DIR = config.OUTPUTS_DIR / "jobs"


class JobStore:
    def __init__(self, max_workers: int = 2):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._subscribers: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}
        self._pool = ThreadPoolExecutor(max_workers, thread_name_prefix="job")
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_existing()

    # ---- persistence ---------------------------------------------------------------

    def _load_existing(self):
        for path in JOBS_DIR.glob("*/job.json"):
            try:
                job = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if job.get("status") in IN_FLIGHT:
                # Its worker thread died with the previous process.
                job["status"] = ERROR
                job["error"] = "Interrupted by a server restart. Start the analysis again."
            self._jobs[job["id"]] = job

    def _save(self, job: dict):
        path = self.dir(job["id"]) / "job.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(job, indent=2))
        tmp.replace(path)  # atomic, so a reader never sees half a file

    def dir(self, job_id: str) -> Path:
        return JOBS_DIR / job_id

    # ---- reads ---------------------------------------------------------------------

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return json.loads(json.dumps(job)) if job else None

    def list(self) -> list[dict]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j["created_at"], reverse=True)
            return [{k: j.get(k) for k in ("id", "created_at", "status", "product_name", "summary")}
                    for j in jobs]

    # ---- events --------------------------------------------------------------------

    def subscribe(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        with self._lock:
            self._subscribers.setdefault(job_id, set()).add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        with self._lock:
            subs = self._subscribers.get(job_id, set())
            for item in list(subs):
                if item[1] is queue:
                    subs.discard(item)

    def _publish(self, job_id: str, event: dict):
        with self._lock:
            subs = list(self._subscribers.get(job_id, ()))
        for loop, queue in subs:
            # Called from worker threads; the queue belongs to the server's event loop.
            loop.call_soon_threadsafe(_offer, queue, event)

    def _update(self, job_id: str, *, event: dict | None = None, **fields):
        with self._lock:
            job = self._jobs[job_id]
            job.update(fields)
            job["updated_at"] = time.time()
            self._save(job)
            status = job["status"]
        if "status" in fields:
            self._publish(job_id, {"type": "status", "status": status, "error": job.get("error")})
        if event:
            self._publish(job_id, event)

    # ---- phase 1: ingest + author --------------------------------------------------

    def create(self, *, video_url=None, manual_url=None, video_upload: Path | None = None,
               manual_upload: Path | None = None, product: str | None = None) -> dict:
        job_id = uuid.uuid4().hex[:12]
        jdir = self.dir(job_id)
        jdir.mkdir(parents=True, exist_ok=True)
        job = {
            "id": job_id, "created_at": time.time(), "updated_at": time.time(),
            "status": INGESTING, "error": None,
            "source": {"video_url": video_url, "manual_url": manual_url, "product": product,
                       "video_upload": bool(video_upload), "manual_upload": bool(manual_upload)},
            "product_name": None, "duration": None, "page_count": 0,
            "sop": None, "step_pages": {}, "author_model": None, "warnings": [],
            "progress": None, "chunks": [], "rows": {}, "report": None, "summary": None,
        }
        # Uploads were streamed to a temporary name; claim them before the request returns.
        if video_upload:
            shutil.move(video_upload, jdir / "video.mp4")
        if manual_upload:
            shutil.move(manual_upload, jdir / "manual.pdf")
        with self._lock:
            self._jobs[job_id] = job
            self._save(job)
        self._pool.submit(self._run_ingest, job_id)
        return self.get(job_id)

    def _run_ingest(self, job_id: str):
        try:
            job = self.get(job_id)
            src, jdir = job["source"], self.dir(job_id)
            video, manual = jdir / "video.mp4", jdir / "manual.pdf"

            if src["product"]:
                pdir = _product_dir(src["product"])
                product = json.loads((pdir / "product.json").read_text())
                first_video = sorted((pdir / "videos").glob("*.mp4"))[0]
                ingest.download(str(first_video), video, allow_local=True)
                ingest.download(str(pdir / product.get("manual", "manual.pdf")), manual, allow_local=True)
                self._update(job_id, product_name=product["name"])
            else:
                if not video.exists():
                    ingest.download(src["video_url"], video)
                if not manual.exists():
                    ingest.download(src["manual_url"], manual)

            meta = chunker.probe(video)  # fails fast on a file that is not a video
            pages = ingest.render_pdf_pages(manual, jdir / "pages")
            self._update(job_id, duration=meta["duration"], page_count=len(pages))

            if src["product"]:
                sop = _clean_sop(json.loads((pdir / "sop.json").read_text()))
                self._update(job_id, status=AWAITING_REVIEW, sop=sop,
                             step_pages={str(k): v for k, v in product.get("step_pages", {}).items()},
                             author_model="preloaded (hand-reviewed)")
                return

            self._update(job_id, status=AUTHORING, progress={"stage": "authoring", "done": 0,
                                                              "total": len(pages)})
            name = _guess_product_name(src)
            drafted = sop_author.author(
                manual, pages, name,
                progress=lambda d, t: self._update(
                    job_id, progress={"stage": "authoring", "done": d, "total": t},
                    event={"type": "progress", "stage": "authoring", "done": d, "total": t}))
            self._update(job_id, status=AWAITING_REVIEW, product_name=name, sop=drafted["sop"],
                         step_pages=drafted["step_pages"], author_model=drafted["author_model"],
                         warnings=drafted["warnings"], progress=None)
        except Exception as exc:
            self._fail(job_id, exc)

    # ---- phase 2: analyse ------------------------------------------------------------

    def start_analysis(self, job_id: str, sop: dict, step_pages: dict) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise KeyError(job_id)
            if job["status"] not in (AWAITING_REVIEW, DONE, ERROR) or job["sop"] is None:
                raise ValueError(f"Job is {job['status']}; wait until it is awaiting review, done or failed")
            self._update(job_id, status=ANALYZING, error=None, sop=sop, step_pages=step_pages,
                         chunks=[], rows={}, report=None, summary=None,
                         progress={"stage": "chunking", "done": 0, "total": 0})
        self._pool.submit(self._run_analysis, job_id)
        return self.get(job_id)

    def _run_analysis(self, job_id: str):
        try:
            job = self.get(job_id)
            jdir = self.dir(job_id)
            rows: dict[str, dict] = {}
            step_ids = [s["step_id"] for s in job["sop"]["expected_steps"]]

            def on_chunks(chunks, duration):
                self._update(job_id, chunks=chunks, duration=duration,
                             event={"type": "chunks", "chunks": chunks, "duration": duration})

            def on_row(ci, scores, activities):
                best = max(range(len(scores)), key=lambda i: scores[i]) if scores else None
                row = {"chunk": ci, "scores": scores,
                       "best_step": step_ids[best] if best is not None else None,
                       "best_score": scores[best] if best is not None else 0,
                       "activity": activities[best] if best is not None else ""}
                rows[str(ci)] = row
                with self._lock:
                    self._jobs[job_id]["rows"] = dict(rows)  # saved with the next progress update
                self._publish(job_id, {"type": "row", **row})

            def progress(stage, done, total):
                p = {"stage": stage, "done": done, "total": total}
                self._update(job_id, progress=p, event={"type": "progress", **p})

            result = pipeline.analyze(
                jdir / "video.mp4", job["sop"], jdir / "analysis",
                step_pages=job["step_pages"], pages_dir=jdir / "pages",
                furniture=job["product_name"], progress=progress,
                on_row=on_row, on_chunks=on_chunks)

            report = {k: result[k] for k in ("steps", "summary", "detect_mode", "model", "elapsed_s")}
            self._update(job_id, status=DONE, report=report, summary=result["summary"],
                         rows=rows, progress=None, event={"type": "report", "report": report})
        except Exception as exc:
            self._fail(job_id, exc)

    def _fail(self, job_id: str, exc: Exception):
        traceback.print_exc()
        self._update(job_id, status=ERROR, error=f"{type(exc).__name__}: {exc}", progress=None)


def _clean_sop(sop: dict) -> dict:
    """Strip leftover citation markers ("[cite: 3]") so people review clean text."""
    for step in sop.get("expected_steps", []):
        for key in ("name", "description", "completion_state"):
            if isinstance(step.get(key), str):
                step[key] = detect.strip_cites(step[key])
        step["visual_cues"] = [detect.strip_cites(c) for c in step.get("visual_cues", [])]
    return sop


def _offer(queue: asyncio.Queue, event: dict):
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        pass  # a stalled browser tab must not block the worker; it resyncs from the snapshot


def _product_dir(name: str) -> Path:
    # Only names from the products listing are valid: never let a request build a path.
    valid = {p.name for p in list_products_dirs()}
    if name not in valid:
        raise ValueError(f"Unknown product: {name}")
    return config.PRODUCTS_DIR / name


def list_products_dirs() -> list[Path]:
    if not config.PRODUCTS_DIR.is_dir():
        return []
    return sorted(p for p in config.PRODUCTS_DIR.iterdir()
                  if p.is_dir() and not p.name.startswith("_")
                  and (p / "product.json").exists() and (p / "sop.json").exists()
                  and any((p / "videos").glob("*.mp4")))


def list_products() -> list[dict]:
    out = []
    for p in list_products_dirs():
        product = json.loads((p / "product.json").read_text())
        sop = json.loads((p / "sop.json").read_text())
        video = sorted((p / "videos").glob("*.mp4"))[0]
        out.append({"id": p.name, "name": product["name"], "category": product.get("category"),
                    "steps": len(sop["expected_steps"]), "video": video.stem})
    return out


def _guess_product_name(src: dict) -> str:
    url = src.get("manual_url") or ""
    stem = Path(url.split("?")[0]).stem if url else ""
    return stem.replace("_", " ").replace("-", " ").strip() or "the product"
