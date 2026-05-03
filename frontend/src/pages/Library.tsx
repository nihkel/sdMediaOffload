import { useEffect, useMemo, useState } from "react";
import { api, type CameraProfileOut, type MediaFileOut } from "../lib/api";
import { bytes } from "../lib/format";

export default function Library() {
  const [profiles, setProfiles] = useState<CameraProfileOut[]>([]);
  const [files, setFiles] = useState<MediaFileOut[]>([]);
  const [camera, setCamera] = useState<string>("");
  const [year, setYear] = useState<number | "">("");
  const [preview, setPreview] = useState<MediaFileOut | null>(null);

  useEffect(() => { api.cameraProfiles().then(setProfiles).catch(console.error); }, []);

  useEffect(() => {
    api.files({ camera: camera || undefined, year: year || undefined, limit: 240 })
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
          <p className="text-muted text-sm">All imported media. Click any tile to preview.</p>
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
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider mb-3">
            {date} <span className="text-muted">· {items.length}</span>
          </h2>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
            {items.map((f) => <Tile key={f.id} file={f} onClick={() => setPreview(f)} />)}
          </div>
        </section>
      ))}

      {preview && <Lightbox file={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}

function Tile({ file, onClick }: { file: MediaFileOut; onClick: () => void }) {
  const isVideo = file.mime_type?.startsWith("video/");
  return (
    <button onClick={onClick}
      className="group relative aspect-square overflow-hidden rounded-lg bg-border hover:ring-2 hover:ring-accent transition">
      <img
        src={`/api/files/${file.id}/thumb`}
        alt={file.original_name}
        loading="lazy"
        className="absolute inset-0 w-full h-full object-cover"
        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
      {isVideo && (
        <div className="absolute bottom-1 right-1 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded">
          ▶ video
        </div>
      )}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-1.5
                      opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="text-[10px] font-mono text-white truncate">{file.original_name}</div>
      </div>
    </button>
  );
}

function Lightbox({ file, onClose }: { file: MediaFileOut; onClose: () => void }) {
  const isVideo = file.mime_type?.startsWith("video/");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={onClose}>
      <div className="max-w-6xl max-h-full flex flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between text-sm">
          <div>
            <div className="font-mono">{file.original_name}</div>
            <div className="text-xs text-muted">
              {file.exif_model || "—"}
              {file.captured_at && <> · {new Date(file.captured_at).toLocaleString()}</>}
              {file.width && file.height && <> · {file.width}×{file.height}</>}
              <> · {bytes(file.size_bytes)}</>
            </div>
          </div>
          <div className="flex gap-2">
            <a className="btn" href={`/api/files/${file.id}/raw`} target="_blank" rel="noreferrer">Open original</a>
            <button className="btn" onClick={onClose}>Close (Esc)</button>
          </div>
        </div>
        <div className="bg-panel rounded-lg overflow-hidden flex items-center justify-center">
          {isVideo ? (
            <video src={`/api/files/${file.id}/raw`} controls autoPlay
                   className="max-h-[80vh] max-w-full" />
          ) : (
            <img src={`/api/files/${file.id}/raw`} alt={file.original_name}
                 className="max-h-[80vh] max-w-full object-contain" />
          )}
        </div>
      </div>
    </div>
  );
}
