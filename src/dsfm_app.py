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
        self._active_count = 0
        self._lock = threading.Lock()

        self.status_item = rumps.MenuItem("○  Waiting for controller…")

        self.menu = [
            self.status_item,
            None,
            rumps.MenuItem("Activate Now", callback=self.activate_now),
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
        def _update():
            self.status_item.title = ("●  " if active else "○  ") + text
            img = _sf(_SYM_ACTIVE if active else _SYM_INACTIVE)
            self._icon_nsimage = img
            try:
                self._nsapp.nsstatusitem.setImage_(img)
            except AttributeError:
                pass
        if threading.current_thread() is threading.main_thread():
            _update()
        else:
            from Foundation import NSOperationQueue
            NSOperationQueue.mainQueue().addOperationWithBlock_(_update)

    # ── IOKit watcher callbacks ────────────────────────────────────────────────
    # Activation is done inside the watcher (via IOHIDDeviceGetReport on the
    # service ref) before these are called, so all we do here is update the UI.

    def _on_iokit_activated(self) -> None:
        with self._lock:
            self._active_count += 1
        log.info("Controller activated (total active: %d)", self._active_count)
        self._set_status("Full input active", active=True)
        rumps.notification(
            "DualSense for Mac",
            "Controller ready",
            "Full input unlocked — touchpad, gyro, and all buttons available.",
            sound=False,
        )

    def _on_device_disappeared(self) -> None:
        with self._lock:
            if self._active_count > 0:
                self._active_count -= 1
            empty = self._active_count == 0
        log.info("Controller removed (total active: %d)", self._active_count)
        if empty:
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
                self._set_status("Full input active", active=True)
                rumps.notification(
                    "DualSense for Mac",
                    "Controller ready",
                    "Full input unlocked — touchpad, gyro, and all buttons available.",
                    sound=False,
                )
            else:
                self._set_status("Activation failed — is Steam holding the lock?")

    def quit(self, _=None) -> None:
        os._exit(0)


if __name__ == "__main__":
    App().run()
