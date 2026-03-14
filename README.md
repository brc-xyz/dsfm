# DSFM — DualSense for Mac

Unlock the full input surface of your PS5 controller on macOS over Bluetooth.

By default, DualSense and DualSense Edge controllers connect in a limited mode
that only exposes sticks, triggers, face buttons, and D-Pad. **Touchpad, gyro,
back buttons, and FN buttons are invisible** to macOS and any app running on it

DSFM fixes this silently and automatically. No Steam required. No remapping.

---

## How it works

Sending a `GET Feature Report 0x05` (IMU calibration request) to the controller
causes it to switch from limited mode (Report `0x01`) to enhanced mode
(Report `0x31`, full input surface). The mode persists in hardware until the
controller is power-cycled or Bluetooth drops.

---

## Requirements

- macOS Sonoma, Sequoia, or Tahoe
- Python 3.9+
- `hidapi` — `pip3 install hidapi`

---

## Install

```bash
git clone https://github.com/alex-brc/dsfm.git
cd dsfm
bash build_and_install.sh
```

This builds `DSFM.app`, installs it to `/Applications`, and registers a
LaunchAgent so it starts automatically at login.

To uninstall:

```bash
bash uninstall.sh
```

---

## Usage

**Menu bar app (recommended)**

After install, DSFM runs in the menu bar. Connect your controller over
Bluetooth — it activates automatically. The icon shows current state.

**Command line**

```bash
# One-shot activation
python3 dsfm.py

# Auto mode — stay running, activate on every connect and reconnect
python3 dsfm.py --auto

# DualSense Edge only
python3 dsfm.py --edge-only

# Verbose output
python3 dsfm.py -v
```

---

## Supported controllers

| Controller | VID | PID |
|---|---|---|
| DualSense Edge | `0x054C` | `0x0DF2` |
| DualSense | `0x054C` | `0x0CE6` |

---

## Known limitations

- **Steam conflict** — If Steam is running with PS Controller Support enabled,
  it may hold an exclusive lock on the controller. Quit Steam and retry.
- The mode resets on every power cycle or Bluetooth reconnect — DSFM's auto
  mode handles this transparently.

---

## License

[PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal,
non-commercial use.
