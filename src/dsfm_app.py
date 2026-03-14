#!/usr/bin/env python3
"""
DSFM — DualSense for Mac
Menu bar app. Auto mode runs on launch.
"""
import logging
import os
import sys
import threading

import rumps
from AppKit import NSImage

_log_path = os.path.expanduser("~/Library/Logs/dsfm.log")
logging.basicConfig(
    level=logging.DEBUG,
    filename=_log_path,
    filemode="a",
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("dsfm").setLevel(logging.DEBUG)
log = logging.getLogger("dsfm.app")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsfm as core

_SYM_ACTIVE   = "xmark.triangle.circle.square.fill"
_SYM_INACTIVE = "xmark.triangle.circle.square"


def _sf(symbol: str) -> NSImage:
    return NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)



class App(rumps.App):
    def __init__(self):
        super().__init__("DSFM", quit_button=None)
        self._icon_nsimage = _sf(_SYM_INACTIVE)

        self.target_pids = {core.DS_EDGE_PID, core.DS_STD_PID}
        self._activated: set = set()
        self._auto = True
        self._lock = threading.Lock()

        self.status_item = rumps.MenuItem("○  Waiting for controller…")
        self.auto_item   = rumps.MenuItem("Auto-activate", callback=self.toggle_auto)
        self.auto_item.state = 1

        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Activate Now", callback=self.activate_now),
            self.auto_item,
            None,
            rumps.MenuItem("Quit", callback=self.quit),
        ]

        # IOKit watcher: fires on kIOFirstMatchNotification (device ready) and
        # kIOTerminatedNotification (device removed). Handles already-connected
        # devices at launch by draining the initial iterator.
        core.start_iokit_hid_watcher(
            self.target_pids,
            self._on_iokit_activated,
            self._on_device_disappeared,
        )

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, text: str, active: bool = False) -> None:
        self.status_item.title = ("●  " if active else "○  ") + text
        img = _sf(_SYM_ACTIVE if active else _SYM_INACTIVE)
        self._icon_nsimage = img
        try:
            self._nsapp.nsstatusitem.setImage_(img)
        except AttributeError:
            pass

    # ── IOKit watcher callback ─────────────────────────────────────────────────

    def _on_iokit_activated(self) -> None:
        devices = core.find_target_devices(self.target_pids)
        for d in devices:
            key = d.get("serial_number") or d.get("path", "")
            with self._lock:
                already = key in self._activated
            if already:
                continue
            if core.activate_enhanced_mode(d):
                with self._lock:
                    self._activated.add(key)
                log.info("Enhanced mode active: %s", core.device_label(d))
                self._set_status("Full input active", active=True)
                rumps.notification(
                    "DualSense for Mac",
                    "Controller ready",
                    "Full input unlocked — touchpad, gyro, and all buttons available.",
                    sound=False,
                )

    # ── BT disconnect handler ─────────────────────────────────────────────────

    def _on_device_disappeared(self) -> None:
        current = {d.get("serial_number") or d.get("path", "")
                   for d in core.find_target_devices(self.target_pids)}
        with self._lock:
            gone = self._activated - current
            self._activated -= gone
        if gone:
            log.info("Deactivated: %s", gone)
        if not self._activated:
            self._set_status("Waiting for controller…")

    # ── Activate Now ──────────────────────────────────────────────────────────

    def activate_now(self, _=None) -> None:
        threading.Thread(target=self._do_activate, daemon=True).start()

    def _do_activate(self) -> None:
        self._set_status("Activating…")
        devices = core.find_target_devices(self.target_pids)
        if not devices:
            self._set_status("No controller found")
            return
        for d in devices:
            if core.activate_enhanced_mode(d):
                key = d.get("serial_number") or d.get("path", "")
                with self._lock:
                    self._activated.add(key)
                self._set_status("Full input active", active=True)
                rumps.notification(
                    "DualSense for Mac",
                    "Controller ready",
                    "Full input unlocked — touchpad, gyro, and all buttons available.",
                    sound=False,
                )
            else:
                self._set_status("Activation failed — is Steam holding the lock?")

    # ── Auto-activate ─────────────────────────────────────────────────────────

    def toggle_auto(self, sender) -> None:
        self._auto = not self._auto
        sender.state = 1 if self._auto else 0
        if not self._auto:
            self._set_status("Auto-activate off")

    def quit(self, _=None) -> None:
        os._exit(0)


if __name__ == "__main__":
    App().run()
