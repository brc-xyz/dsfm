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

import objc
import rumps
from AppKit import NSImage
from Foundation import NSObject
from IOBluetooth import IOBluetoothDevice

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


class _BTWatcher(NSObject):
    """Fires immediately when a DualSense connects or disconnects over Bluetooth."""

    def initWithApp_(self, app):
        self = objc.super(_BTWatcher, self).init()
        if self is None:
            return None
        self._app = app
        self._disconnect_notifs = {}   # addr → IOBluetoothUserNotification (must stay alive)
        self._connect_notif = IOBluetoothDevice.registerForConnectNotifications_selector_(
            self, "deviceConnected:device:"
        )
        log.debug("BTWatcher: listening for BT connections")
        return self

    def deviceConnected_device_(self, notification, device):
        if device.vendorID() != core.SONY_VID:
            return
        addr = device.addressString()
        log.info("BT connected: %s (vid=0x%04x pid=0x%04x)", addr,
                 device.vendorID(), device.productID())
        n = device.registerForDisconnectNotification_selector_(
            self, "deviceDisconnected:device:"
        )
        self._disconnect_notifs[addr] = n
        if self._app._auto:
            threading.Thread(target=self._app._on_device_appeared, daemon=True).start()

    def deviceDisconnected_device_(self, notification, device):
        addr = device.addressString()
        log.info("BT disconnected: %s", addr)
        self._disconnect_notifs.pop(addr, None)
        self._app._on_device_disappeared()


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

        # Scan once for already-connected controllers, then hand off to BTWatcher
        threading.Thread(target=self._on_device_appeared, daemon=True).start()
        self._bt_watcher = _BTWatcher.alloc().initWithApp_(self)

    # ── Status ────────────────────────────────────────────────────────────────

    def _set_status(self, text: str, active: bool = False) -> None:
        self.status_item.title = ("●  " if active else "○  ") + text
        img = _sf(_SYM_ACTIVE if active else _SYM_INACTIVE)
        self._icon_nsimage = img
        try:
            self._nsapp.nsstatusitem.setImage_(img)
        except AttributeError:
            pass

    # ── BT event handlers ─────────────────────────────────────────────────────

    def _on_device_appeared(self) -> None:
        time.sleep(0.3)  # let HID enumerate after BT connect
        devices = core.find_target_devices(self.target_pids)
        for d in devices:
            key = d.get("serial_number") or d.get("path", "")
            with self._lock:
                already = key in self._activated
            if not already:
                log.info("Activating: %s", core.device_label(d))
                for attempt in range(1, 6):
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
                        break
                    log.warning("Attempt %d failed for %s, retrying…", attempt, core.device_label(d))
                    time.sleep(0.5)
                else:
                    log.warning("Activation failed after 5 attempts: %s", core.device_label(d))

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
        if self._auto:
            threading.Thread(target=self._on_device_appeared, daemon=True).start()
            self._set_status("Waiting for controller…")
        else:
            self._set_status("Auto-activate off")

    def quit(self, _=None) -> None:
        os._exit(0)


if __name__ == "__main__":
    App().run()
