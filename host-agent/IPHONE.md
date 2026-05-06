# iPhone / iOS support

The iPhone is not a block device — it speaks **AFC** (Apple File Conduit) over USB, exposed by `usbmuxd`. We mount the photo library with `ifuse` (FUSE filesystem) and treat the resulting mount like any other camera source.

## One-time host setup

```bash
apt install -y libimobiledevice-utils ifuse usbmuxd fuse
systemctl enable --now usbmuxd

# Allow non-root access to /dev/fuse for the mount (already default on Debian 12).
# If the agent fails with "fusermount: user has no write access to /etc/fuse.conf",
# add `user_allow_other` to /etc/fuse.conf.

# Connect the iPhone over USB. The phone shows a "Trust This Computer?" dialog — Trust it.
# Then pair persistently:
idevicepair pair

# Verify:
idevice_id -l            # should print the UDID
idevicename -u <UDID>    # should print the iPhone's name
```

## Install the iPhone udev rule

```bash
cp /opt/sdoffload/host-agent/udev/99-sdoffload-iphone.rules /etc/udev/rules.d/
udevadm control --reload-rules
```

## How it works

1. iPhone plugged in → udev fires (Apple vendor 05ac)
2. `sdoffload-agent attach-iphone <UDID>` runs:
   - `idevice_id -l` confirms the phone is paired & visible
   - `ifuse -o ro,allow_other -u <UDID> /mnt/sdoffload/iphone-<short>`
   - Notifies the backend (LXC) — same flow as an SD card
3. Backend scans `/mnt/sdoffload/iphone-<short>/DCIM/100APPLE/`, detects "iphone" profile, deduplicates, copies HEIC/MOV/JPG to destination.

The iPhone profile (`slug=iphone`) is seeded automatically.

## Caveats

- HEIC thumbnails work because `pillow-heif` is in the Docker image.
- HEIC playback in browser requires Safari, or Chrome with the HEIC extension. Original download always works.
- iPhone exposes only DCIM (camera roll), not Photos.app albums or iCloud-only photos.
- If you reboot the host, you might need to replug the iPhone (usbmuxd usually handles this fine).
- Multi-iPhone is supported — each gets its own `iphone-<udid8>` mount.

## Troubleshooting

```bash
# What does udev see when you plug in the iPhone?
udevadm monitor --property --subsystem-match=usb

# Manual mount test:
mkdir -p /tmp/iphone-test
ifuse -u <UDID> /tmp/iphone-test
ls /tmp/iphone-test/DCIM/
fusermount -u /tmp/iphone-test

# Manual agent test:
sdoffload-agent attach-iphone <UDID>
journalctl -t sdoffload-agent -n 30
```
