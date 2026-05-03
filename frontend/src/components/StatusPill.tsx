import type { ImportOut } from "../lib/api";

const cls: Record<ImportOut["status"], string> = {
  pending: "pill pill-pending",
  scanning: "pill pill-running",
  copying: "pill pill-running",
  done: "pill pill-done",
  failed: "pill pill-failed",
  cancelled: "pill pill-failed",
};

export default function StatusPill({ status }: { status: ImportOut["status"] }) {
  return <span className={cls[status]}>{status}</span>;
}
