# SD Media Offload

Sistema automático de offload de tarjetas SD y dispositivos media (GoPro, Sony, DJI, etc.) conectados al host Proxmox. Detecta el dispositivo, identifica la cámara, copia los archivos nuevos a un destino montado en la VM, y mantiene una base de datos con todas las importaciones para evitar duplicados. Los originales nunca se tocan.

## Arquitectura

```
┌──────────────────────────────────────┐         ┌──────────────────────────────────────┐
│            Proxmox host              │         │              VM (LXC/QEMU)           │
│                                      │         │                                      │
│  udev → host-agent (systemd)         │  HTTP   │  FastAPI backend                     │
│    · detecta block device            │ ──────► │    · /api/host/device-attached       │
│    · monta read-only en /mnt/sdoff/  │         │    · scan + dedup + copia            │
│    · exporta vía NFS read-only ──────┼───NFS──►│    · SQLite (registro permanente)    │
│    · notifica al backend             │         │    · WebSocket → progreso en vivo    │
│                                      │         │                                      │
└──────────────────────────────────────┘         │  React frontend (Vite)               │
                                                 │    · Dashboard, Imports, Library     │
                                                 └──────────────────────────────────────┘
                                                                │
                                                                ▼
                                                  /mnt/media (destino, p.ej. NAS NFS)
                                                  └─ {camera}/{YYYY}/{YYYY-MM-DD}/...
```

### Por qué este split

- **Host hace lo mínimo**: udev + montaje read-only + NFS export. No tiene Python pesado, no tiene DB. Si la VM está caída, el host solo guarda la tarjeta montada y reintenta.
- **VM hace todo el trabajo**: hash, dedup, copia, EXIF, frontend, DB. Si quieres mover la VM a otra máquina, todo el estado va con ella.
- **Sin USB passthrough**: el lector SD del Proxmox sigue siendo del host. Conectar una cámara nueva o cambiar de lector no requiere reconfigurar la VM.

## Componentes

### `host-agent/`
Servicio Python pequeño en el host Proxmox.
- Regla udev dispara cuando se conecta un block device removible.
- Monta read-only en `/mnt/sdoffload/<uuid>`.
- POST a `http://<vm>:8000/api/host/device-attached` con metadatos.
- Cuando se desconecta, POST a `/api/host/device-detached` y desmonta.

### `backend/`
FastAPI + SQLite.
- Recibe eventos del host-agent.
- Encola un job de importación.
- Worker async escanea, detecta cámara, calcula hash parcial, deduplica, copia.
- Expone REST + WebSocket.

### `frontend/`
React + Vite + TypeScript + Tailwind.
- Dashboard: dispositivos activos, importación en curso con progreso live.
- Imports: histórico paginado, drill-down a detalle de cada import.
- Library: navegador de archivos importados, agrupados por fecha/cámara.
- Settings: perfiles de cámara, ruta destino, plantilla de organización.

## Modelo de datos (resumen)

- **`devices`**: cada tarjeta/cámara que se ha conectado alguna vez (clave: `fs_uuid` + `serial`).
- **`camera_profiles`**: GoPro, Sony A6000, DJI Mavic Mini, etc. Reglas de detección y plantilla de destino.
- **`imports`**: cada vez que se conecta un dispositivo se crea una fila. Estado: `pending → scanning → copying → done|failed|cancelled`.
- **`media_files`**: archivos importados. Clave de dedup: `(partial_hash, size_bytes, original_name)`.
- **`import_skips`**: archivos saltados (duplicados, errores) con motivo.
- **`events`**: log estructurado para el frontend.

### Dedup (hash parcial)

Para ficheros >8MB: SHA256 de `first_4MB ‖ last_4MB ‖ size_bytes`. Para ficheros menores, hash completo. Es ~100× más rápido que hash completo en vídeos 4K y la probabilidad de colisión es despreciable. La clave única en DB es `(partial_hash, size_bytes, original_name)`, así que un GX010001.MP4 con mismo hash parcial y mismo tamaño cuenta como ya importado aunque venga de otra tarjeta.

## Flujo de una importación

1. Conectas SD al lector del Proxmox.
2. udev → `sdoffload-agent` monta `/mnt/sdoffload/<uuid>` read-only y avisa al backend.
3. Backend crea fila en `devices` (o reutiliza por `fs_uuid`) y `imports` con estado `pending`.
4. Worker:
   - **scan**: walk del árbol, identifica cámara por estructura de directorios y EXIF.
   - **plan**: por cada archivo calcula `partial_hash` y consulta `media_files`. Si existe → `import_skips` con razón `duplicate`. Si no → cola de copia.
   - **copy**: lee EXIF para fecha de captura, resuelve destino con la plantilla, copia con verificación. Inserta en `media_files`. Actualiza progreso vía WebSocket.
5. Cuando termina, `imports.status = done`. Desconectas la SD y el host-agent desmonta.

## Plantilla de destino

Por defecto: `{camera_slug}/{captured:%Y}/{captured:%Y-%m-%d}/{original_name}`

Variables disponibles:
- `camera_slug` — `gopro`, `sony_a6000`, `dji_mavic_mini`, `unknown`
- `captured` — datetime de captura (EXIF; fallback mtime)
- `original_name`, `original_stem`, `original_ext`
- `device_label`, `device_uuid`

Configurable por perfil de cámara en `Settings`.

