# DualSense for Mac

Unlock the full input surface of your PS5 controller on macOS over Bluetooth.

By default, DualSense and DualSense Edge controllers connect in a limited mode
that only exposes sticks, triggers, face buttons, and D-Pad. **Touchpad, gyro,
back buttons, and FN buttons are invisible** to macOS and any app running on it.

DualSense for Mac fixes this silently and automatically. No Steam required. No remapping.

[My tech blog on this app →](https://brc.xyz/projects/001-dualsense-for-mac/)

## Supported controllers

| Controller | VID | PID |
|---|---|---|
| DualSense Edge | `0x054C` | `0x0DF2` |
| DualSense | `0x054C` | `0x0CE6` |

## How it works

Sending a `GET Feature Report 0x05` (IMU calibration request) to the controller
causes it to switch from limited mode (Report `0x01`) to enhanced mode
(Report `0x31`, full input surface). The mode persists in hardware until the
controller is power-cycled or Bluetooth drops.

## Install

```bash
brew tap brc-xyz/dsfm
brew install --cask dsfm
```

Launch DualSense for Mac from Spotlight or Applications. Connect your controller
over Bluetooth — it activates automatically. Each connected controller appears
as a menu item with a checkmark when in enhanced mode.

To uninstall:

```bash
brew uninstall --cask dsfm
```

## Requirements

macOS Sonoma, Sequoia, or Tahoe.

## Known limitations

- **Steam conflict** — If Steam is running with PS Controller Support enabled,
  it may hold an exclusive lock on the controller. Quit Steam and retry.
- **World of Warcraft — touchpad after reconnect** — WoW initializes
  DualSense-specific inputs once at first connection. If the controller
  reconnects mid-session, the touchpad may stop responding. Create a macro
  with `/console gamepadEnable 0` on the first line and
  `/console gamepadEnable 1` on the second to reset WoW's controller state.

## Version history

**0.3.1** — Bundle hidapi dependency; drop CLI; clean up README.

**0.3.0** — Multi-controller support. Each connected DualSense or DualSense
Edge appears as its own menu item, activated automatically and shown with a
checkmark for visual confirmation. Renamed to DualSense for Mac.

**0.2.0** — IOKit-native connect detection. Controller connections are now
detected via `IOServiceAddMatchingNotification` and enhanced mode is activated
directly from the IOKit service ref — no polling, no sleeps. UI updates are
dispatched to the main thread. New app and menu bar icons. Added WoW touchpad
workaround to docs.

**0.1.1** — New app and menu bar icons. Removed launch agent (app must be
started manually or added to Login Items).

**0.1.0** — Initial release.

## License

[MIT](LICENSE)
