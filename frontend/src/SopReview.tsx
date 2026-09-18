import { useMemo, useState } from "react";
import { api, Job, Sop, Step } from "./api";

type Props = {
  job: Job;
  onConfirm: (sop: Sop, stepPages: Record<string, number>) => Promise<void>;
  onCancel?: () => void;
};

/**
 * The pause between reading the manual and watching the video.
 *
 * The video model leans heavily on the wording of each step, and the draft can be plainly
 * wrong, so a person fixes it here before any analysis runs.
 */
export default function SopReview({ job, onConfirm, onCancel }: Props) {
  const [steps, setSteps] = useState<Step[]>(() => structuredClone(job.sop!.expected_steps));
  const [pages, setPages] = useState<Record<string, number>>(() => ({ ...job.step_pages }));
  const [selected, setSelected] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const problems = useMemo(() => validate(steps), [steps]);
  const step = steps[selected];
  const page = step ? pages[String(step.step_id)] : undefined;
  const preloaded = job.author_model?.startsWith("preloaded");

  function patch(i: number, change: Partial<Step>) {
    setSteps((prev) => prev.map((s, j) => (j === i ? { ...s, ...change } : s)));
  }

  function renumber(i: number, value: number) {
    const old = String(steps[i].step_id);
    patch(i, { step_id: value });
    setPages((prev) => {
      const next = { ...prev };
      if (old in next) {
        next[String(value)] = next[old];
        delete next[old];
      }
      return next;
    });
  }

  function add() {
    const next = Math.max(0, ...steps.map((s) => s.step_id)) + 1;
    setSteps((prev) => [...prev, { step_id: next, name: "", description: "", visual_cues: [], completion_state: "", state_is_monotone: true }]);
    setSelected(steps.length);
  }

  function remove(i: number) {
    const id = String(steps[i].step_id);
    setSteps((prev) => prev.filter((_, j) => j !== i));
    setPages((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    setSelected((s) => Math.max(0, Math.min(s, steps.length - 2)));
  }

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const ordered = [...steps].sort((a, b) => a.step_id - b.step_id);
      await onConfirm({ ...job.sop!, expected_steps: ordered }, pages);
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  }

  return (
    <div className="review">
      <div className="card review-intro">
        <div>
          <h2>Check the steps before analysing</h2>
          <p className="muted">
            {preloaded
              ? "These steps were written and checked by hand. Adjust them if you like, then run the analysis."
              : `Drafted from the manual by ${job.author_model}. The video model relies on this wording, so fix anything that doesn't match the drawings.`}
          </p>
          {job.warnings.map((w) => <div key={w} className="alert alert-warn">{w}</div>)}
        </div>
        <div className="review-actions">
          {onCancel && <button className="btn" onClick={onCancel} disabled={saving}>Cancel</button>}
          <button className="btn btn-primary" onClick={submit} disabled={saving || problems.length > 0}>
            {saving ? "Starting…" : `Run analysis on ${steps.length} steps`}
          </button>
        </div>
      </div>
      {problems.length > 0 && <div className="alert alert-warn">{problems.join(" · ")}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="review-body">
        <nav className="card step-nav" aria-label="Steps">
          {steps.map((s, i) => (
            <button key={i} className={`step-nav-item ${i === selected ? "on" : ""}`} onClick={() => setSelected(i)}>
              <span className="step-num">{s.step_id}</span>
              <span className="step-nav-name">{s.name || <em>Untitled</em>}</span>
            </button>
          ))}
          <button className="btn btn-small add-step" onClick={add}>+ Add step</button>
        </nav>

        {step ? (
          <div className="card step-editor" key={selected}>
            <div className="editor-row">
              <label className="field field-narrow">
                <span>Step no.</span>
                <input className="input" type="number" min={1} value={step.step_id}
                  onChange={(e) => renumber(selected, Number(e.target.value))} />
              </label>
              <label className="field">
                <span>Name</span>
                <input className="input" value={step.name} onChange={(e) => patch(selected, { name: e.target.value })} />
              </label>
              <label className="field field-narrow">
                <span>Manual page</span>
                <select className="input" value={page ?? ""}
                  onChange={(e) => setPages((p) => {
                    const next = { ...p };
                    if (e.target.value) next[String(step.step_id)] = Number(e.target.value);
                    else delete next[String(step.step_id)];
                    return next;
                  })}>
                  <option value="">none</option>
                  {Array.from({ length: job.page_count }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>What is done</span>
              <textarea className="input" rows={3} value={step.description}
                onChange={(e) => patch(selected, { description: e.target.value })} />
            </label>
            <label className="field">
              <span>What a camera would see <em>(one per line)</em></span>
              <textarea className="input" rows={4} value={step.visual_cues.join("\n")}
                onChange={(e) => patch(selected, { visual_cues: e.target.value.split("\n") })}
                onBlur={() => patch(selected, { visual_cues: step.visual_cues.map((c) => c.trim()).filter(Boolean) })} />
            </label>
            <label className="field">
              <span>How it looks once done <em>(judged from a single still frame)</em></span>
              <input className="input" value={step.completion_state ?? ""}
                onChange={(e) => patch(selected, { completion_state: e.target.value })} />
            </label>
            <label className="check">
              <input type="checkbox" checked={step.state_is_monotone ?? true}
                onChange={(e) => patch(selected, { state_is_monotone: e.target.checked })} />
              Stays that way for the rest of the procedure
              <span className="muted"> — untick if a later step undoes it (a template is removed, the piece is flipped back)</span>
            </label>

            <div className="editor-foot">
              <button className="btn btn-small btn-danger" onClick={() => remove(selected)} disabled={steps.length <= 1}>
                Remove step
              </button>
            </div>
          </div>
        ) : <div className="card muted">Add a step to begin.</div>}

        <figure className="card manual-page">
          {page ? (
            <>
              <img src={api.pageUrl(job.id, page)} alt={`Manual page ${page}`} />
              <figcaption>Manual page {page} — look for bold number {step?.step_id}</figcaption>
            </>
          ) : (
            <p className="muted">No manual page set for this step. Pick one so the model also sees the drawing.</p>
          )}
        </figure>
      </div>
    </div>
  );
}

function validate(steps: Step[]): string[] {
  const out: string[] = [];
  const ids = steps.map((s) => s.step_id);
  if (steps.length === 0) out.push("Add at least one step");
  if (new Set(ids).size !== ids.length) out.push("Step numbers must be unique");
  if (ids.some((n) => !Number.isInteger(n) || n < 1)) out.push("Step numbers must be whole numbers from 1");
  const unnamed = steps.filter((s) => !s.name.trim()).map((s) => s.step_id);
  if (unnamed.length) out.push(`Name step${unnamed.length > 1 ? "s" : ""} ${unnamed.join(", ")}`);
  return out;
}
