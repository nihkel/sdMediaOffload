import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, openProgressSocket, type ImportOut, type MediaFileOut } from "../lib/api";
import { bytes, pct, relTime } from "../lib/format";
import StatusPill from "../components/StatusPill";
import ImportControls from "../components/ImportControls";

type Skip = { id: number; original_path: string; reason: string; matched_media_id: number | null; detail: string | null };

export default function ImportDetail() {
  const { id } = useParams();
  const importId = Number(id);
  const [imp, setImp] = useState<ImportOut | null>(null);
  const [files, setFiles] = useState<MediaFileOut[]>([]);
  const [skips, setSkips] = useState<Skip[]>([]);
  const [tab, setTab] = useState<"files" | "skipped">("files");

  async function refresh() {
    const [i, f, s] = await Promise.all([
      api.importById(importId), api.importFiles(importId), api.importSkips(importId),
    ]);
    setImp(i); setFiles(f); setSkips(s);
  }

  useEffect(() => {
    refresh().catch(console.error);
    const t = setInterval(() => {
      if (imp && !["pending", "scanning", "copying"].includes(imp.status)) return;
      refresh().catch(console.error);
    }, 2000);
    const close = openProgressSocket((data) => {
      if (data.import_id === importId) refresh().catch(console.error);
    });
    return () => { clearInterval(t); close(); };
  }, [importId]);

  if (!imp) return <div className="p-8 text-muted">Loading…</div>;

  const filePct = pct(imp.files_new + imp.files_skipped + imp.files_failed, imp.files_total);

  return (
    <div className="p-8 space-y-6">
      <Link to="/imports" className="text-xs text-muted hover:text-white">← Imports</Link>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Import #{imp.id}</h1>
          <div className="text-sm text-muted mt-1">
            {imp.camera_profile?.name || "—"} · {imp.device?.label || `device #${imp.device_id}`} ·
            {" "}started {relTime(imp.started_at)}
            {imp.finished_at && <> · finished {relTime(imp.finished_at)}</>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ImportControls imp={imp} onChange={refresh} />
          <StatusPill status={imp.status} />
        </div>
      </header>

      {imp.error && (
        <div className="panel p-4 border-rose-500/40 text-rose-300 text-sm">{imp.error}</div>
      )}

      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Total files" value={imp.files_total.toLocaleString()} />
        <Stat label="New" value={imp.files_new.toLocaleString()} accent />
        <Stat label="Skipped" value={imp.files_skipped.toLocaleString()} />
        <Stat label="Failed" value={imp.files_failed.toLocaleString()} />
      </section>

      <section className="panel p-5 space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">Progress</span>
          <span>{bytes(imp.bytes_copied)} / {bytes(imp.bytes_total)} · {filePct}%</span>
        </div>
        <div className="h-2 rounded-full bg-border overflow-hidden">
          <div className="h-full bg-accent transition-all" style={{ width: `${filePct}%` }} />
        </div>
        <div className="text-xs text-muted">Source: {imp.mount_path}</div>
      </section>

      <section>
        <div className="flex gap-2 mb-3">
          <Tab active={tab === "files"} onClick={() => setTab("files")}>Imported ({files.length})</Tab>
          <Tab active={tab === "skipped"} onClick={() => setTab("skipped")}>Skipped ({skips.length})</Tab>
        </div>
        {tab === "files" ? (
          <div className="panel divide-y divide-border">
            {files.length === 0 && <div className="p-6 text-muted text-sm">No files imported yet.</div>}
            {files.map((f) => (
              <div key={f.id} className="p-3 flex items-center gap-4 text-sm">
                <div className="flex-1">
                  <div className="font-mono text-xs">{f.original_name}</div>
                  <div className="text-xs text-muted truncate">{f.dest_path}</div>
                </div>
                <div className="text-xs text-muted whitespace-nowrap">
                  {f.exif_model || "—"} · {f.captured_at ? new Date(f.captured_at).toLocaleString() : "—"}
                </div>
                <div className="text-xs w-20 text-right">{bytes(f.size_bytes)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="panel divide-y divide-border">
            {skips.length === 0 && <div className="p-6 text-muted text-sm">No skipped files.</div>}
            {skips.map((s) => (
              <div key={s.id} className="p-3 flex items-center gap-4 text-sm">
                <span className="pill pill-pending">{s.reason}</span>
                <div className="flex-1 font-mono text-xs truncate">{s.original_path}</div>
                {s.detail && <div className="text-xs text-muted truncate max-w-xs">{s.detail}</div>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="panel p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${accent ? "text-accent" : ""}`}>{value}</div>
    </div>
  );
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-sm ${active ? "bg-border text-white" : "text-muted hover:bg-border/40"}`}
    >
      {children}
    </button>
  );
}
