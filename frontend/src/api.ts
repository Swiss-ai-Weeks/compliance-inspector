// Types mirror the JSON the FastAPI backend returns (backend/jobs.py, backend/report.py).

export type JobStatus = "ingesting" | "authoring" | "awaiting_review" | "analyzing" | "done" | "error";
export type StepStatus = "verified" | "likely" | "out_of_order" | "unclear" | "not_observed";

export interface Step {
  step_id: number;
  name: string;
  description: string;
  visual_cues: string[];
  completion_state?: string;
  state_is_monotone?: boolean;
  manual_reference?: string | null;
}

export interface Sop {
  task_name: string;
  total_manual_steps?: number;
  expected_steps: Step[];
}

export interface StepResult {
  step_id: number;
  name: string;
  status: StepStatus;
  confidence: number;
  start: number | null;
  end: number | null;
  state_at: number | null;
  score: number;
  signals: ("action" | "state")[];
  evidence: string[];
  start_label: string;
  end_label: string;
  state_label: string;
}

export interface Summary {
  total_steps: number;
  observed_steps: number;
  correct_steps: number;
  verified_steps: number;
  out_of_order_steps: number;
  unclear_steps?: number[];
  missed_steps: number[];
  coverage: number;
  compliance: number;
}

export interface Chunk {
  index: number;
  start: number;
  end: number;
  label: string;
}

export interface Row {
  chunk: number;
  scores: number[];
  best_step: number | null;
  best_score: number;
  activity: string;
}

export interface Progress {
  stage: string;
  done: number | null;
  total: number | null;
}

export interface Job {
  id: string;
  created_at: number;
  status: JobStatus;
  error: string | null;
  product_name: string | null;
  duration: number | null;
  page_count: number;
  sop: Sop | null;
  step_pages: Record<string, number>;
  author_model: string | null;
  warnings: string[];
  progress: Progress | null;
  chunks: Chunk[];
  rows: Record<string, Row>;
  report: { steps: StepResult[]; summary: Summary; detect_mode: string; model: string; elapsed_s: number } | null;
  summary: Summary | null;
}

export interface JobListItem {
  id: string;
  created_at: number;
  status: JobStatus;
  product_name: string | null;
  summary: Summary | null;
}

export interface Product {
  id: string;
  name: string;
  category: string | null;
  steps: number;
  video: string;
}

export interface Health {
  nim: { ok: boolean; models?: string[]; error?: string };
  video_model: string;
  detect_mode: string;
  author_model: string | null;
  author_hosted: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* not JSON: keep the status line */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  products: () => request<Product[]>("/api/products"),
  jobs: () => request<JobListItem[]>("/api/jobs"),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  createJob: (form: FormData) => request<Job>("/api/jobs", { method: "POST", body: form }),
  confirmSop: (id: string, sop: Sop, stepPages: Record<string, number>) =>
    request<Job>(`/api/jobs/${id}/sop`, {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ ...sop, step_pages: stepPages }),
    }),
  videoUrl: (id: string) => `/api/jobs/${id}/media/video`,
  pageUrl: (id: string, page: number) => `/api/jobs/${id}/media/page/${page}`,
};

export function mmss(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  const s = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
