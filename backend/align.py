"""Pick the best staircase through the score grid.

The grid from detect.py has one row per clip (in time order) and one column per SOP step.
Assembly moves forward, so the correct reading is a staircase: it may stay in a column, or
move right, but it never climbs back left.

    step1  step2  step3
   [  8 ]     3      1      00:00-00:10
   [  7 ]     4      2      00:08-00:18
      2    [  9 ]    3      00:16-00:26
      1    [  7 ]    4      00:24-00:34
      2       3   [  8 ]    00:32-00:42

The notebook's checker walked down the rows holding a pointer, asking only "is my step done,
is the next one starting?". A yes-biased model answers "yes" at row 1, the pointer advances,
and it can never go back - so every later row is asked about the wrong step. That is exactly
how bench_tjusig stamped steps 2 and 3 at 00:08 (they happen at 00:37 and 00:58) and how
bench_applaro reached a perfect 100%.

Here nothing is decided while reading. The whole grid is filled first, then one dynamic
program picks the highest-scoring staircase over all of it, so a single noisy cell is
outvoted by the other 259.
"""

from dataclasses import dataclass, field

import numpy as np

from . import config


@dataclass
class StepSpan:
    step_id: int
    chunks: list[int] = field(default_factory=list)   # chunks the staircase assigned here
    evidence: list[int] = field(default_factory=list)  # of those, the ones that scored well
    start: float | None = None
    end: float | None = None
    score: float = 0.0          # best score among the evidence chunks
    out_of_order: bool = False
    weak: bool = False          # a middling match somewhere, too weak to place or to call out of order
    peak_chunk: int | None = None  # strongest evidence anywhere, in or out of position


def align(scores: np.ndarray, chunks, step_ids,
          *, idle_score: float | None = None, skip_penalty: float | None = None,
          min_step_score: float | None = None,
          out_of_order_score: float | None = None) -> list[StepSpan]:
    """Find the best monotone assignment of chunks to steps.

    Returns one StepSpan per step, in SOP order.
    """
    idle_score = idle_score if idle_score is not None else config.IDLE_SCORE
    skip_penalty = skip_penalty if skip_penalty is not None else config.SKIP_PENALTY
    min_step_score = min_step_score if min_step_score is not None else config.MIN_STEP_SCORE
    out_of_order_score = (out_of_order_score if out_of_order_score is not None
                          else config.OUT_OF_ORDER_SCORE)

    n_c, n_s = scores.shape
    if n_c == 0 or n_s == 0:
        return [StepSpan(step_id=sid) for sid in step_ids]

    # A chunk that matches nothing well is better explained as "nothing relevant happening",
    # so its contribution is floored: low scores stop dragging the path around.
    value = np.maximum(scores, idle_score)

    NEG = -1e18
    best = np.full((n_c, n_s), NEG)
    back = np.full((n_c, n_s), -1, dtype=int)  # which step the previous chunk was on

    # First chunk: starting on step k means steps 0..k-1 were skipped before the video began.
    for k in range(n_s):
        best[0, k] = value[0, k] - skip_penalty * k

    for c in range(1, n_c):
        # advance[c][k] = max over j < k of (best[c-1][j] - skip_penalty*(k-j-1))
        #               = max over j < k of (best[c-1][j] + skip_penalty*j) - skip_penalty*(k-1)
        # so carrying that inner max forward makes each cell O(1) instead of O(n_s).
        running_max, running_arg = NEG, -1
        for k in range(n_s):
            stay = best[c - 1, k]
            advance = NEG
            advance_from = -1
            if running_arg >= 0:
                # cost of skipping the (k - j - 1) steps strictly between j and k
                advance = running_max - skip_penalty * (k - 1)
                advance_from = running_arg
            if stay >= advance:
                best[c, k], back[c, k] = stay + value[c, k], k
            else:
                best[c, k], back[c, k] = advance + value[c, k], advance_from
            # fold step k into the running max for the next column
            cand = best[c - 1, k] + skip_penalty * k
            if cand > running_max:
                running_max, running_arg = cand, k

    # Finishing on step k means steps k+1..n_s-1 were skipped at the end.
    finals = [best[n_c - 1, k] - skip_penalty * (n_s - 1 - k) for k in range(n_s)]
    k = int(np.argmax(finals))

    assignment = [0] * n_c
    for c in range(n_c - 1, -1, -1):
        assignment[c] = k
        k = back[c, k] if c > 0 else k

    spans = [StepSpan(step_id=sid) for sid in step_ids]
    for c, k in enumerate(assignment):
        spans[k].chunks.append(c)

    for si, span in enumerate(spans):
        column = scores[:, si]
        span.peak_chunk = int(np.argmax(column)) if n_c else None

        # Only chunks that actually scored count as evidence: a chunk can sit inside a
        # step's span simply because nothing else explained it better.
        span.evidence = [c for c in span.chunks if scores[c, si] >= min_step_score]
        if span.evidence:
            span.start = chunks[span.evidence[0]].start
            span.end = chunks[span.evidence[-1]].end
            span.score = float(max(scores[c, si] for c in span.evidence))
        elif span.peak_chunk is not None and column[span.peak_chunk] >= out_of_order_score:
            # The staircase could not fit this step in order, yet the grid shows strong
            # evidence somewhere. That is a genuine out-of-order execution, not a miss -
            # in bench_tjusig step 4 really does happen before step 2.
            span.out_of_order = True
            span.evidence = [span.peak_chunk]
            span.start = chunks[span.peak_chunk].start
            span.end = chunks[span.peak_chunk].end
            span.score = float(column[span.peak_chunk])
        elif span.peak_chunk is not None and column[span.peak_chunk] >= min_step_score:
            # Some clip matched, but only weakly, and not where the manual order puts it.
            # With a yes-biased model almost every step gets one such middling score, so
            # calling these "out of order" would be noise and calling them "not seen" would
            # be false. Report where the match was and let a person look.
            span.weak = True
            span.start = chunks[span.peak_chunk].start
            span.end = chunks[span.peak_chunk].end
            span.score = float(column[span.peak_chunk])

    return spans
