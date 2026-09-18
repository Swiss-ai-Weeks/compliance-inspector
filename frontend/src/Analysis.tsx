import { useEffect, useMemo, useRef, useState } from "react";
import { api, Job, mmss, StepResult } from "./api";
import Timeline, { statusText, stepHue } from "./Timeline";

const STAGE_TEXT: Record<string, string> = {
  chunking: "Cutting the video into clips",
  scoring: "Rating every clip against every step",
  aligning: "Fitting the steps to the timeline",
  state: "Checking how the object looks over time",
  done: "Finishing up",
};

export default function Analysis({ job, onEditSteps }: { job: Job; onEditSteps: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const running = job.status === "analyzing";

  const results = useMemo(() => {
    const m = new Map<number, StepResult>();
    job.report?.steps.forEach((s) => m.set(s.step_id, s));
    return m;
  }, [job.report]);

  function seek(seconds: number) {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = Math.max(0, seconds);
    setTime(v.currentTime);
  }

  function select(stepId: number, jump = true) {
    setSelected(stepId);
    const r = results.get(stepId);
    if (jump && r?.start != null) seek(r.start);
    document.getElementById(`step-${stepId}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  return (
    <div className="analysis">
      {running ? <Running job={job} /> : job.summary && <SummaryBar job={job} onEditSteps={onEditSteps} />}

      <div className="analysis-grid">
        <div className="analysis-main">
          <div className="card player">
            <video ref={videoRef} src={api.videoUrl(job.id)} controls preload="metadata"
              onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)} onSeeked={(e) => setTime(e.currentTarget.currentTime)} />
          </div>
          <div className="card">
            <div className="card-head">
              <h2>Timeline</h2>
              <Legend />
            </div>
            <Timeline job={job} currentTime={time} selected={selected} onSeek={seek} onSelect={(id) => select(id)} />
          </div>
        </div>

        <aside className="card step-list">
          <h2>Steps</h2>
          <ol>
            {(job.sop?.expected_steps ?? []).map((s, i) => (
              <StepItem key={s.step_id} index={i} stepId={s.step_id} name={s.name} result={results.get(s.step_id)}
                running={running} selected={selected === s.step_id} active={isActive(results.get(s.step_id), time)}
                onClick={() => select(s.step_id)} onSeek={seek} />
            ))}
          </ol>
        </aside>
      </div>
      <TrustNote job={job} />
    </div>
  );
}

function isActive(r: StepResult | undefined, t: number) {
  return !!r && r.start != null && r.end != null && t >= r.start && t <= r.end;
}

function Running({ job }: { job: Job }) {
  const p = job.progress;
  const pct = p?.total ? Math.round(((p.done ?? 0) / p.total) * 100) : 0;
  const scored = Object.keys(job.rows).length;
  return (
    <div className="card running">
      <div className="spinner" aria-hidden />
      <div className="running-text">
        <strong>{STAGE_TEXT[p?.stage ?? ""] ?? "Analysing"}</strong>
        <span className="muted">
          {p?.total ? ` — ${p.done} of ${p.total}` : ""}
          {job.chunks.length ? ` · ${scored} of ${job.chunks.length} clips done` : ""}
        </span>
        <div className="bar"><div style={{ width: `${pct}%` }} /></div>
        <span className="muted small">You can watch the "best guess" strip on the timeline fill in as clips finish.</span>
      </div>
    </div>
  );
}

function SummaryBar({ job, onEditSteps }: { job: Job; onEditSteps: () => void }) {
  const s = job.summary!;
  return (
    <div className="card summary">
      <Ring value={s.coverage} label="Seen" hint={`${s.observed_steps} of ${s.total_steps} steps had usable evidence in the video`} />
      <Ring value={s.compliance} label="Correct" hint={`${s.correct_steps} of ${s.observed_steps} seen steps were done in order`} />
      <div className="summary-facts">
        <Fact n={s.verified_steps} label="verified" cls="verified" hint="Both the action and the finished state were seen" />
        <Fact n={s.correct_steps - s.verified_steps} label="likely" cls="likely" hint="One of the two signals was seen" />
        <Fact n={s.out_of_order_steps} label="out of order" cls="out_of_order" hint="Seen clearly, but not where the manual puts it" />
        <Fact n={s.unclear_steps?.length ?? 0} label="unclear" cls="unclear" hint="Only a weak match that could not be placed - worth checking by eye" />
        <Fact n={s.missed_steps.length} label="not seen" cls="not_observed" hint="Skipped, or simply not shown in the video" />
      </div>
      <div className="summary-actions">
        <button className="btn btn-small" onClick={onEditSteps}>Edit steps & re-run</button>
        {job.report && <span className="muted small">{job.report.model} · {Math.round(job.report.elapsed_s)} s</span>}
      </div>
    </div>
  );
}

function Ring({ value, label, hint }: { value: number; label: string; hint: string }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const pct = Math.round(value * 100);
  return (
    <div className="ring" title={hint}>
      <svg viewBox="0 0 80 80" width="80" height="80" aria-hidden>
        <circle cx="40" cy="40" r={r} className="ring-track" />
        <circle cx="40" cy="40" r={r} className="ring-fill" strokeDasharray={`${c * value} ${c}`} transform="rotate(-90 40 40)" />
        <text x="40" y="45" textAnchor="middle" className="ring-text">{pct}%</text>
      </svg>
      <div>
        <div className="ring-label">{label}</div>
        <div className="muted small">{hint}</div>
      </div>
    </div>
  );
}

function Fact({ n, label, cls, hint }: { n: number; label: string; cls: string; hint: string }) {
  return (
    <div className="fact" title={hint}>
      <span className={`fact-n status-${cls}`}>{n}</span>
      <span className="fact-label">{label}</span>
    </div>
  );
}

type ItemProps = {
  index: number; stepId: number; name: string; result?: StepResult; running: boolean;
  selected: boolean; active: boolean; onClick: () => void; onSeek: (t: number) => void;
};

function StepItem({ index, stepId, name, result: r, running, selected, active, onClick, onSeek }: ItemProps) {
  const [open, setOpen] = useState(false);
  useEffect(() => { if (selected) setOpen(true); }, [selected]);

  return (
    <li id={`step-${stepId}`} className={`step ${selected ? "step-sel" : ""} ${active ? "step-active" : ""}`}>
      <button className="step-main" onClick={onClick}>
        <span className="step-dot" style={{ background: `hsl(${stepHue(index)} 65% 50%)` }} />
        <span className="step-num">{stepId}</span>
        <span className="step-name">{name}</span>
        {r ? (
          <span className={`pill status-bg-${r.status}`}>{statusText(r.status)}</span>
        ) : (
          <span className="pill pill-pending">{running ? "…" : "–"}</span>
        )}
      </button>
      {r && (
        <div className="step-detail">
          {r.status === "not_observed" ? (
            <span className="muted small">No evidence found — skipped, or not shown in the video.</span>
          ) : r.status === "unclear" ? (
            <div className="step-meta">
              <span className="muted small">Only a weak match, and not where the manual puts it.</span>
              {r.start != null && (
                <button className="link small" onClick={() => onSeek(r.start!)}>check {r.start_label}</button>
              )}
              {r.evidence.length > 0 && (
                <button className="link small" onClick={() => setOpen((o) => !o)}>{open ? "hide" : "why?"}</button>
              )}
            </div>
          ) : (
            <div className="step-meta">
              <button className="link" onClick={() => r.start != null && onSeek(r.start)}>
                {r.start_label}–{r.end_label}
              </button>
              <span className="conf" title="How much both signals support this">
                <span className="conf-bar"><span style={{ width: `${r.confidence * 100}%` }} /></span>
                {Math.round(r.confidence * 100)}%
              </span>
              <span className="signals">
                <span className={`chip ${r.signals.includes("action") ? "chip-on" : ""}`} title="The action was recognised in a clip">action</span>
                <span className={`chip ${r.signals.includes("state") ? "chip-on" : ""}`}
                  title={r.state_at != null ? `Looked done from ${mmss(r.state_at)}` : "The finished state was not recognised"}>state</span>
              </span>
              {r.evidence.length > 0 && (
                <button className="link small" onClick={() => setOpen((o) => !o)}>{open ? "hide" : "why?"}</button>
              )}
            </div>
          )}
          {open && r.evidence.length > 0 && (
            <ul className="evidence">
              {r.evidence.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function Legend() {
  return (
    <div className="legend">
      <span title="Verified or likely: done, in manual order"><i className="lg lg-pass" />pass</span>
      <span title="Out of order or unclear: look at the video"><i className="lg lg-check" />check</span>
      <span title="No evidence the step was done"><i className="lg lg-fail" />not seen</span>
      <span><i className="lg lg-state" />looked done</span>
    </div>
  );
}

function TrustNote({ job }: { job: Job }) {
  return (
    <details className="card trust">
      <summary>How much should I trust this?</summary>
      <p>
        Each step is checked two independent ways. <strong>Action</strong>: every short clip is rated against every step,
        then the steps are fitted to the timeline in manual order, so one bad rating cannot drag the rest along.{" "}
        <strong>State</strong>: frames across the video are checked for how the object looks once the step is done.
        <em> Verified</em> means both agreed; <em>likely</em> means one did; <em>unclear</em> means only a weak match
        turned up somewhere the manual order doesn't expect, so it is shown for you to check rather than counted.
      </p>
      <p>
        The current video model ({job.report?.model ?? "Cosmos"}) is not reliable at telling which steps were
        missed. Its answers also vary between runs: re-running the same video changes about a quarter of the clip
        ratings, and can change a step's status. Treat every status as "worth checking", not as proof, and use the
        timeline to jump to the moment and look.
      </p>
    </details>
  );
}
