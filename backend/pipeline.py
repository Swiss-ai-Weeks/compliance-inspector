"""Run the whole analysis: video + steps in, report out.

    chunker.cut  ->  detect.score_matrix  ->  align.align   ->  report.build
                     detect.state_transitions ----------------^

Used by the job runner (jobs.py) and by tools/evaluate.py, so the thing measured against
ground truth is exactly the thing the website runs.
"""

import json
import time
from pathlib import Path

import numpy as np

from . import align, chunker, config, detect, report


def analyze(video_path, sop: dict, out_dir, *, step_pages=None, pages_dir=None,
            furniture: str | None = None, progress=None, use_state: bool = True,
            recut: bool = False, mode: str | None = None, on_row=None,
            on_chunks=None) -> dict:
    """Analyse one video against one SOP. Writes artifacts into `out_dir`."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    furniture = furniture or sop.get("task_name", "product")

    def say(stage, done=None, total=None):
        if progress:
            progress(stage, done, total)

    t0 = time.time()
    steps = detect.load_steps(sop, step_pages, pages_dir)
    meta = chunker.probe(video_path)

    say("chunking")
    chunk_dir = out_dir / f"chunks_{int(config.CHUNK_SECONDS)}s_ov{int(config.CHUNK_OVERLAP)}_{config.CHUNK_HEIGHT}p"
    chunks = chunker.cut(video_path, chunk_dir, duration=meta["duration"], recut=recut)
    if on_chunks:
        on_chunks([c.as_dict() for c in chunks], meta["duration"])

    mode = mode or config.DETECT_MODE
    detector = detect.choice_matrix if mode == "choice" else detect.score_matrix
    say("scoring", 0, len(chunks) if mode == "choice" else len(chunks) * len(steps))
    scores, activities = detector(chunks, steps, furniture, on_row=on_row,
                                  progress=lambda d, t: say("scoring", d, t))

    say("aligning")
    from . import config
    if config.ALIGN_MODE == "greedy":
        spans = align.greedy_align(scores, chunks, [s["step_id"] for s in steps])
    else:
        spans = align.align(scores, chunks, [s["step_id"] for s in steps])

    state_times = {}
    if use_state:
        say("state", 0, len(steps))
        state_times = detect.state_transitions(
            video_path, steps, meta["duration"], out_dir / "frames", furniture,
            progress=lambda d, t: say("state", d, t))

    results = report.build(spans, steps, chunks, activities, state_times)
    summary = report.summarise(results)

    payload = {
        "video": str(video_path),
        "task_name": sop.get("task_name"),
        "model": config.NIM_MODEL,
        "detect_mode": mode,
        "duration": meta["duration"],
        "chunk_seconds": config.CHUNK_SECONDS,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "elapsed_s": round(time.time() - t0, 1),
        "summary": summary,
        "steps": [r.as_dict() for r in results],
        "chunks": [c.as_dict() for c in chunks],
    }

    (out_dir / "report.json").write_text(json.dumps(payload, indent=2))
    np.save(out_dir / "scores.npy", scores)
    say("done")
    return payload
