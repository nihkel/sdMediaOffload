import { useEffect, useMemo, useState } from "react";
import { api, type CameraProfileOut, type MediaFileOut } from "../lib/api";
import { bytes } from "../lib/format";

export default function Library() {
  const [profiles, setProfiles] = useState<CameraProfileOut[]>([]);
  const [files, setFiles] = useState<MediaFileOut[]>([]);
  const [camera, setCamera] = useState<string>("");
  const [year, setYear] = useState<number | "">("");

  useEffect(() => { api.cameraProfiles().then(setProfiles).catch(console.error); }, []);

  useEffect(() => {
    api.files({ camera: camera || undefined, year: year || undefined, limit: 200 })
      .then(setFiles).catch(console.error);
  }, [camera, year]);

  const groups = useMemo(() => {
    const m = new Map<string, MediaFileOut[]>();
    for (const f of files) {
      const d = f.captured_at ? f.captured_at.slice(0, 10) : "Unknown";
      if (!m.has(d)) m.set(d, []);
      m.get(d)!.push(f);
    }
    return [...m.entries()].sort(([a], [b]) => (a < b ? 1 : -1));
  }, [files]);

  const years = useMemo(() => {
    const s = new Set<number>();
    files.forEach((f) => f.captured_at && s.add(new Date(f.captured_at).getFullYear()));
    return [...s].sort((a, b) => b - a);
  }, [files]);

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Library</h1>
          <p className="text-muted text-sm">All imported media, grouped by capture date.</p>
        </div>
        <div className="flex gap-2 text-sm">
          <select value={camera} onChange={(e) => setCamera(e.target.value)}
            className="bg-panel border border-border rounded-lg px-3 py-1.5">
            <option value="">All cameras</option>
            {profiles.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
          </select>
          <select value={year} onChange={(e) => setYear(e.target.value ? Number(e.target.value) : "")}
            className="bg-panel border border-border rounded-lg px-3 py-1.5">
            <option value="">All years</option>
            {years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
      </header>

      {groups.length === 0 && <div className="panel p-6 text-muted text-sm">No files in library yet.</div>}

      {groups.map(([date, items]) => (
        <section key={date}>
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-2">
            {date} <span className="text-muted">· {items.length}</span>
          </h2>
          <div className="panel divide-y divide-border">
            {items.map((f) => (
              <div key={f.id} className="p-3 flex items-center gap-4 text-sm">
                <div className="flex-1">
                  <div className="font-mono text-xs">{f.original_name}</div>
                  <div className="text-xs text-muted truncate">{f.dest_path}</div>
                </div>
                <div className="text-xs text-muted whitespace-nowrap">{f.exif_model || "—"}</div>
                {(f.width && f.height) && (
                  <div className="text-xs text-muted whitespace-nowrap">{f.width}×{f.height}</div>
                )}
                <div className="text-xs w-20 text-right">{bytes(f.size_bytes)}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
