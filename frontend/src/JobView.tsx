import { useState } from "react";
import { api, Job } from "./api";
import { useJob } from "./useJob";
import SopReview from "./SopReview";
import Analysis from "./Analysis";

const STAGES: Record<string, string> = {
  authoring: "Reading the manual, page by page",
  chunking: "Cutting the video into clips",
  scoring: "Asking the video model about every clip and step",
  aligning: "Fitting the steps to the timeline",
  state: "Checking how the object looks across the video",
  done: "Finishing up",
};

export default function JobView({ id }: { id: string }) {
  const { job, setJob, error, live } = useJob(id);
  const [editing, setEditing] = useState(false);

  if (error) return <div className="alert alert-error">{error} <a href="#/">Back</a></div>;
  if (!job) return <div className="loading">Loading…</div>;

  const reviewing = job.status === "awaiting_review" || (editing && (job.status === "done" || job.status === "error"));

  async function confirm(sop: NonNullable<Job["sop"]>, pages: Record<string, number>) {
    const updated = await api.confirmSop(job!.id, sop, pages);
    setJob(updated);
    setEditing(false);
  }

  return (
    <div className="job">
      <div className="job-head">
        <div>
          <a href="#/" className="back">← All checks</a>
          <h1>{job.product_name || "Untitled check"}</h1>
        </div>
        <div className="job-head-right">
          <Stepper status={job.status} />
          <span className={`live ${live ? "live-on" : ""}`} title={live ? "Receiving live updates" : "Reconnecting…"}>
            {live ? "● live" : "○ offline"}
          </span>
        </div>
      </div>

      {job.status === "error" && !editing && (
        <div className="alert alert-error">
          <strong>This check failed.</strong> {job.error}
          {job.sop && (
            <button className="btn btn-small" onClick={() => setEditing(true)}>Review steps and retry</button>
          )}
        </div>
      )}

      {(job.status === "ingesting" || job.status === "authoring") && <Working job={job} />}

      {reviewing && job.sop && (
        <SopReview job={job} onConfirm={confirm} onCancel={editing ? () => setEditing(false) : undefined} />
      )}

      {!reviewing && (job.status === "analyzing" || job.status === "done") && (
        <Analysis job={job} onEditSteps={() => setEditing(true)} />
      )}
    </div>
  );
}

function Stepper({ status }: { status: Job["status"] }) {
  const order = ["ingest", "review", "analyse", "report"];
  const at = { ingesting: 0, authoring: 0, awaiting_review: 1, analyzing: 2, done: 3, error: -1 }[status];
  return (
    <ol className="stepper">
      {order.map((name, i) => (
        <li key={name} className={i < at ? "done" : i === at ? "now" : ""}>{name}</li>
      ))}
    </ol>
  );
}

function Working({ job }: { job: Job }) {
  const p = job.progress;
  const pct = p?.total ? Math.round(((p.done ?? 0) / p.total) * 100) : null;
  const label = job.status === "ingesting" ? "Downloading the video and manual" : STAGES[p?.stage ?? ""] ?? "Working";
  return (
    <div className="card working">
      <div className="spinner" aria-hidden />
      <div className="working-text">
        <strong>{label}</strong>
        {pct !== null && <span className="muted"> — {p!.done} of {p!.total}</span>}
        {pct !== null && <div className="bar"><div style={{ width: `${pct}%` }} /></div>}
      </div>
    </div>
  );
}
