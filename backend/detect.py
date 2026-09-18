"""Ask Cosmos about the video, and turn the answers into numbers.

Two independent signals come out of this module:

* `score_matrix()` - "how strongly does clip C show step K?", for every C and K.
  A grid of 0-10 scores. This is the ACTION signal. align.py turns it into a verdict.

* `state_transitions()` - "is step K's completion state visible yet?", asked on frames
  sampled across the video and fitted to one switch-point. This is the STATE signal, and it
  is independent of the grid.

Why scores rather than the notebook's booleans: measured on the two ground-truth videos,
cosmos3-nano answers "yes" to most step/chunk pairs (precision 0.2-0.35, recall 0.04-0.2,
and bench_applaro scored a perfect 100% because the model never said no). A boolean throws
away the only information that distinguishes a strong match from a shrug; a score keeps it.
choice_matrix() goes further and makes the model compare steps against each other.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from . import chunker, config, cosmos

_CITE_RE = re.compile(r"\s*\[cite:[^\]]*\]")

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "activity": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 10},
    },
    "required": ["activity", "score"],
}

STATE_SCHEMA = {
    "type": "object",
    "properties": {"state_true": {"type": "boolean"}},
    "required": ["state_true"],
}


def strip_cites(text: str) -> str:
    return _CITE_RE.sub("", text or "").strip()


def load_steps(sop: dict, step_pages: dict | None = None, pages_dir=None) -> list[dict]:
    """Normalise sop.json into the shape the rest of the pipeline uses.

    Attaches each step's manual drawing when product.json maps it to a PDF page, so the
    model gets both words and a picture. Ported from compliance_check.ipynb cell 7.
    """
    step_pages = {int(k): v for k, v in (step_pages or {}).items()}
    steps = []
    for s in sop["expected_steps"]:
        page = step_pages.get(s["step_id"])
        steps.append({
            "step_id": s["step_id"],
            "name": strip_cites(s.get("name", "")),
            "description": strip_cites(s.get("description", "")),
            "visual_cues": [strip_cites(c) for c in s.get("visual_cues", [])],
            "completion_state": strip_cites(s.get("completion_state", "")),
            "state_is_monotone": s.get("state_is_monotone", True),
            "image": str(Path(pages_dir) / f"page_{page:02d}.png") if page and pages_dir else None,
        })
    return steps


def describe(step: dict) -> str:
    return (f"Step {step['step_id']} - {step['name']}: {step['description']} "
            f"Visual cues: {'; '.join(step['visual_cues'])}.")


# ---------------------------------------------------------------------------------
# Signal 1: the action score grid
# ---------------------------------------------------------------------------------

def _score_prompt(step: dict, furniture: str) -> str:
    return "\n".join([
        f"The clip shows part of someone assembling an IKEA {furniture}. Real parts look different "
        "from the black-and-white manual drawings. Any attached manual page contains the drawing for "
        f"step {step['step_id']} - look at the drawing next to that bold step number.",
        f"STEP BEING ASKED ABOUT: {describe(step)}",
        "Rate how strongly THIS clip shows THIS SPECIFIC step, 0-10:",
        "  0-2  = a different step, an intro shot, talking, or a finished-product shot",
        "  3-5  = general assembly of this product, but not clearly this step",
        "  6-8  = this step is probably being performed",
        "  9-10 = this step is unmistakably being performed",
        "Most clips show some OTHER step, so most answers should be low. Reserve 6 and above "
        "for the specific parts and motions named in the visual cues. Also give `activity`: "
        "one sentence describing what the person actually does in the clip.",
    ])


def score_matrix(chunks, steps, furniture: str, *, progress=None, on_row=None,
                 max_parallel: int | None = None) -> tuple[np.ndarray, list[list[str]]]:
    """Score every (chunk, step) pair. Returns (scores, activities), both n_chunks x n_steps.

    `on_row(chunk_index, row_scores, row_activities)` fires as each chunk's row completes, in
    time order, so the UI can fill the timeline while the rest of the grid is still running.
    """
    max_parallel = max_parallel or config.MAX_PARALLEL_REQUESTS
    n_c, n_s = len(chunks), len(steps)
    scores = np.zeros((n_c, n_s), dtype=float)
    activities = [["" for _ in range(n_s)] for _ in range(n_c)]

    def one(job):
        ci, si = job
        chunk, step = chunks[ci], steps[si]
        try:
            ans = cosmos.ask(
                _score_prompt(step, furniture),
                images=[step["image"]] if step["image"] else [],
                video=chunk.path,
                schema=SCORE_SCHEMA,
                max_tokens=200,
            )
            return ci, si, float(ans["score"]), ans.get("activity", "")
        except Exception as exc:
            # One dead cell must not kill a 260-call run; alignment tolerates a zero.
            return ci, si, 0.0, f"(error: {exc})"

    jobs = [(ci, si) for ci in range(n_c) for si in range(n_s)]
    done = 0
    with ThreadPoolExecutor(max_parallel) as pool:
        for ci, si, score, activity in pool.map(one, jobs):
            scores[ci, si] = score
            activities[ci][si] = activity
            done += 1
            if progress and done % 10 == 0:
                progress(done, len(jobs))
            if on_row and si == n_s - 1:
                on_row(ci, scores[ci].tolist(), activities[ci])
    return scores, activities


def _choice_prompt(steps: list[dict], furniture: str) -> str:
    listing = "\n".join(f"  {s['step_id']}: {s['name']} - {s['description']}" for s in steps)
    return "\n".join([
        f"The clip shows part of someone assembling an IKEA {furniture}. These are the assembly "
        "steps from the manual:",
        listing,
        "  0: none of these - intro shot, talking, unpacking, or showing the finished product",
        "Which ONE step is being performed in this clip? Compare the steps against each other and "
        "pick the one whose specific parts and motions you actually see. Give `step_id`, "
        "`confidence` 0-10 for that choice, and `activity`: one sentence describing what the "
        "person does.",
    ])


def choice_matrix(chunks, steps, furniture: str, *, progress=None, on_row=None,
                  max_parallel: int | None = None) -> tuple[np.ndarray, list[list[str]]]:
    """One forced-choice question per chunk: "which of these steps is this clip?"

    Asking about each step in isolation lets a weak model answer "sort of, 3" to every step,
    which leaves whole rows of the grid carrying no information. Making it pick one forces a
    comparison between steps - the discrimination the task actually needs - and costs one
    call per chunk instead of one per chunk x step.

    Returns the same (scores, activities) shape as score_matrix, so align.py is unchanged:
    the chosen step gets the confidence, every other step in that row gets 0.
    """
    max_parallel = max_parallel or config.MAX_PARALLEL_REQUESTS
    ids = [s["step_id"] for s in steps]
    schema = {
        "type": "object",
        "properties": {
            "activity": {"type": "string"},
            "step_id": {"type": "integer", "enum": [0, *ids]},
            "confidence": {"type": "integer", "minimum": 0, "maximum": 10},
        },
        "required": ["activity", "step_id", "confidence"],
    }
    prompt = _choice_prompt(steps, furniture)
    scores = np.zeros((len(chunks), len(steps)), dtype=float)
    activities = [["" for _ in steps] for _ in chunks]

    def one(ci):
        try:
            ans = cosmos.ask(prompt, video=chunks[ci].path, schema=schema, max_tokens=200)
            return ci, int(ans["step_id"]), float(ans["confidence"]), ans.get("activity", "")
        except Exception as exc:
            return ci, 0, 0.0, f"(error: {exc})"

    with ThreadPoolExecutor(max_parallel) as pool:
        for n, (ci, sid, conf, activity) in enumerate(pool.map(one, range(len(chunks))), 1):
            if sid in ids:
                si = ids.index(sid)
                scores[ci, si] = conf
                activities[ci][si] = activity
            if progress:
                progress(n, len(chunks))
            if on_row:
                on_row(ci, scores[ci].tolist(), activities[ci])
    return scores, activities


# ---------------------------------------------------------------------------------
# Signal 2: object-state transitions
# ---------------------------------------------------------------------------------

def _state_prompt(step: dict, furniture: str) -> str:
    return (
        f"This is a still frame from an IKEA {furniture} assembly. Look only at the object, "
        "not at what the person is doing.\n"
        f"QUESTION: {step['completion_state']}\n"
        "Answer state_true = true only if that is clearly visible in this frame. If the object "
        "is hidden, out of frame or you cannot tell, answer false."
    )


def sample_times(video_path, duration: float, frames_dir, samples: int = 16) -> list[tuple[float, Path]]:
    """Evenly spaced frames across the video, with blank ones dropped.

    Edited videos routinely open or close on black frames and title cards. A blank frame
    answers "no" to every state question, which is noise the transition fit should not see.
    """
    import cv2

    out = []
    for i in range(samples):
        t = duration * (i + 0.5) / samples
        path = chunker.frame_at(video_path, t, Path(frames_dir) / f"t{int(t * 10):06d}.png")
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is not None and img.std() > 8:  # near-uniform frame: black, white, fade
            out.append((t, path))
    return out


def fit_transition(times: list[float], answers: list[bool], min_support: int = 2) -> float | None:
    """Best single switch-point: false before, true after.

    Chooses the split that disagrees with the fewest answers, so one wrong answer costs one
    disagreement instead of derailing the result the way it would derail a binary search.
    "Never became true" is always a candidate, and wins ties, so the fit only claims a
    transition when the answers actually support one.
    """
    n = len(answers)
    if n == 0:
        return None
    trues_before = [0] * (n + 1)
    for i, a in enumerate(answers):
        trues_before[i + 1] = trues_before[i] + a
    total_true = trues_before[n]

    best_i, best_cost = n, total_true  # split at n = never became true
    for i in range(n):
        falses_after = (n - i) - (total_true - trues_before[i])
        cost = trues_before[i] + falses_after
        if cost < best_cost:
            best_i, best_cost = i, cost

    if best_i == n or sum(answers[best_i:]) < min_support:
        return None
    return times[best_i]


def state_transitions(video_path, steps, duration: float, frames_dir, furniture: str,
                      *, progress=None, max_parallel: int | None = None,
                      samples: int = 16) -> dict[int, float | None]:
    """When does each step's completion state first hold? Returns {step_id: seconds or None}.

    Every monotone step's question is asked on the same sampled frames, then each step's
    answers are fitted to a single false-to-true switch. Steps whose state is not monotone
    (e.g. the cardboard template goes on, then comes off) are skipped: a switch-point fit
    would report nonsense for them, so they rely on the action signal alone.
    """
    max_parallel = max_parallel or config.MAX_PARALLEL_REQUESTS
    frames = sample_times(video_path, duration, frames_dir, samples)
    usable = [s for s in steps if s["completion_state"] and s["state_is_monotone"]]
    out = {s["step_id"]: None for s in steps}
    if not frames or not usable:
        return out

    def one(job):
        si, fi = job
        try:
            ans = cosmos.ask(_state_prompt(usable[si], furniture), images=[frames[fi][1]],
                             schema=STATE_SCHEMA, max_tokens=30)
            return si, fi, bool(ans["state_true"])
        except Exception:
            return si, fi, False

    answers = [[False] * len(frames) for _ in usable]
    jobs = [(si, fi) for si in range(len(usable)) for fi in range(len(frames))]
    with ThreadPoolExecutor(max_parallel) as pool:
        for n, (si, fi, val) in enumerate(pool.map(one, jobs), 1):
            answers[si][fi] = val
            if progress and n % 10 == 0:
                progress(n, len(jobs))

    times = [t for t, _ in frames]
    for si, step in enumerate(usable):
        out[step["step_id"]] = fit_transition(times, answers[si])
    return out
