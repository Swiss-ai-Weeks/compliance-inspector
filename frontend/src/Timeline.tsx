import { MouseEvent, useMemo, useRef } from "react";
import { Job, mmss, StepResult } from "./api";

type Props = {
  job: Job;
  currentTime: number;
  selected: number | null;
  onSeek: (seconds: number) => void;
  onSelect: (stepId: number) => void;
};

const W = 1000;          // viewBox width; the SVG scales to its container
const GUTTER = 200;      // left column for step labels
const CLEAR_SCORE = 5;   // same bar as the backend's MIN_STEP_SCORE: below it, no step is recognised
const PAD_R = 12;
const CLIP_LANE = 26;
const LANE = 26;
const AXIS = 22;

export const stepHue = (index: number) => Math.round((index * 137.508) % 360); // golden angle: neighbours differ

/**
 * One lane per step. In each lane:
 *   thick bar      - when the model places it: green = pass, orange = check by eye, red = not seen
 *   diamond        - when its "how it looks once done" state first held
 * The strip on top shows, per clip, which step the model rated highest - it fills in live.
 */
export default function Timeline({ job, currentTime, selected, onSeek, onSelect }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const steps = job.sop?.expected_steps ?? [];
  const duration = job.duration || Math.max(1, ...job.chunks.map((c) => c.end));
  const plotW = W - GUTTER - PAD_R;
  const x = (t: number) => GUTTER + (Math.min(Math.max(t, 0), duration) / duration) * plotW;

  const results = useMemo(() => {
    const m = new Map<number, StepResult>();
    job.report?.steps.forEach((s) => m.set(s.step_id, s));
    return m;
  }, [job.report]);

  const stepIndex = useMemo(() => new Map(steps.map((s, i) => [s.step_id, i])), [steps]);
  const height = AXIS + CLIP_LANE + 8 + steps.length * LANE + 6;
  const tickEvery = duration > 600 ? 60 : duration > 240 ? 30 : duration > 90 ? 20 : 10;
  const ticks = Array.from({ length: Math.floor(duration / tickEvery) + 1 }, (_, i) => i * tickEvery);

  function seekFromClick(e: MouseEvent<SVGRectElement>) {
    const svg = svgRef.current!;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const local = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    onSeek(((local.x - GUTTER) / plotW) * duration);
  }

  return (
    <div className="timeline-wrap">
      <svg ref={svgRef} className="timeline" viewBox={`0 0 ${W} ${height}`} role="img"
        aria-label="Timeline of when each step happens in the video">
        {/* axis */}
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={AXIS - 4} y2={height} className="tl-grid" />
            <text x={x(t)} y={AXIS - 8} className="tl-tick" textAnchor="middle">{mmss(t)}</text>
          </g>
        ))}

        {/* clip strip */}
        <text x={GUTTER - 10} y={AXIS + CLIP_LANE / 2 + 4} className="tl-label tl-label-muted" textAnchor="end">
          model's best guess
        </text>
        {job.chunks.map((c) => {
          const row = job.rows[String(c.index)];
          const idx = row?.best_step != null ? stepIndex.get(row.best_step) : undefined;
          const strong = row && row.best_score >= CLEAR_SCORE;
          return (
            <rect key={c.index} x={x(c.start)} y={AXIS + 3} width={Math.max(1, x(c.end) - x(c.start) - 1)}
              height={CLIP_LANE - 6} rx={2} onClick={() => onSeek(c.start)}
              className={row ? "tl-clip" : "tl-clip tl-clip-pending"}
              style={strong && idx !== undefined
                ? { fill: `hsl(${stepHue(idx)} 65% 50%)`, opacity: 0.35 + 0.65 * ((row.best_score - CLEAR_SCORE) / (10 - CLEAR_SCORE)) }
                : undefined}>
              <title>
                {`${c.label}` + (row
                  ? strong ? ` · best: step ${row.best_step} (${row.best_score}/10)\n${row.activity}` : ` · no clear step (best ${row.best_score}/10)`
                  : " · not scored yet")}
              </title>
            </rect>
          );
        })}

        {/* step lanes */}
        {steps.map((s, i) => {
          const y = AXIS + CLIP_LANE + 8 + i * LANE;
          const r = results.get(s.step_id);
          const isSel = selected === s.step_id;
          return (
            <g key={s.step_id} className={`tl-lane ${isSel ? "tl-lane-sel" : ""}`}>
              <rect x={0} y={y} width={W} height={LANE} className="tl-lane-bg" onClick={() => onSelect(s.step_id)} />
              <g onClick={() => onSelect(s.step_id)} style={{ cursor: "pointer" }}>
                <circle cx={14} cy={y + LANE / 2} r={4.5} style={{ fill: `hsl(${stepHue(i)} 65% 50%)` }} />
                <text x={26} y={y + LANE / 2 + 4} className="tl-label">
                  <tspan className="tl-num">{s.step_id}</tspan> {truncate(s.name, 24)}
                  <title>{s.name}</title>
                </text>
              </g>
              {r?.start != null && r.end != null && (
                <rect x={x(r.start)} y={y + 11} width={Math.max(4, x(r.end) - x(r.start))} height={10} rx={3}
                  className={`tl-pred tl-${r.status}`} onClick={() => { onSelect(s.step_id); onSeek(r.start!); }}>
                  <title>{`${statusText(r.status)} · ${r.start_label}–${r.end_label} · confidence ${Math.round(r.confidence * 100)}%`}</title>
                </rect>
              )}
              {r?.status === "not_observed" && (
                <g onClick={() => onSelect(s.step_id)}>
                  <rect x={GUTTER} y={y + 11} width={plotW} height={10} rx={3} className="tl-pred tl-not_observed">
                    <title>Not seen anywhere in the video</title>
                  </rect>
                  <text x={GUTTER + 8} y={y + 20} className="tl-missed-text">not seen</text>
                </g>
              )}
              {r?.state_at != null && (
                <path d={`M ${x(r.state_at)} ${y + 9} l 6 7 l -6 7 l -6 -7 z`} className="tl-state"
                  onClick={() => onSeek(r.state_at!)}>
                  <title>{`Looked done from ${r.state_label}`}</title>
                </path>
              )}
            </g>
          );
        })}

        {/* click-to-seek surface over the plot, below the bars so they stay clickable */}
        <rect x={GUTTER} y={0} width={plotW} height={AXIS} className="tl-seek" onClick={seekFromClick} />

        {/* playhead */}
        <line x1={x(currentTime)} x2={x(currentTime)} y1={AXIS - 4} y2={height} className="tl-playhead" />
        <path d={`M ${x(currentTime) - 5} ${AXIS - 10} h 10 l -5 6 z`} className="tl-playhead-cap" />
      </svg>
    </div>
  );
}

export function statusText(status: StepResult["status"]) {
  return { verified: "Verified", likely: "Likely", out_of_order: "Out of order", unclear: "Unclear", not_observed: "Not seen" }[status];
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
