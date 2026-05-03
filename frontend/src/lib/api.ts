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

export type ImportOut = {
  id: number;
  device_id: number;
  camera_profile_id: number | null;
  mount_path: string;
  status: "pending" | "scanning" | "copying" | "done" | "failed" | "cancelled";
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
  info: () => get<{ destination_root: string; default_template: string; db_path: string }>("/settings/info"),
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
