import { useEffect, useState } from "react";
import { api, type CameraProfileOut } from "../lib/api";

export default function SettingsPage() {
  const [profiles, setProfiles] = useState<CameraProfileOut[]>([]);
  const [info, setInfo] = useState<{ destination_root: string; default_template: string; db_path: string } | null>(null);

  useEffect(() => {
    Promise.all([api.cameraProfiles(), api.info()])
      .then(([p, i]) => { setProfiles(p); setInfo(i); })
      .catch(console.error);
  }, []);

  return (
    <div className="p-8 space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted text-sm">Camera profiles, destination, dedup. Edit on disk for now — UI editing coming.</p>
      </header>

      <section className="panel p-5">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted mb-3">System</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <KV label="Destination" value={info?.destination_root ?? "—"} />
          <KV label="Default template" value={info?.default_template ?? "—"} />
          <KV label="DB" value={info?.db_path ?? "—"} />
        </dl>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted">Camera profiles</h2>
        {profiles.map((p) => (
          <div key={p.id} className="panel p-4">
            <div className="flex items-baseline justify-between">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted font-mono">{p.slug}</div>
              </div>
              <code className="text-xs bg-bg px-2 py-1 rounded">{p.dest_template}</code>
            </div>
            <pre className="mt-3 text-xs text-muted overflow-x-auto">
{JSON.stringify(p.detection_rules, null, 2)}
            </pre>
          </div>
        ))}
      </section>
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-mono text-xs break-all">{value}</dd>
    </div>
  );
}
