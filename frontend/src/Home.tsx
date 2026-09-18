import { FormEvent, useEffect, useState } from "react";
import { api, Health, JobListItem, Product } from "./api";
import { navigate } from "./App";

const STATUS_LABEL: Record<string, string> = {
  ingesting: "Downloading",
  authoring: "Reading manual",
  awaiting_review: "Needs review",
  analyzing: "Analysing",
  done: "Done",
  error: "Failed",
};

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    api.products().then(setProducts).catch((e: Error) => setError(e.message));
    api.jobs().then(setJobs).catch(() => {});
  }, []);

  async function start(form: FormData, key: string) {
    setBusy(key);
    setError(null);
    try {
      const job = await api.createJob(form);
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  function startProduct(id: string) {
    const form = new FormData();
    form.set("product", id);
    start(form, id);
  }

  return (
    <div className="home">
      <section className="hero">
        <h1>Check a procedure against its manual</h1>
        <p>
          Give it a video of the work and the instruction PDF. It drafts the steps from the manual for you to
          check, then finds when each one happens in the video, and flags the ones it could not see.
        </p>
        <HealthBanner health={health} />
      </section>

      {error && <div className="alert alert-error">{error}</div>}

      <section className="card">
        <h2>Try a demo</h2>
        <p className="muted">Sample assembly videos with their manuals, ready to run.</p>
        <div className="product-grid">
          {products.map((p) => (
            <button key={p.id} className="product" onClick={() => startProduct(p.id)} disabled={busy !== null}>
              <span className="product-name">{p.name}</span>
              <span className="product-meta">
                {p.steps} steps
              </span>
              <span className="product-go">{busy === p.id ? "Starting…" : "Run →"}</span>
            </button>
          ))}
          {products.length === 0 && <p className="muted">No demo products installed.</p>}
        </div>
      </section>

      <NewJobForm busy={busy === "custom"} disabled={busy !== null} onSubmit={(f) => start(f, "custom")} />

      {jobs.length > 0 && (
        <section className="card">
          <h2>Recent checks</h2>
          <ul className="job-list">
            {jobs.slice(0, 12).map((j) => (
              <li key={j.id}>
                <a href={`#/jobs/${j.id}`}>
                  <span className="job-name">{j.product_name || "Untitled"}</span>
                  <span className={`pill pill-${j.status}`}>{STATUS_LABEL[j.status] ?? j.status}</span>
                  <span className="job-meta">
                    {j.summary ? `${Math.round(j.summary.coverage * 100)}% seen · ${Math.round(j.summary.compliance * 100)}% correct` : ""}
                  </span>
                  <span className="job-time">{new Date(j.created_at * 1000).toLocaleString()}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function HealthBanner({ health }: { health: Health | null }) {
  if (!health) return null;
  return (
    <div className="health">
      <span className={`dot ${health.nim.ok ? "dot-ok" : "dot-bad"}`} />
      {health.nim.ok ? `Video model online: ${health.video_model}` : "Video model unreachable – analyses will fail"}
      {!health.author_hosted && (
        <span className="health-warn">
          · No hosted authoring key: steps from new manuals will be drafted by the local video model and need careful review
        </span>
      )}
    </div>
  );
}

type SourceMode = "url" | "file";

function NewJobForm({ busy, disabled, onSubmit }: { busy: boolean; disabled: boolean; onSubmit: (f: FormData) => void }) {
  const [videoMode, setVideoMode] = useState<SourceMode>("url");
  const [manualMode, setManualMode] = useState<SourceMode>("url");

  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    // Only send the half of each pair the user chose, so a stale value in a hidden field is ignored.
    for (const [mode, url, file] of [
      [videoMode, "video_url", "video_file"],
      [manualMode, "manual_url", "manual_file"],
    ] as const) {
      form.delete(mode === "url" ? file : url);
    }
    onSubmit(form);
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Check your own video</h2>
      <div className="source-grid">
        <SourceField label="Video" mode={videoMode} setMode={setVideoMode} urlName="video_url" fileName="video_file"
          accept="video/mp4,video/quicktime,video/*" placeholder="https://…/assembly.mp4" />
        <SourceField label="Manual (PDF)" mode={manualMode} setMode={setManualMode} urlName="manual_url"
          fileName="manual_file" accept="application/pdf" placeholder="https://…/manual.pdf" />
      </div>
      <div className="form-actions">
        <button className="btn btn-primary" type="submit" disabled={disabled}>
          {busy ? "Uploading…" : "Read manual"}
        </button>
        <span className="muted">Next you'll review the steps it drafts before any video is analysed.</span>
      </div>
    </form>
  );
}

function SourceField(props: {
  label: string; mode: SourceMode; setMode: (m: SourceMode) => void;
  urlName: string; fileName: string; accept: string; placeholder: string;
}) {
  return (
    <fieldset className="source">
      <legend>{props.label}</legend>
      <div className="seg" role="tablist">
        {(["url", "file"] as const).map((m) => (
          <button key={m} type="button" role="tab" aria-selected={props.mode === m}
            className={props.mode === m ? "seg-on" : ""} onClick={() => props.setMode(m)}>
            {m === "url" ? "Link" : "Upload"}
          </button>
        ))}
      </div>
      {props.mode === "url" ? (
        <input className="input" type="url" name={props.urlName} placeholder={props.placeholder} required />
      ) : (
        <input className="input" type="file" name={props.fileName} accept={props.accept} required />
      )}
    </fieldset>
  );
}
