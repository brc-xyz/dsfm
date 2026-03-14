#!/usr/bin/env python3
"""
DSFM — DualSense for Mac
Menu bar app. Auto mode runs on launch.
"""
import logging
import os
import sys
import threading
import time

import rumps

logging.basicConfig(level=logging.WARNING)
logging.getLogger("dsfm").setLevel(logging.WARNING)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsfm as core


def _icon(name: str) -> str:
    """Resolve icon path for both bundled (.app) and dev (source) contexts."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "..", "Resources", name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "icons", name)


ICON_ACTIVE   = _icon("icon_menubar_active.png")
ICON_INACTIVE = _icon("icon_menubar_inactive.png")


class App(rumps.App):
    def __init__(self):
        super().__init__("DSFM", icon=ICON_INACTIVE, quit_button=None, template=True)

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

        threading.Thread(target=self._auto_loop, daemon=True).start()

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, text: str, active: bool = False) -> None:
        self.status_item.title = ("●  " if active else "○  ") + text
        self.icon = ICON_ACTIVE if active else ICON_INACTIVE

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
        if self._auto:
            threading.Thread(target=self._auto_loop, daemon=True).start()
            self._set_status("Waiting for controller…")
        else:
            self._set_status("Auto-activate off")

    def quit(self, _=None) -> None:
        os._exit(0)

    def _auto_loop(self) -> None:
        while self._auto:
            devices = core.find_target_devices(self.target_pids)

            for d in devices:
                key = d.get("serial_number") or d.get("path", "")
                with self._lock:
                    already = key in self._activated
                if not already:
                    if core.activate_enhanced_mode(d):
                        with self._lock:
                            self._activated.add(key)
                        self._set_status("Full input active", active=True)
                        rumps.notification(
                            "DualSense for Mac",
                            "Controller ready",
                            "Full input unlocked — touchpad, gyro, and all buttons available.",
                            sound=False,
                        )

            current = {d.get("serial_number") or d.get("path", "") for d in devices}
            with self._lock:
                gone = self._activated - current
                self._activated -= gone

            if gone and not self._activated:
                self._set_status("Waiting for controller…")

            time.sleep(2)


if __name__ == "__main__":
    App().run()
