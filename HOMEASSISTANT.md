# Home Assistant integration

SD Media Offload exposes everything Home Assistant needs over plain REST + WebSocket and ships with a wall-tablet-friendly kiosk view for embedding.

- **Kiosk URL** — `http://<lxc-ip>:8999/kiosk`  (clean, full-bleed, auto-refreshing every 2s)
- **HA-friendly summary endpoint** — `GET /api/settings/ha-summary` (one call, everything HA needs)
- **iframe-embeddable** — backend sets `Content-Security-Policy: frame-ancestors *`

## 1. Embed the dashboard in HA (iframe)

In HA, **Settings → Dashboards → Edit Dashboard → + ADD CARD → Webpage**:

```yaml
type: iframe
url: http://10.0.40.14:8999/kiosk
aspect_ratio: 16:9
```

For a **full-screen panel** (the entire HA dashboard tab is the iframe — perfect for the wall tablet):

```yaml
# in your dashboards YAML (or via UI: Edit dashboard → Add view → Type: Panel)
views:
  - title: SD Offload
    path: sd-offload
    icon: mdi:sd
    panel: true
    cards:
      - type: iframe
        url: http://10.0.40.14:8999/kiosk
```

> **Auth tip**: if you set `SDOFFLOAD_UI_PASSWORD`, the tablet must log in once at `http://10.0.40.14:8999/kiosk` directly so the cookie is set. Then the iframe in HA will reuse it (browser sends cookies for our origin from the iframe). The cookie lasts 7 days.
>
> For a hands-off wall display, **leave `SDOFFLOAD_UI_PASSWORD` empty** — the LXC is on your private LAN.

## 2. Surface stats as HA sensors

Add to `configuration.yaml`:

```yaml
rest:
  - resource: http://10.0.40.14:8999/api/settings/ha-summary
    scan_interval: 5
    sensor:
      - name: "SD Offload Status"
        value_template: "{{ value_json.overall_status }}"
        json_attributes_path: "$"
        json_attributes:
          - progress_pct
          - active_import
          - destination_root
          - destination_free_human
        icon: mdi:sd
      - name: "SD Offload Progress"
        value_template: "{{ value_json.progress_pct }}"
        unit_of_measurement: "%"
        state_class: measurement
      - name: "SD Offload Library Files"
        value_template: "{{ value_json.library_total_files }}"
        unit_of_measurement: files
        state_class: measurement
      - name: "SD Offload Library Size"
        value_template: "{{ (value_json.library_total_bytes / 1024**3) | round(1) }}"
        unit_of_measurement: "GB"
        state_class: measurement
      - name: "SD Offload Free Space"
        value_template: "{{ (value_json.destination_free_bytes / 1024**3) | round(1) if value_json.destination_free_bytes else 0 }}"
        unit_of_measurement: "GB"
        state_class: measurement
      - name: "SD Offload Devices Known"
        value_template: "{{ value_json.devices_count }}"
        state_class: measurement
```

After a HA restart you'll have:
- `sensor.sd_offload_status` — `idle` / `copying` / `paused` / etc.
- `sensor.sd_offload_progress` — 0–100
- `sensor.sd_offload_library_files`, `sensor.sd_offload_library_size`, `sensor.sd_offload_free_space`, `sensor.sd_offload_devices_known`

The `active_import` object is exposed as an attribute of `sd_offload_status` so you can drill in:

```yaml
{{ state_attr('sensor.sd_offload_status', 'active_import').camera }}
```

## 3. Trigger actions from HA (pause / resume / eject)

```yaml
rest_command:
  sd_offload_pause:
    url: "http://10.0.40.14:8999/api/imports/{{ import_id }}/pause"
    method: post
  sd_offload_resume:
    url: "http://10.0.40.14:8999/api/imports/{{ import_id }}/resume"
    method: post
  sd_offload_cancel:
    url: "http://10.0.40.14:8999/api/imports/{{ import_id }}/cancel"
    method: post
  sd_offload_retry:
    url: "http://10.0.40.14:8999/api/imports/{{ import_id }}/retry"
    method: post
  sd_offload_eject:
    url: "http://10.0.40.14:8999/api/devices/{{ device_id }}/eject"
    method: post
```

