import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ImportOut } from "../lib/api";
import { bytes, relTime } from "../lib/format";
import StatusPill from "../components/StatusPill";

const FILTERS = ["all", "pending", "scanning", "copying", "done", "failed"] as const;

export default function Imports() {
  const [imports, setImports] = useState<ImportOut[]>([]);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");

  useEffect(() => {
    api.imports(filter === "all" ? undefined : filter).then(setImports).catch(console.error);
  }, [filter]);

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Imports</h1>
          <p className="text-muted text-sm">Every offload operation, with drill-down.</p>
        </div>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs ${filter === f ? "bg-border text-white" : "text-muted hover:bg-border/40"}`}
            >
              {f}
            </button>
          ))}
        </div>
      </header>

      <div className="panel divide-y divide-border">
        {imports.length === 0 && <div className="p-6 text-muted text-sm">No imports.</div>}
        {imports.map((imp) => (
          <Link key={imp.id} to={`/imports/${imp.id}`} className="p-4 flex items-center gap-4 hover:bg-border/30">
            <div className="w-16 text-xs text-muted">#{imp.id}</div>
            <StatusPill status={imp.status} />
            <div className="flex-1">
              <div className="text-sm">{imp.camera_profile?.name || "—"} · {imp.device?.label || imp.device?.fs_uuid || `device #${imp.device_id}`}</div>
              <div className="text-xs text-muted">{imp.mount_path}</div>
            </div>
            <div className="text-right text-xs">
              <div>{imp.files_new} new · {imp.files_skipped} skip · {imp.files_failed} fail</div>
              <div className="text-muted">{bytes(imp.bytes_copied)} · {relTime(imp.started_at)}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
