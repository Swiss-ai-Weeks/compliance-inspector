"""Turn the alignment and the state probes into the thing a person reads.

Two independent signals arrive here:

* the action span, from align.py over the score grid
* the state-transition time, from detect.state_transitions()

A step confirmed by both is reported differently from one confirmed by neither, because at
the measured precision of this model a bare green checkmark would be a guess dressed up as
a fact.
"""

import os
from dataclasses import dataclass, asdict

from .chunker import mmss

# How close the state transition must be to the action span to count as agreement.
# Defaults to about two chunk strides.
AGREE_TOLERANCE = float(os.environ.get("AGREE_TOLERANCE", 20.0))

VERIFIED = "verified"
LIKELY = "likely"
OUT_OF_ORDER = "out_of_order"
UNCLEAR = "unclear"
NOT_OBSERVED = "not_observed"


@dataclass
class StepResult:
    step_id: int
    name: str
    status: str
    confidence: float          # 0-1, for the UI
    start: float | None
    end: float | None
    state_at: float | None     # when the completion state first held
    score: float               # best action score, 0-10
    signals: list[str]         # which signals fired: "action", "state"
    evidence: list[str]        # the model's own sentences, with timestamps

    def as_dict(self) -> dict:
        d = asdict(self)
        d["start_label"] = mmss(self.start)
        d["end_label"] = mmss(self.end)
        d["state_label"] = mmss(self.state_at)
        return d


def _confidence(signals, score, out_of_order) -> float:
    base = min(score / 10.0, 1.0)
    if len(signals) == 2:
        base = 0.6 + 0.4 * base       # both signals agree: floor it high
    elif signals:
        base = 0.25 + 0.45 * base     # one signal only
    else:
        return 0.0
    return round(base * (0.75 if out_of_order else 1.0), 2)


def build(spans, steps, chunks, activities, state_times) -> list[StepResult]:
    """Fuse the action spans with the state transitions, one result per SOP step."""
    by_id = {s["step_id"]: s for s in steps}
    index_of = {s["step_id"]: i for i, s in enumerate(steps)}
    results = []

    for span in spans:
        step = by_id[span.step_id]
        si = index_of[span.step_id]
        state_at = state_times.get(span.step_id)

        has_action = bool(span.evidence) and not span.weak
        # The state marks when the step finished, so it should land near the span's end.
        has_state = state_at is not None and (
            not has_action or (span.start - AGREE_TOLERANCE) <= state_at <= (span.end + AGREE_TOLERANCE)
        )

        signals = [n for n, on in (("action", has_action), ("state", has_state)) if on]

        if span.out_of_order:
            status = OUT_OF_ORDER
        elif span.weak and not has_state:
            status = UNCLEAR
        elif len(signals) == 2:
            status = VERIFIED
        elif signals:
            status = LIKELY
        else:
            status = NOT_OBSERVED

        start, end = span.start, span.end
        if (start is None or span.weak) and has_state:
            # State fired but the action grid never did: report the state moment alone.
            start = end = state_at

        results.append(StepResult(
            step_id=span.step_id,
            name=step["name"],
            status=status,
            confidence=_confidence(signals, span.score, span.out_of_order),
            start=start,
            end=end,
            state_at=state_at,
            score=round(span.score, 1),
            signals=signals,
            evidence=[f"[{chunks[c].label}] {activities[c][si]}"
                      for c in (span.evidence or ([span.peak_chunk] if span.weak else []))
                      if activities[c][si]],
        ))
    return results


def summarise(results) -> dict:
    """Two numbers, not one.

    `completed / total` is misleading because "not observed" conflates *the worker skipped it*
    with *the editor cut it from the video* - 4 of bench_tjusig's 13 steps simply are not on
    camera. So report how much of the procedure we could see at all, separately from how much
    of what we saw was done correctly.
    """
    total = len(results)
    # "Unclear" is not usable evidence, so it counts towards neither number.
    observed = [r for r in results if r.status not in (NOT_OBSERVED, UNCLEAR)]
    correct = [r for r in observed if r.status in (VERIFIED, LIKELY)]

    return {
        "total_steps": total,
        "observed_steps": len(observed),
        "correct_steps": len(correct),
        "verified_steps": sum(1 for r in observed if r.status == VERIFIED),
        "out_of_order_steps": sum(1 for r in observed if r.status == OUT_OF_ORDER),
        "unclear_steps": [r.step_id for r in results if r.status == UNCLEAR],
        "missed_steps": [r.step_id for r in results if r.status == NOT_OBSERVED],
        # % of the procedure the video gave us any usable evidence about
        "coverage": round(len(observed) / total, 3) if total else 0.0,
        # % of what we could see that was done correctly and in order
        "compliance": round(len(correct) / len(observed), 3) if observed else 0.0,
    }