Use them in automations:

```yaml
# Example: pause the active import when you say "Hey Google, pause photos"
- alias: Pause SD Offload
  trigger:
    - platform: conversation
      command: ["pause photo offload"]
  action:
    - service: rest_command.sd_offload_pause
      data:
        import_id: "{{ state_attr('sensor.sd_offload_status', 'active_import').id }}"
```

## 4. Notifications via HA (alternative to ntfy)

Skip `SDOFFLOAD_NOTIFY_URL` and use HA's automations on state change:

```yaml
- alias: SD Offload finished notify
  trigger:
    - platform: state
      entity_id: sensor.sd_offload_status
      to: "idle"
      from: ["copying", "scanning", "pending"]
  action:
    - service: notify.mobile_app_my_phone
      data:
        title: "SD Offload"
        message: >
          Done · {{ state_attr('sensor.sd_offload_status', 'active_import').files_new
                    if state_attr('sensor.sd_offload_status', 'active_import')
                    else state.attributes.library_total_files }} files
```

## 5. Lovelace card showing only key stats (no iframe)

If you want a compact native HA card instead of the full kiosk:

```yaml
type: vertical-stack
cards:
  - type: glance
    title: SD Offload
    entities:
      - entity: sensor.sd_offload_status
        name: Status
      - entity: sensor.sd_offload_progress
        name: Progress
      - entity: sensor.sd_offload_library_files
        name: Files
      - entity: sensor.sd_offload_free_space
        name: Free GB
  - type: gauge
    entity: sensor.sd_offload_progress
    min: 0
    max: 100
    severity:
      green: 80
      yellow: 30
      red: 0
```

## 6. Tablet wall-mount tips (21" landscape)

### HA "Kiosk Mode" plugin
Install via HACS. Hides the HA top bar/sidebar so the iframe takes the full screen.

```yaml
kiosk_mode:
  hide_sidebar: true
  hide_header: true
```

### Always-on display
On a Fire HD / Lenovo Tab / Galaxy Tab:
- Install **Fully Kiosk Browser** (€) or **WallPanel** (free)
- URL: `http://homeassistant.local:8123/lovelace/sd-offload`
- Enable: Auto-launch on boot, Keep screen on, Hide system bars

### Direct kiosk (no HA)
If you don't want the HA wrapper, just point the tablet's browser to:
```
http://10.0.40.14:8999/kiosk
```
Use Fully Kiosk Browser pointing here directly. Shorter latency, no iframe overhead.

### Recommended Fully Kiosk settings
- **Web zoom**: 100% (the kiosk view scales font with viewport)
- **Brightness**: dim 20% at night via HA automation:
  ```yaml
  - service: rest_command.fully_kiosk_brightness
    data:
      brightness: "{{ 50 if now().hour >= 22 or now().hour < 7 else 220 }}"
  ```
- **Motion-activated wake**: bring screen to full brightness when someone walks past (PIR sensor).

## 7. Troubleshooting iframe embedding

If HA shows "refused to connect" or a blank iframe:

```bash
# Verify the headers
curl -I http://10.0.40.14:8999/kiosk
# Should include: Content-Security-Policy: frame-ancestors *
# Should NOT include: X-Frame-Options: DENY|SAMEORIGIN
```

If you proxy the LXC via HAProxy/nginx/caddy, make sure the proxy doesn't strip the CSP header or inject a stricter X-Frame-Options.

## 8. URLs cheat sheet

| Purpose | URL |
|---|---|
| Full UI | `http://10.0.40.14:8999/` |
| Kiosk (iframe / wall) | `http://10.0.40.14:8999/kiosk` |
| HA summary JSON | `http://10.0.40.14:8999/api/settings/ha-summary` |
| Active imports | `http://10.0.40.14:8999/api/imports/active` |
| Health | `http://10.0.40.14:8999/api/health` |
| OpenAPI docs | `http://10.0.40.14:8999/docs` |
