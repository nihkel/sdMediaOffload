import type { ImportStatus } from "../lib/api";

const cls: Record<ImportStatus, string> = {
  pending: "pill pill-pending",
  scanning: "pill pill-running",
  copying: "pill pill-running",
  paused: "pill pill-paused",
  done: "pill pill-done",
  failed: "pill pill-failed",
  cancelled: "pill pill-failed",
};

export default function StatusPill({ status }: { status: ImportStatus }) {
  return <span className={cls[status]}>{status}</span>;
}
