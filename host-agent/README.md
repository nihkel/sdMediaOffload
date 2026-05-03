# sdoffload-agent

Pequeño servicio Python que corre en el **host de Proxmox**. Cuando udev detecta una tarjeta SD o cámara montada, invoca al agente, que:

1. Lee UUID/label/serial del dispositivo (`blkid`, `udevadm`).
2. Monta read-only en `/mnt/sdoffload/<uuid>`.
3. POST a la VM (`/api/host/device-attached`) con un token compartido.
4. Cuando se desconecta, desmonta y avisa.

## Instalación en Proxmox

```bash
# 1. Copia los archivos al host
scp -r host-agent/ root@proxmox:/opt/sdoffload-agent/

# 2. En el host
ssh root@proxmox
cd /opt/sdoffload-agent
pip install -e .
ln -sf /usr/local/bin/sdoffload-agent /usr/local/bin/sdoffload-agent

# 3. udev + systemd
cp udev/99-sdoffload.rules /etc/udev/rules.d/
cp systemd/sdoffload-agent.service /etc/systemd/system/
udevadm control --reload-rules
systemctl daemon-reload
systemctl enable --now sdoffload-agent

# 4. Configuración
cat > /etc/default/sdoffload-agent <<EOF
SDOFFLOAD_VM_URL=http://10.0.0.50:8000
SDOFFLOAD_TOKEN=$(openssl rand -hex 32)
SDOFFLOAD_MOUNT_BASE=/mnt/sdoffload
EOF
mkdir -p /mnt/sdoffload
```

Pon ese mismo token en el backend (`SDOFFLOAD_HOST_TOKEN` en el `.env` o en la unidad systemd de la VM).

## Cómo accede la VM a los archivos montados

Dos opciones:

### A) NFS (recomendado)
Exporta `/mnt/sdoffload` desde el host y móntalo en la VM en el mismo path. Así el `mount_path` que envía el agente es válido tal cual desde la VM.

```bash
# Host
apt install nfs-kernel-server
echo "/mnt/sdoffload  10.0.0.50(ro,sync,no_subtree_check,no_root_squash)" >> /etc/exports
exportfs -ra

# VM
mount -t nfs proxmox:/mnt/sdoffload /mnt/sdoffload
```

### B) virtiofs (Proxmox 8+)
Configura un `mp` con virtiofs en la VM apuntando a `/mnt/sdoffload`. Más eficiente que NFS pero requiere apagar la VM para añadir el mount.

## Debug

```bash
# Probar manualmente con una partición conocida
sdoffload-agent attach /dev/sda1

# Ver eventos de udev en tiempo real
udevadm monitor --property --subsystem-match=block

# Logs del agente (van a syslog porque udev lo lanza)
journalctl -t sdoffload-agent -f
```
