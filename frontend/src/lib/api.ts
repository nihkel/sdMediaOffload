export type DeviceOut = {
  id: number;
  fs_uuid: string | null;
  serial: string | null;
  label: string | null;
  fs_type: string | null;
  size_bytes: number | null;
  detected_camera: CameraProfileOut | null;
  first_seen: string;
  last_seen: string;
};

export type CameraProfileOut = {
  id: number;
  slug: string;
  name: string;
  detection_rules: Record<string, unknown>;
  dest_template: string;
};

export type ImportStatus = "pending" | "scanning" | "copying" | "paused" | "done" | "failed" | "cancelled";

export type ImportOut = {
  id: number;
  device_id: number;
  camera_profile_id: number | null;
  mount_path: string;
  status: ImportStatus;
  files_total: number;
  files_new: number;
  files_skipped: number;
  files_failed: number;
  bytes_total: number;
  bytes_copied: number;
  started_at: string;
  finished_at: string | null;
  error: string | null;
  device?: DeviceOut | null;
  camera_profile?: CameraProfileOut | null;
};

export type MediaFileOut = {
  id: number;
  original_name: string;
  size_bytes: number;
  mime_type: string | null;
  exif_make: string | null;
  exif_model: string | null;
  captured_at: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  dest_path: string;
  imported_at: string;
};

export type EventOut = {
  id: number;
  ts: string;
  level: string;
  source: string;
  message: string;
  import_id: number | null;
  device_id: number | null;
  data: Record<string, unknown> | null;
};

export type Stats = {
  total_files: number;
  total_bytes: number;
  by_camera: { slug: string; count: number }[];
};

const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function send<T>(method: "PUT" | "POST" | "DELETE", path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const api = {
  health: () => get<{ ok: boolean; version: string }>("/health"),
  devices: () => get<DeviceOut[]>("/devices"),
  imports: (status?: string) => get<ImportOut[]>(`/imports${status ? `?status=${status}` : ""}`),
  activeImports: () => get<ImportOut[]>("/imports/active"),
  importById: (id: number) => get<ImportOut>(`/imports/${id}`),
  pauseImport: (id: number) => send<ImportOut>("POST", `/imports/${id}/pause`),
  cancelImport: (id: number) => send<ImportOut>("POST", `/imports/${id}/cancel`),
  resumeImport: (id: number) => send<ImportOut>("POST", `/imports/${id}/resume`),
  retryImport: (id: number) => send<ImportOut>("POST", `/imports/${id}/retry`),
  setImportCamera: (id: number, slug: string) =>
    send<ImportOut>("POST", `/imports/${id}/set-camera/${slug}`),
  reorganizeImport: (id: number) =>
    send<{ moved: number; skipped: number; failed: number; total: number }>("POST", `/imports/${id}/reorganize`),
  listBackups: () => get<BackupEntry[]>("/admin/backups"),
  runBackup: () => send<{ ok: boolean; path: string; size_bytes: number }>("POST", "/admin/backups/run"),
  events: (params: { level?: string; source?: string; device_id?: number; import_id?: number; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.level) qs.set("level", params.level);
    if (params.source) qs.set("source", params.source);
    if (params.device_id) qs.set("device_id", String(params.device_id));
    if (params.import_id) qs.set("import_id", String(params.import_id));
    if (params.limit) qs.set("limit", String(params.limit));
    return get<EventOut[]>(`/events?${qs}`);
  },
  eventSources: () => get<string[]>("/events/sources"),
  importFiles: (id: number) => get<MediaFileOut[]>(`/imports/${id}/files`),
  importSkips: (id: number) =>
    get<{ id: number; original_path: string; reason: string; matched_media_id: number | null; detail: string | null }[]>(
      `/imports/${id}/skips`,
    ),
  files: (params: { camera?: string; year?: number; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.camera) qs.set("camera", params.camera);
    if (params.year) qs.set("year", String(params.year));
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.offset) qs.set("offset", String(params.offset));
    return get<MediaFileOut[]>(`/files?${qs}`);
  },
  stats: () => get<Stats>("/files/stats"),
  cameraProfiles: () => get<CameraProfileOut[]>("/settings/camera-profiles"),
  upsertProfile: (slug: string, body: Omit<CameraProfileOut, "id">) =>
    send<CameraProfileOut>("PUT", `/settings/camera-profiles/${slug}`, body),
  deleteProfile: (slug: string) => send<{ ok: boolean }>("DELETE", `/settings/camera-profiles/${slug}`),
  info: () => get<SystemInfo>("/settings/info"),
  ejectDevice: (id: number) => send<{ ok: boolean; mount_path: string }>("POST", `/devices/${id}/eject`),
};

export type BackupEntry = {
  name: string;
  path: string;
  size_bytes: number;
  mtime: string;
};

export type SystemInfo = {
  destination_root: string;
  default_template: string;
  db_path: string;
  host_agent_configured: boolean;
  notify_configured: boolean;
  destination_free_bytes: number | null;
  destination_total_bytes: number | null;
  destination_used_bytes: number | null;
};

export function openProgressSocket(onMessage: (data: any) => void): () => void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/ws/progress`);
  ws.onmessage = (e) => {
    try {
      onMessage(JSON.parse(e.data));
    } catch {}
  };
  return () => ws.close();
}