## Estado actual (Phase 1)

- [x] Esqueleto del proyecto
- [x] Modelos DB y migraciones
- [x] Endpoints `/api/host/*` para que el host avise
- [x] Detección de cámara (reglas + EXIF)
- [x] Hash parcial y dedup
- [x] Worker de importación
- [x] Host-agent con udev + systemd
- [x] Frontend base (Dashboard)
- [ ] Frontend completo (Imports detail, Library, Settings) — Phase 2
- [ ] WebSocket de progreso live — Phase 2
- [ ] Generación de thumbnails — Phase 2
- [x] Soporte iPhone/MTP (vía libimobiledevice + ifuse — ver [host-agent/IPHONE.md](host-agent/IPHONE.md))

## Despliegue con Docker

El `Dockerfile` es multi-stage: primero compila el frontend (Vite) y luego empaqueta el backend Python con el bundle estático servido en la misma URL. **Una imagen, un puerto, todo dentro.** El `host-agent` NO se dockeriza — vive en el host de Proxmox porque necesita udev y montar dispositivos reales.

### Producción (un solo comando)

```bash
cp .env.example .env
# Edita .env: pon un SDOFFLOAD_HOST_TOKEN seguro y rutas reales
docker compose up -d --build
```

UI + API en `http://<host>:8000`. La DB persiste en `./data/sdoffload.db` (volumen). Los archivos importados van a la ruta que configures en `SDOFFLOAD_DESTINATION_PATH`.

### Desarrollo (hot reload, sin Python local)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

- Backend: uvicorn con `--reload`, bind-mount sobre `./backend` → cambios en Python recargan al instante.
- Frontend: contenedor Node con `vite dev` en `:5173`, proxy `/api` → backend container.

Abre `http://localhost:5173`.

### Test rápido sin Proxmox

Para probar el flujo completo con archivos locales (simulando una SD):

```bash
mkdir -p mock-source/DCIM/100GOPRO
# copia algún .jpg o .mp4 ahí dentro
docker compose up -d
curl -X POST http://localhost:8000/api/host/device-attached \
  -H "Content-Type: application/json" \
  -H "X-Host-Token: $(grep SDOFFLOAD_HOST_TOKEN .env | cut -d= -f2)" \
  -d '{"fs_uuid":"test-uuid-001","label":"TESTSD","fs_type":"vfat","mount_path":"/mnt/sdoffload"}'
```

Mira el Dashboard en `http://localhost:8000` — verás el dispositivo, la importación y los archivos copiados a `./media/`.

## Despliegue en Proxmox

### Topología recomendada

```
Proxmox host
├─ host-agent (systemd + udev) — sin Docker
├─ NFS server exporta /mnt/sdoffload (read-only) a la VM
└─ VM/LXC con Docker
   └─ docker-compose stack con la app
       ├─ /mnt/sdoffload  ← NFS mount desde el host
       └─ /data/media     ← NFS desde tu NAS o dataset Proxmox
```

### Pasos

**En el host Proxmox** (instala el agente + NFS):

```bash
# 1. Copia y instala el host-agent
scp -r host-agent/ root@proxmox:/opt/sdoffload-agent/
ssh root@proxmox
cd /opt/sdoffload-agent && pip install -e . --break-system-packages
cp udev/99-sdoffload.rules /etc/udev/rules.d/
cp systemd/sdoffload-agent.service /etc/systemd/system/
udevadm control --reload-rules
systemctl daemon-reload && systemctl enable --now sdoffload-agent

# 2. Configura el agente
cat > /etc/default/sdoffload-agent <<EOF
SDOFFLOAD_VM_URL=http://<vm-ip>:8000
SDOFFLOAD_TOKEN=<el-mismo-token-que-en-la-VM>
SDOFFLOAD_MOUNT_BASE=/mnt/sdoffload
EOF
mkdir -p /mnt/sdoffload

# 3. Exporta /mnt/sdoffload por NFS hacia la VM
apt install -y nfs-kernel-server
echo "/mnt/sdoffload  <vm-ip>(ro,sync,no_subtree_check,no_root_squash,fsid=42)" >> /etc/exports
exportfs -ra
```

**En la VM con Docker**:

```bash
# 1. Monta el NFS del host
apt install -y nfs-common
mkdir -p /mnt/sdoffload
echo "<proxmox-ip>:/mnt/sdoffload  /mnt/sdoffload  nfs  ro,_netdev  0  0" >> /etc/fstab
mount -a

# 2. Despliega la app
git clone <este-repo> /opt/sdoffload && cd /opt/sdoffload
cp .env.example .env
# edita .env:
#   SDOFFLOAD_HOST_TOKEN=<el-mismo-token>
#   SDOFFLOAD_SOURCE_PATH=/mnt/sdoffload
#   SDOFFLOAD_DESTINATION_PATH=/mnt/photos    (tu NAS)
docker compose up -d --build
```

**Listo**. Conecta una SD al lector del Proxmox → udev → host-agent monta + notifica → backend importa por NFS → ves todo en la UI en `:8000`.

## Desarrollo del host-agent (avanzado)

Si quieres modificar el agente, en el host Proxmox:

```bash
sdoffload-agent attach /dev/sda1   # simula manualmente
udevadm monitor --property --subsystem-match=block   # observa eventos
journalctl -t sdoffload-agent -f                     # logs
```
