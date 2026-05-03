import { useState } from "react";
import { api, type ImportOut } from "../lib/api";

type Props = {
  imp: ImportOut;
  onChange?: () => void;
  size?: "sm" | "md";
};

export default function ImportControls({ imp, onChange, size = "md" }: Props) {
  const [busy, setBusy] = useState(false);

  async function act(fn: () => Promise<unknown>, confirmMsg?: string) {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusy(true);
    try {
      await fn();
      onChange?.();
    } catch (e) {
      alert(`Action failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  const isRunning = ["pending", "scanning", "copying"].includes(imp.status);
  const isPaused = imp.status === "paused";
  const canRetry = imp.status === "failed" || imp.status === "cancelled";
  const sizeCls = size === "sm" ? "text-[11px] px-2 py-1" : "";

  return (
    <div className="flex gap-1.5" onClick={(e) => e.stopPropagation()}>
      {isRunning && (
        <>
          <button className={`btn ${sizeCls}`} disabled={busy}
                  onClick={() => act(() => api.pauseImport(imp.id))}>Pause</button>
          <button className={`btn btn-danger ${sizeCls}`} disabled={busy}
                  onClick={() => act(() => api.cancelImport(imp.id),
                    "Cancel this import? Already-copied files stay on disk.")}>Cancel</button>
        </>
      )}
      {isPaused && (
        <>
          <button className={`btn btn-accent ${sizeCls}`} disabled={busy}
                  onClick={() => act(() => api.resumeImport(imp.id))}>Resume</button>
          <button className={`btn btn-danger ${sizeCls}`} disabled={busy}
                  onClick={() => act(() => api.cancelImport(imp.id),
                    "Cancel this import?")}>Cancel</button>
        </>
      )}
      {canRetry && (
        <button className={`btn btn-accent ${sizeCls}`} disabled={busy}
                onClick={() => act(() => api.retryImport(imp.id))}>Retry</button>
      )}
    </div>
  );
}
