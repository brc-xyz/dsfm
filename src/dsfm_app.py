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

# Key assigned by rumps to the first separator added to the menu.
_SEP_KEY = "SeparatorMenuItem_1"


def _sf(symbol: str) -> NSImage:
    return NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)


class App(rumps.App):
    def __init__(self):
        super().__init__("DualSense for Mac", quit_button=None)
        self._icon_nsimage = _sf(_SYM_INACTIVE)

        self.target_pids = {core.DS_EDGE_PID, core.DS_STD_PID}
        self._controllers = {}  # key → MenuItem

        self.error_item = rumps.MenuItem("Could not activate — view log", callback=self._open_log)
        self.error_item._menuitem.setImage_(_sf("exclamationmark.triangle"))
        self.error_item._menuitem.setHidden_(True)

        self.status_item = rumps.MenuItem("No DualSense connected")
        self.status_item._menuitem.setImage_(_sf("zzz"))

        quit_item = rumps.MenuItem("Quit", callback=self.quit)
        quit_item._menuitem.setImage_(_sf("xmark.rectangle"))

        self.menu = [
            self.error_item,
            self.status_item,
            None,       # separator — always above Quit; controllers inserted before this
            quit_item,
        ]

        core.start_iokit_hid_watcher(
            self.target_pids,
            self._on_iokit_activated,
            self._on_device_disappeared,
            self._on_iokit_error,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _run_on_main(self, fn):
        if threading.current_thread() is threading.main_thread():
            fn()
        else:
            from Foundation import NSOperationQueue
            NSOperationQueue.mainQueue().addOperationWithBlock_(fn)

    def _device_key(self, info: dict) -> str:
        return info.get("serial_number") or info.get("path", "")

    def _controller_label(self, info: dict) -> str:
        name = "DualSense Edge" if info.get("product_id") == core.DS_EDGE_PID else "DualSense"
        same = sum(1 for item in self._controllers.values() if item.title == name or item.title.startswith(name + " "))
        return name if same == 0 else f"{name} {same + 1}"

    def _open_log(self, _=None):
        import subprocess
        subprocess.Popen(["open", _log_path])

    # ── Controller list sync ──────────────────────────────────────────────────

    def _sync(self, devices: list, notify: bool = False):
        """Reconcile controller menu items with `devices`. Must run on main thread."""
        current = {self._device_key(d): d for d in devices}
        added_labels = []

        # Remove items for disconnected controllers
        for key in list(self._controllers):
            if key not in current:
                item = self._controllers.pop(key)
                try:
                    del self.menu[item.title]
                except Exception:
                    pass

        # Add items for newly connected controllers
        for key, info in current.items():
            if key not in self._controllers:
                label = self._controller_label(info)
                item = rumps.MenuItem(label)
                item._menuitem.setImage_(_sf("checkmark"))
                item._menuitem.setEnabled_(False)
                self.menu.insert_before(_SEP_KEY, item)
                self._controllers[key] = item
                added_labels.append(label)

        # Status item: visible only when no controllers are connected
        self.status_item._menuitem.setHidden_(bool(current))

        # Menu bar icon
        img = _sf(_SYM_ACTIVE if current else _SYM_INACTIVE)
        self._icon_nsimage = img
        try:
            self._nsapp.nsstatusitem.setImage_(img)
        except AttributeError:
            pass

        # Clear error banner whenever at least one controller is active
        if added_labels:
            self.error_item._menuitem.setHidden_(True)

        if notify:
            for label in added_labels:
                rumps.notification(
                    "DualSense for Mac",
                    "Controller ready",
                    f"{label} — touchpad, gyro, and all buttons available.",
                    sound=False,
                )

    # ── IOKit watcher callbacks ────────────────────────────────────────────────

    def _on_iokit_activated(self) -> None:
        devices = core.find_target_devices(self.target_pids)

        def _update():
            self._sync(devices, notify=True)

        self._run_on_main(_update)

    def _on_iokit_error(self) -> None:
        def _update():
            self.error_item._menuitem.setHidden_(False)
        self._run_on_main(_update)

    def _on_device_disappeared(self) -> None:
        devices = core.find_target_devices(self.target_pids)

        def _update():
            self._sync(devices)

        self._run_on_main(_update)

    def quit(self, _=None) -> None:
        os._exit(0)


if __name__ == "__main__":
    App().run()
