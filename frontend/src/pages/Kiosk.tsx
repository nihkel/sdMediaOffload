import { useEffect, useState } from "react";
import { api, openProgressSocket, type DeviceOut, type ImportOut, type Stats, type SystemInfo } from "../lib/api";
import { bytes, pct, relTime } from "../lib/format";
import StatusPill from "../components/StatusPill";

/**
 * Wall-mounted tablet view. Large fonts, big touch targets, dark theme,
 * auto-refresh every 2s. Designed for 1920x1080+ landscape displays
 * (21" tablets typically render at 1920x1200 or higher).
 *
 * Embed inside Home Assistant via:
 *   type: iframe
 *   url: http://<lxc-ip>:8999/kiosk
 */
export default function Kiosk() {
  const [devices, setDevices] = useState<DeviceOut[]>([]);
  const [active, setActive] = useState<ImportOut[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [recent, setRecent] = useState<ImportOut[]>([]);
  const [now, setNow] = useState(new Date());

  async function refresh() {
    const [d, a, s, r, i] = await Promise.all([
      api.devices(), api.activeImports(), api.stats(), api.imports(), api.info(),
    ]);
    setDevices(d);
    setActive(a);
    setStats(s);
    setRecent(r.slice(0, 4));
    setInfo(i);
  }

  useEffect(() => {
    refresh().catch(console.error);
    const t = setInterval(() => { refresh().catch(console.error); setNow(new Date()); }, 2000);
    const close = openProgressSocket(() => refresh().catch(console.error));
    return () => { clearInterval(t); close(); };
  }, []);

  const headlineImport = active[0];
  const headlinePct = headlineImport
    ? pct(headlineImport.files_new + headlineImport.files_skipped + headlineImport.files_failed,
          headlineImport.files_total)
    : 0;

  return (
    <div className="kiosk min-h-screen text-slate-100 p-6 lg:p-10">
      <header className="flex items-baseline justify-between mb-6 lg:mb-10">
        <div>
          <div className="text-muted text-xs lg:text-sm uppercase tracking-widest">SD Media Offload</div>
          <h1 className="text-3xl lg:text-5xl font-semibold mt-1">
            {headlineImport
              ? <>Importing — <span className="text-accent">{headlinePct}%</span></>
              : devices.length > 0
                ? <>Idle — {devices.length} device{devices.length !== 1 ? "s" : ""} known</>
                : <>Ready</>}
          </h1>
        </div>
        <div className="text-right">
          <div className="text-3xl lg:text-5xl font-mono">{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
          <div className="text-xs lg:text-sm text-muted mt-1">{now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</div>
        </div>
      </header>

      {/* Active import — full width, prominent */}
      {headlineImport && (
        <section className="kiosk-panel p-6 lg:p-10 mb-6 lg:mb-10">
          <div className="flex items-center gap-4 mb-5">
            <StatusPill status={headlineImport.status} />
            <div className="flex-1">
              <div className="text-2xl lg:text-3xl font-semibold">
                {headlineImport.camera_profile?.name || "Detecting…"}
              </div>
              <div className="text-muted text-sm lg:text-base mt-1 truncate">{headlineImport.mount_path}</div>
            </div>
            <div className="text-right">
              <div className="text-3xl lg:text-5xl font-semibold">
                {headlineImport.files_new + headlineImport.files_skipped + headlineImport.files_failed}
                <span className="text-muted text-xl lg:text-2xl"> / {headlineImport.files_total}</span>
              </div>
              <div className="text-muted text-sm lg:text-base mt-1">
                {bytes(headlineImport.bytes_copied)} / {bytes(headlineImport.bytes_total)}
              </div>
            </div>
          </div>

          <div className="h-3 lg:h-4 rounded-full bg-border overflow-hidden">
            <div className="h-full bg-accent transition-all duration-500" style={{ width: `${headlinePct}%` }} />
          </div>

          <div className="grid grid-cols-3 gap-4 mt-6 text-center">
            <Mini value={headlineImport.files_new} label="New" tone="accent" />
            <Mini value={headlineImport.files_skipped} label="Skipped" />
            <Mini value={headlineImport.files_failed} label="Failed" tone={headlineImport.files_failed ? "warn" : undefined} />
          </div>
        </section>
      )}

      {/* Stats grid */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6 mb-6 lg:mb-10">
        <BigStat label="Files in library" value={stats ? stats.total_files.toLocaleString() : "—"} />
        <BigStat label="Storage used" value={stats ? bytes(stats.total_bytes) : "—"} />
        <BigStat label="Devices" value={String(devices.length)} />
        <BigStat
          label="Free space"
          value={info?.destination_free_bytes != null ? bytes(info.destination_free_bytes) : "—"}
          sub={info?.destination_total_bytes
            ? `${pct(info.destination_used_bytes ?? 0, info.destination_total_bytes)}% used`
            : undefined}
        />
      </section>

      {/* Devices + recent — two columns on landscape */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10">
        <div>
          <h2 className="text-sm lg:text-base text-muted uppercase tracking-widest mb-3">Devices</h2>
          <div className="kiosk-panel divide-y divide-border">
            {devices.length === 0 && <div className="p-5 text-muted">No devices yet.</div>}
            {devices.slice(0, 4).map((d) => (
              <div key={d.id} className="p-4 lg:p-5 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-lg lg:text-xl font-medium truncate">
                    {d.label || d.fs_uuid || `#${d.id}`}
                  </div>
                  <div className="text-xs lg:text-sm text-muted truncate">
                    {d.detected_camera ? d.detected_camera.name : "unknown"} · {bytes(d.size_bytes ?? 0)}
                  </div>
                </div>
                <div className="text-xs lg:text-sm text-muted whitespace-nowrap">{relTime(d.last_seen)}</div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-sm lg:text-base text-muted uppercase tracking-widest mb-3">Recent</h2>
          <div className="kiosk-panel divide-y divide-border">
            {recent.length === 0 && <div className="p-5 text-muted">No imports yet.</div>}
            {recent.map((imp) => (
              <div key={imp.id} className="p-4 lg:p-5 flex items-center gap-4">
                <StatusPill status={imp.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-base lg:text-lg truncate">
                    #{imp.id} · {imp.camera_profile?.name || "—"}
                  </div>
                  <div className="text-xs lg:text-sm text-muted">
                    {imp.files_new} new · {bytes(imp.bytes_copied)} · {relTime(imp.started_at)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function BigStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="kiosk-panel p-5 lg:p-6">
      <div className="text-xs lg:text-sm text-muted uppercase tracking-widest">{label}</div>
      <div className="text-3xl lg:text-5xl font-semibold mt-1.5">{value}</div>
      {sub && <div className="text-xs lg:text-sm text-muted mt-1">{sub}</div>}
    </div>
  );
}

function Mini({ value, label, tone }: { value: number; label: string; tone?: "accent" | "warn" }) {
  const color = tone === "accent" ? "text-accent" : tone === "warn" ? "text-rose-300" : "text-slate-100";
  return (
    <div>
      <div className={`text-2xl lg:text-4xl font-semibold ${color}`}>{value.toLocaleString()}</div>
      <div className="text-xs lg:text-sm text-muted uppercase tracking-widest mt-1">{label}</div>
    </div>
  );
}
