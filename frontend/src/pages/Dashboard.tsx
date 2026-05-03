import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, openProgressSocket, type DeviceOut, type ImportOut, type Stats } from "../lib/api";
import { bytes, pct, relTime } from "../lib/format";
import StatusPill from "../components/StatusPill";
import ImportControls from "../components/ImportControls";

export default function Dashboard() {
  const [devices, setDevices] = useState<DeviceOut[]>([]);
  const [active, setActive] = useState<ImportOut[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<ImportOut[]>([]);

  async function refresh() {
    const [d, a, s, r] = await Promise.all([api.devices(), api.activeImports(), api.stats(), api.imports()]);
    setDevices(d);
    setActive(a);
    setStats(s);
    setRecent(r.slice(0, 8));
  }

  useEffect(() => {
    refresh().catch(console.error);
    const t = setInterval(() => refresh().catch(console.error), 5000);
    const close = openProgressSocket(() => refresh().catch(console.error));
    return () => { clearInterval(t); close(); };
  }, []);

  return (
    <div className="p-8 space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted text-sm">Live overview of devices and imports.</p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat label="Files in library" value={stats ? stats.total_files.toLocaleString() : "—"} />
        <Stat label="Storage used" value={stats ? bytes(stats.total_bytes) : "—"} />
        <Stat label="Devices known" value={String(devices.length)} />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wider">Active imports</h2>
        {active.length === 0 ? (
          <div className="panel p-6 text-muted text-sm">No imports running. Connect a card or camera.</div>
        ) : (
          <div className="space-y-3">
            {active.map((imp) => <ActiveCard key={imp.id} imp={imp} onChange={refresh} />)}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wider">Devices</h2>
        <div className="panel divide-y divide-border">
          {devices.length === 0 && <div className="p-6 text-muted text-sm">No devices yet.</div>}
          {devices.map((d) => (
            <div key={d.id} className="p-4 flex items-center gap-4">
              <div className="flex-1">
                <div className="font-medium">{d.label || d.fs_uuid || `device #${d.id}`}</div>
                <div className="text-xs text-muted">
                  {d.fs_type || "?"} · {bytes(d.size_bytes ?? 0)} ·
                  {" "}{d.detected_camera ? d.detected_camera.name : "unknown camera"}
                </div>
              </div>
              <div className="text-xs text-muted">last seen {relTime(d.last_seen)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-muted uppercase tracking-wider">Recent imports</h2>
        <div className="panel divide-y divide-border">
          {recent.length === 0 && <div className="p-6 text-muted text-sm">Nothing imported yet.</div>}
          {recent.map((imp) => (
            <Link key={imp.id} to={`/imports/${imp.id}`} className="p-4 flex items-center gap-4 hover:bg-border/30">
              <StatusPill status={imp.status} />
              <div className="flex-1">
                <div className="text-sm">
                  #{imp.id} · {imp.camera_profile?.name || "—"} · {imp.files_new}/{imp.files_total} files
                </div>
                <div className="text-xs text-muted">{relTime(imp.started_at)} · {imp.mount_path}</div>
              </div>
              <div className="text-xs text-muted">{bytes(imp.bytes_copied)}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel p-5">
      <div className="text-muted text-xs uppercase tracking-wider">{label}</div>
      <div className="text-3xl font-semibold mt-1">{value}</div>
    </div>
  );
}

function ActiveCard({ imp, onChange }: { imp: ImportOut; onChange: () => void }) {
  const processed = imp.files_new + imp.files_skipped + imp.files_failed;
  const filePct = pct(processed, imp.files_total);
  const bytePct = pct(imp.bytes_copied, imp.bytes_total);
  return (
    <Link to={`/imports/${imp.id}`} className="panel p-4 block hover:border-accent/40">
      <div className="flex items-center gap-4">
        <StatusPill status={imp.status} />
        <div className="flex-1 min-w-0">
          <div className="font-medium">
            {imp.camera_profile?.name || "Detecting…"} · #{imp.id}
          </div>
          <div className="text-xs text-muted truncate">{imp.mount_path}</div>
        </div>
        <div className="text-right text-xs">
          <div>{processed} / {imp.files_total} files</div>
          <div className="text-muted">{bytes(imp.bytes_copied)} / {bytes(imp.bytes_total)}</div>
        </div>
        <ImportControls imp={imp} onChange={onChange} size="sm" />
      </div>
      <div className="mt-3 h-1.5 rounded-full bg-border overflow-hidden">
        <div className="h-full bg-accent transition-all" style={{ width: `${Math.max(filePct, bytePct)}%` }} />
      </div>
    </Link>
  );
}
