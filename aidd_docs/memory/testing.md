# Testing

## Accuracy: `tools/evaluate.py`

The main test. Runs the same `backend/pipeline.py` the website runs, on a demo product, and compares
it with the human timestamps in `products/<name>/ground_truth/`.

```bash
.venv/bin/python -m tools.evaluate bench_tjusig                 # full run, ~3 min with state checks
.venv/bin/python -m tools.evaluate bench_tjusig --reuse         # re-align saved scores, no model calls
.venv/bin/python -m tools.evaluate bench_applaro --mode choice
```

It prints chunk x step precision/recall, per-step status against the labels, mean IoU (unlocated
labelled steps count as 0), and verdict accuracy next to what "mark every step done" would score.
A change is only an improvement if it beats that trivial line on both videos.

- `--reuse` makes threshold changes free to test, since scores are saved per mode under
  `outputs/eval/<product>/<video>/<mode>/`.
- Model output varies between runs (about a quarter of ratings), so compare approaches on the same
  saved grid, and do not read much into a single fresh run.
- Only two labelled videos exist: tuning thresholds against them overfits quickly.

## Unit checks

No test suite yet. `align.align` has been checked by hand on three toy grids (in order, a skipped
step, an out-of-order step) and `detect.fit_transition` on five answer patterns; both are pure
functions and the first candidates for `pytest`.

## End to end

Checked by driving the built app in headless Chromium (Playwright, outside the project): home =>
demo => review and edit a step => run => live timeline => report, plus phone width (no horizontal
scroll) and dark mode. Also run inside the Docker image against the host NIM. Playwright is not an
app dependency.