def greedy_align(scores, chunks, step_ids,
                 *, min_step_score: float | None = None,
                 patience: int = 2, required_streak: int = 2):
    """Find a greedy assignment of chunks to steps, simulating a real-time stream.

    Returns one StepSpan per step, in SOP order, just like the global alignment,
    ensuring 100% compatibility with report.py downstream logic.
    """
    import numpy as np
    from . import config
    
    min_step_score = min_step_score if min_step_score is not None else config.MIN_STEP_SCORE

    n_c, n_s = scores.shape
    spans = [StepSpan(step_id=sid) for sid in step_ids]
    if n_c == 0 or n_s == 0:
        return spans

    active_si = None
    missing_signal = 0
    highest_closed_si = -1
    
    # State for streak tracking
    current_streak_si = None
    current_streak_count = 0

    for ci in range(n_c):
        row = scores[ci]
        best_si = int(np.argmax(row))
        best_score = float(row[best_si])

        if best_score >= min_step_score:
            if active_si == best_si:
                # We are already in this step
                missing_signal = 0
                span = spans[active_si]
                span.chunks.append(ci)
                span.evidence.append(ci)
                if best_score > span.score:
                    span.score = best_score
                    span.peak_chunk = ci
            else:
                # We see a different step scoring high.
                if current_streak_si == best_si:
                    current_streak_count += 1
                else:
                    current_streak_si = best_si
                    current_streak_count = 1
                
                if current_streak_count >= required_streak:
                    # Switch to new step!
                    if active_si is not None:
                        highest_closed_si = max(highest_closed_si, active_si)
                        # Retrospectively add the streak chunks to the new step
                        for past_ci in range(ci - required_streak + 1, ci):
                            spans[best_si].chunks.append(past_ci)
                            spans[best_si].evidence.append(past_ci)
                            if scores[past_ci, best_si] > spans[best_si].score:
                                spans[best_si].score = float(scores[past_ci, best_si])
                                spans[best_si].peak_chunk = past_ci
                    
                    active_si = best_si
                    missing_signal = 0
                    current_streak_count = 0
                    
                    span = spans[active_si]
                    span.chunks.append(ci)
                    span.evidence.append(ci)
                    if best_score > span.score:
                        span.score = best_score
                        span.peak_chunk = ci
                else:
                    # Not enough streak yet.
                    if active_si is not None:
                        missing_signal += 1
                        if missing_signal > patience:
                            highest_closed_si = max(highest_closed_si, active_si)
                            active_si = None
                        else:
                            spans[active_si].chunks.append(ci)
        else:
            # No step scores high enough
            current_streak_si = None
            current_streak_count = 0
            
            if active_si is not None:
                missing_signal += 1
                if missing_signal > patience:
                    # Timeout exceeded, close step
                    highest_closed_si = max(highest_closed_si, active_si)
                    active_si = None
                else:
                    spans[active_si].chunks.append(ci)

    # Post-process spans
    for si, span in enumerate(spans):
        column = scores[:, si]
        span.peak_chunk = int(np.argmax(column)) if n_c else None
        
        if span.evidence:
            span.start = chunks[span.evidence[0]].start
            span.end = chunks[span.evidence[-1]].end
            if highest_closed_si > si:
                span.out_of_order = True
        else:
            if span.peak_chunk is not None and column[span.peak_chunk] >= config.OUT_OF_ORDER_SCORE:
                span.out_of_order = True
                span.evidence = [span.peak_chunk]
                span.start = chunks[span.peak_chunk].start
                span.end = chunks[span.peak_chunk].end
                span.score = float(column[span.peak_chunk])
            elif span.peak_chunk is not None and column[span.peak_chunk] >= min_step_score:
                span.weak = True
                span.start = chunks[span.peak_chunk].start
                span.end = chunks[span.peak_chunk].end
                span.score = float(column[span.peak_chunk])

    return spans
