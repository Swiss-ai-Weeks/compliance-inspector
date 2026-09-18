"""Score the pipeline against human ground truth.

This is the gate. The notebook's baseline on bench_tjusig was precision 0.2-0.35,
recall 0.04-0.2, and mean IoU of exactly 0 - while bench_applaro scored a perfect
100% because the model never said no. Any change to detect.py or align.py has to be
justified here, not by how the dashboard looks.

    python -m tools.evaluate bench_tjusig
    python -m tools.evaluate bench_tjusig --mode grid --no-state --reuse
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend import align, chunker, config, detect, pipeline, report  # noqa: E402

MIN_OVERLAP_S = 2.0


def overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def load_product(name: str):
    pdir = config.PRODUCTS_DIR / name
    product = json.loads((pdir / "product.json").read_text())
    sop = json.loads((pdir / "sop.json").read_text())
    videos = sorted((pdir / "videos").glob("*.mp4"))
    if not videos:
        raise SystemExit(f"No videos in {pdir/'videos'}")
    video = videos[0]
    gt_path = pdir / "ground_truth" / f"{video.stem}.json"
    gt = json.loads(gt_path.read_text()) if gt_path.exists() else None
    return pdir, product, sop, video, gt


def grid_metrics(scores, chunks, steps, gt_segments, threshold):
    """Precision/recall of the raw grid, the notebook's section 7d measure.

    It ignores the alignment rules entirely, so it measures the model's perception alone.
    """
    step_ids = [s["step_id"] for s in steps]
    truth = np.zeros_like(scores, dtype=int)
    for ci, c in enumerate(chunks):
        for si, sid in enumerate(step_ids):
            for seg in gt_segments:
                if seg["step_id"] == sid and overlap(c.start, c.end, seg["start"], seg["end"]) >= MIN_OVERLAP_S:
                    truth[ci, si] = 1
                    break
    pred = (scores >= threshold).astype(int)

    tp = int(((pred == 1) & (truth == 1)).sum())
    fp = int(((pred == 1) & (truth == 0)).sum())
    fn = int(((pred == 0) & (truth == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn, "positives_predicted": int(pred.sum())}


def step_metrics(results, gt_segments):
    """Per-step verdict correctness and IoU of the predicted interval."""
    by_step = {}
    for seg in gt_segments:
        lo, hi = by_step.get(seg["step_id"], (seg["start"], seg["end"]))
        by_step[seg["step_id"]] = (min(lo, seg["start"]), max(hi, seg["end"]))

    rows = []
    for r in results:
        in_video = r.step_id in by_step
        says_done = r.status in (report.VERIFIED, report.LIKELY, report.OUT_OF_ORDER)
        row = {"step_id": r.step_id, "status": r.status, "in_video": in_video,
               "verdict_correct": in_video == says_done, "iou": None,
               "gt": "-", "pred": "-", "start_err": None}
        if in_video:
            gs, ge = by_step[r.step_id]
            row["gt"] = f"{chunker.mmss(gs)}-{chunker.mmss(ge)}"
            if r.start is not None:
                inter = overlap(r.start, r.end, gs, ge)
                union = max(r.end, ge) - min(r.start, gs)
                row["iou"] = round(inter / union, 2) if union else 0.0
                row["pred"] = f"{chunker.mmss(r.start)}-{chunker.mmss(r.end)}"
                row["start_err"] = round(r.start - gs, 1)
        elif r.start is not None:
            row["pred"] = f"{chunker.mmss(r.start)}-{chunker.mmss(r.end)}"
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--mode", choices=["choice", "grid"], default=config.DETECT_MODE)
    ap.add_argument("--no-state", action="store_true", help="skip the object-state signal")
    ap.add_argument("--reuse", action="store_true",
                    help="re-align saved scores instead of calling the model (action signal only)")
    ap.add_argument("--threshold", type=float, default=config.MIN_STEP_SCORE)
    args = ap.parse_args()

    pdir, product, sop, video, gt = load_product(args.product)
    out_dir = config.OUTPUTS_DIR / "eval" / args.product / video.stem / args.mode
    pages_dir = config.OUTPUTS_DIR / "eval" / args.product / "manual_pages"

    from backend import ingest
    ingest.render_pdf_pages(pdir / product.get("manual", "manual.pdf"), pages_dir)
    steps = detect.load_steps(sop, product.get("step_pages"), pages_dir)
    saved = out_dir / "scores.npy"

    if args.reuse and saved.exists():
        print(f"Reusing {saved}")
        scores = np.load(saved)
        chunks = chunker.cut(video, out_dir / f"chunks_{int(config.CHUNK_SECONDS)}s_"
                             f"ov{int(config.CHUNK_OVERLAP)}_{config.CHUNK_HEIGHT}p")
        spans = align.align(scores, chunks, [s["step_id"] for s in steps])
        activities = [["" for _ in steps] for _ in chunks]
        results = report.build(spans, steps, chunks, activities, {})
        summary = report.summarise(results)
    else:
        def progress(stage, done, total):
            if done and total:
                print(f"\r  {stage}: {done}/{total}", end="", flush=True)
            else:
                print(f"\n[{stage}]", end="", flush=True)

        payload = pipeline.analyze(
            video, sop, out_dir, step_pages=product.get("step_pages"), pages_dir=pages_dir,
            furniture=product.get("name"), progress=progress, use_state=not args.no_state,
            mode=args.mode)
        print()
        scores = np.load(saved)
        chunks = [chunker.Chunk(c["index"], c["start"], c["end"], c["path"])
                  for c in payload["chunks"]]
        results = [report.StepResult(
            step_id=s["step_id"], name=s["name"], status=s["status"], confidence=s["confidence"],
            start=s["start"], end=s["end"], state_at=s["state_at"], score=s["score"],
            signals=s["signals"], evidence=s["evidence"]) for s in payload["steps"]]
        summary = payload["summary"]

    print(f"\n=== {product['name']} / {video.stem} / mode={args.mode} ===")
    print(f"coverage {summary['coverage']:.0%}   compliance {summary['compliance']:.0%}   "
          f"verified {summary['verified_steps']}  out-of-order {summary['out_of_order_steps']}  "
          f"unclear {summary.get('unclear_steps', [])}  "
          f"missed {summary['missed_steps']}")

    if not gt:
        print("No ground truth for this video - skipping accuracy metrics.")
        return

    m = grid_metrics(scores, chunks, steps, gt["segments"], args.threshold)
    print("\n-- chunk x step (notebook baseline: precision 0.2-0.35, recall 0.04-0.2) --")
    print(f"  precision {m['precision']:.3f}  recall {m['recall']:.3f}  f1 {m['f1']:.3f}"
          f"   ({m['positives_predicted']} positives predicted)")

    print("\n-- per step (notebook baseline: IoU 0.00 on every step) --")
    rows = step_metrics(results, gt["segments"])
    print(f"  {'id':>3} {'status':<14} {'in_vid':<7} {'ok':<4} {'gt':<14} {'pred':<14} {'IoU':>5}")
    for r in rows:
        iou = f"{r['iou']:.2f}" if r["iou"] is not None else "  -"
        print(f"  {r['step_id']:>3} {r['status']:<14} {str(r['in_video']):<7} "
              f"{'Y' if r['verdict_correct'] else 'N':<4} {r['gt']:<14} {r['pred']:<14} {iou:>5}")

    labelled = [r for r in rows if r["in_video"]]
    # A labelled step we failed to locate counts as IoU 0, so missing steps cannot flatter the mean.
    mean_iou = np.mean([r["iou"] or 0.0 for r in labelled]) if labelled else 0.0
    correct = sum(1 for r in rows if r["verdict_correct"])
    trivial = len(labelled)  # what "mark every step done" would score
    print(f"\n  verdict correct {correct}/{len(rows)}  (marking every step done scores {trivial}/{len(rows)})")
    print(f"  mean IoU {mean_iou:.3f} over all {len(labelled)} labelled steps")

if __name__ == "__main__":
    main()
