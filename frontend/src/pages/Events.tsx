import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type EventOut } from "../lib/api";

const LEVELS = ["", "info", "warn", "error", "debug"] as const;

export default function Events() {
  const [events, setEvents] = useState<EventOut[]>([]);
  const [sources, setSources] = useState<string[]>([]);
  const [level, setLevel] = useState<string>("");
  const [source, setSource] = useState<string>("");

  async function refresh() {
    const [e, src] = await Promise.all([
      api.events({ level: level || undefined, source: source || undefined, limit: 300 }),
      api.eventSources(),
    ]);
    setEvents(e);
    setSources(src);
  }

  useEffect(() => {
    refresh().catch(console.error);
    const t = setInterval(() => refresh().catch(console.error), 4000);
    return () => clearInterval(t);
  }, [level, source]);

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Events</h1>
          <p className="text-muted text-sm">Activity log across all components.</p>
        </div>
        <div className="flex gap-2 text-sm">
          <select value={level} onChange={(e) => setLevel(e.target.value)}
            className="bg-panel border border-border rounded-lg px-3 py-1.5">
            {LEVELS.map((l) => <option key={l} value={l}>{l || "all levels"}</option>)}
          </select>
          <select value={source} onChange={(e) => setSource(e.target.value)}
            className="bg-panel border border-border rounded-lg px-3 py-1.5">
            <option value="">all sources</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </header>

      <div className="panel divide-y divide-border">
        {events.length === 0 && <div className="p-6 text-muted text-sm">No events.</div>}
        {events.map((e) => (
          <div key={e.id} className="p-3 flex items-start gap-4 text-sm">
            <span className={levelClass(e.level)}>{e.level}</span>
            <span className="text-xs text-muted w-44 shrink-0 font-mono">
              {new Date(e.ts).toLocaleString()}
            </span>
            <span className="text-xs text-muted w-20 shrink-0 font-mono">{e.source}</span>
            <div className="flex-1 min-w-0">
              <div>{e.message}</div>
              {e.data && (
                <pre className="text-[11px] text-muted mt-1 truncate">{JSON.stringify(e.data)}</pre>
              )}
            </div>
            <div className="flex gap-2 shrink-0 text-xs">
              {e.import_id && <Link to={`/imports/${e.import_id}`} className="text-accent">#{e.import_id}</Link>}
              {e.device_id && <span className="text-muted">dev {e.device_id}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function levelClass(level: string) {
  const map: Record<string, string> = {
    info: "pill pill-pending",
    warn: "pill pill-running",
    error: "pill pill-failed",
    debug: "pill pill-paused",
  };
  return map[level] || "pill";
}
