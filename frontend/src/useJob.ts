import { useEffect, useState } from "react";
import { api, Job } from "./api";

type JobEvent =
  | { type: "snapshot"; job: Job }
  | { type: "status"; status: Job["status"]; error: string | null }
  | { type: "progress"; stage: string; done: number | null; total: number | null }
  | { type: "chunks"; chunks: Job["chunks"]; duration: number }
  | ({ type: "row" } & Job["rows"][string])
  | { type: "report"; report: NonNullable<Job["report"]> };

/**
 * Keeps one job in sync with the server.
 *
 * The server sends a full snapshot on every (re)connect, then small events. EventSource
 * reconnects by itself after a network blip, and the fresh snapshot resyncs anything missed.
 */
export function useJob(id: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    let closed = false;
    const source = new EventSource(`/api/jobs/${id}/events`);

    source.onopen = () => setLive(true);
    source.onerror = () => {
      setLive(false);
      // A 404 closes the stream for good; tell the user instead of spinning forever.
      if (source.readyState === EventSource.CLOSED && !closed) {
        api.job(id).catch((e: Error) => setError(e.message));
      }
    };

    source.onmessage = (msg) => {
      const event = JSON.parse(msg.data) as JobEvent;
      if (event.type === "snapshot") {
        setJob(event.job);
        setError(null);
        return;
      }
      if (event.type === "status") {
        // Status changes can carry large payloads (a drafted SOP, a report) that the event
        // itself omits, so fetch the whole job once.
        api.job(id).then((j) => !closed && setJob(j)).catch(() => {});
      }
      setJob((prev) => (prev ? applyEvent(prev, event) : prev));
    };

    return () => {
      closed = true;
      source.close();
    };
  }, [id]);

  return { job, setJob, error, live };
}

function applyEvent(job: Job, event: JobEvent): Job {
  switch (event.type) {
    case "status":
      return { ...job, status: event.status, error: event.error };
    case "progress":
      return { ...job, progress: { stage: event.stage, done: event.done, total: event.total } };
    case "chunks":
      return { ...job, chunks: event.chunks, duration: event.duration };
    case "row": {
      const { type: _type, ...row } = event;
      return { ...job, rows: { ...job.rows, [String(row.chunk)]: row } };
    }
    case "report":
      return { ...job, report: event.report, summary: event.report.summary };
    default:
      return job;
  }
}
