import { useEffect, useState } from "react";
import { api, type CameraProfileOut, type SystemInfo } from "../lib/api";
import { bytes } from "../lib/format";

const BLANK: Omit<CameraProfileOut, "id"> = {
  slug: "",
  name: "",
  detection_rules: { dirs: [], files: [], exif_make: "" },
  dest_template: "{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}",
};

export default function SettingsPage() {
  const [profiles, setProfiles] = useState<CameraProfileOut[]>([]);
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [editing, setEditing] = useState<string | null>(null);   // slug being edited or "" for new
  const [draft, setDraft] = useState<Omit<CameraProfileOut, "id">>(BLANK);
  const [rulesText, setRulesText] = useState<string>("{}");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [p, i] = await Promise.all([api.cameraProfiles(), api.info()]);
    setProfiles(p);
    setInfo(i);
  }

  useEffect(() => { refresh().catch(console.error); }, []);

  function startEdit(p: CameraProfileOut) {
    setEditing(p.slug);
    setDraft({ slug: p.slug, name: p.name, detection_rules: p.detection_rules, dest_template: p.dest_template });
    setRulesText(JSON.stringify(p.detection_rules, null, 2));
    setError(null);
  }

  function startNew() {
    setEditing("");
    setDraft(BLANK);
    setRulesText(JSON.stringify(BLANK.detection_rules, null, 2));
    setError(null);
  }

  function cancel() {
    setEditing(null);
    setError(null);
  }

  async function save() {
    setError(null);
    let rules: Record<string, unknown>;
    try {
      rules = JSON.parse(rulesText);
    } catch (e) {
      setError(`Invalid JSON in detection rules: ${(e as Error).message}`);
      return;
    }
    if (!draft.slug.trim()) { setError("slug is required"); return; }
    if (!draft.name.trim()) { setError("name is required"); return; }
    try {
      await api.upsertProfile(draft.slug, { ...draft, detection_rules: rules });
      setEditing(null);
      refresh();
    } catch (e) {
      setError(`Save failed: ${(e as Error).message}`);
    }
  }

  async function remove(slug: string) {
    if (slug === "unknown") { alert("'unknown' is the fallback profile and cannot be deleted"); return; }
    if (!window.confirm(`Delete camera profile '${slug}'? Past imports keep their assignment.`)) return;
    await api.deleteProfile(slug);
    refresh();
  }

  return (
    <div className="p-8 space-y-8">
      <header>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted text-sm">Camera profiles, destination, system info.</p>
      </header>

      <section className="panel p-5">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted mb-3">System</h2>
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <KV label="Destination" value={info?.destination_root ?? "—"} />
          <KV label="Default template" value={info?.default_template ?? "—"} />
          <KV label="DB" value={info?.db_path ?? "—"} />
          <KV label="Free space" value={info?.destination_free_bytes != null ? bytes(info.destination_free_bytes) : "—"} />
          <KV label="Eject from UI" value={info?.host_agent_configured ? "enabled" : "disabled (set SDOFFLOAD_HOST_AGENT_URL)"} />
          <KV label="Notifications" value={info?.notify_configured ? "enabled" : "disabled (set SDOFFLOAD_NOTIFY_URL)"} />
        </dl>
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wider text-muted">Camera profiles</h2>
          <button className="btn btn-accent" onClick={startNew}>+ New profile</button>
        </div>

        {editing !== null && (
          <ProfileForm
            isNew={editing === ""}
            draft={draft}
            setDraft={setDraft}
            rulesText={rulesText}
            setRulesText={setRulesText}
            error={error}
            onSave={save}
            onCancel={cancel}
          />
        )}

        {profiles.map((p) => (
          <div key={p.id} className="panel p-4">
            <div className="flex items-baseline justify-between gap-3">
              <div className="min-w-0">
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted font-mono">{p.slug}</div>
              </div>
              <div className="flex items-center gap-2">
                <code className="text-xs bg-bg px-2 py-1 rounded truncate max-w-md">{p.dest_template}</code>
                <button className="btn" onClick={() => startEdit(p)}>Edit</button>
                {p.slug !== "unknown" && (
                  <button className="btn btn-danger" onClick={() => remove(p.slug)}>Delete</button>
                )}
              </div>
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

function ProfileForm({
  isNew, draft, setDraft, rulesText, setRulesText, error, onSave, onCancel,
}: {
  isNew: boolean;
  draft: Omit<CameraProfileOut, "id">;
  setDraft: (d: Omit<CameraProfileOut, "id">) => void;
  rulesText: string;
  setRulesText: (s: string) => void;
  error: string | null;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="panel p-5 border-accent/40">
      <h3 className="font-medium mb-3">{isNew ? "New camera profile" : `Editing '${draft.slug}'`}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field label="Slug (lowercase, no spaces)" disabled={!isNew}>
          <input value={draft.slug} disabled={!isNew}
            onChange={(e) => setDraft({ ...draft, slug: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") })}
            className="input" placeholder="e.g. dji_mavic_3" />
        </Field>
        <Field label="Display name">
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            className="input" placeholder="e.g. DJI Mavic 3" />
        </Field>
        <Field label="Destination template" full>
          <input value={draft.dest_template} onChange={(e) => setDraft({ ...draft, dest_template: e.target.value })}
            className="input font-mono" />
          <div className="text-[11px] text-muted mt-1">
            Variables: {"{camera_slug}"}, {"{captured:%Y}"}, {"{captured:%Y-%m-%d}"}, {"{original_name}"}, {"{original_stem}"}, {"{original_ext}"}, {"{device_label}"}, {"{device_uuid}"}
          </div>
        </Field>
        <Field label="Detection rules (JSON)" full>
          <textarea value={rulesText} onChange={(e) => setRulesText(e.target.value)}
            rows={8} className="input font-mono text-xs" />
          <div className="text-[11px] text-muted mt-1">
            Keys: <code>dirs</code> (glob like <code>DCIM/*MEDIA</code>), <code>files</code> (e.g. <code>DJI_*.MP4</code>), <code>exif_make</code> (substring), <code>exif_model</code>.
          </div>
        </Field>
      </div>
      {error && <div className="text-xs text-rose-300 mt-3">{error}</div>}
      <div className="flex justify-end gap-2 mt-4">
        <button className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-accent" onClick={onSave}>Save</button>
      </div>
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

function Field({ label, children, disabled, full }: {
  label: string; children: React.ReactNode; disabled?: boolean; full?: boolean;
}) {
  return (
    <div className={full ? "sm:col-span-2" : ""}>
      <label className={`text-xs uppercase tracking-wider ${disabled ? "text-muted/60" : "text-muted"}`}>{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
