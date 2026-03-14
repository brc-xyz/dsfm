#!/usr/bin/env python3
"""
dsfm — DualSense for Mac
========================
Unlocks the full input surface of a PS5 DualSense or DualSense Edge controller
connected to macOS over Bluetooth.

By default, PS5 controllers connect in a limited Bluetooth mode that only
exposes sticks, triggers, face buttons, and D-Pad. Touchpad, gyro,
accelerometer, back buttons, and FN buttons are invisible to macOS and any
app running on it.

DSFM fixes this silently and automatically, with no configuration required.

Usage:
    # One-shot: activate any currently connected controller
    python3 dsfm.py

    # Auto mode: stay running, activate on every connect and reconnect
    python3 dsfm.py --auto

    # Custom poll interval (seconds)
    python3 dsfm.py --auto --interval 1

    # DualSense Edge only
    python3 dsfm.py --edge-only

    # Verbose output
    python3 dsfm.py -v

Requirements:
    pip3 install hidapi
    macOS — no root required.
"""

import ctypes
import sys
import threading
import time
import signal
import argparse
import logging

try:
    import hid
except ImportError:
    print("[ERROR] hidapi not found. Install with:  pip3 install hidapi", file=sys.stderr)
    sys.exit(1)

# ── Device identifiers ──────────────────────────────────────────────────────
SONY_VID    = 0x054C
DS_EDGE_PID = 0x0DF2   # DualSense Edge
DS_STD_PID  = 0x0CE6   # DualSense (standard)

# ── HID report constants ────────────────────────────────────────────────────
FEATURE_REPORT_CALIBRATION      = 0x05
FEATURE_REPORT_CALIBRATION_SIZE = 41
INPUT_REPORT_SIMPLE_ID          = 0x01
INPUT_REPORT_ENHANCED_ID        = 0x31
INPUT_REPORT_ENHANCED_SIZE      = 78

# ── Logging ─────────────────────────────────────────────────────────────────
log = logging.getLogger("dsfm")

# ── IOKit / CoreFoundation ctypes bindings ───────────────────────────────────

_iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
_cf    = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

# Primitive types
_c_io_object_t          = ctypes.c_uint32
_c_io_service_t         = ctypes.c_uint32
_c_io_iterator_t        = ctypes.c_uint32
_c_IOReturn             = ctypes.c_int32
_c_IONotificationPortRef = ctypes.c_void_p
_c_CFIndex              = ctypes.c_long
_kIOReturnSuccess       = 0
_kIOFirstMatchNotification    = b"IOServiceFirstMatch"
_kCFStringEncodingUTF8        = ctypes.c_uint32(0x08000100)
_kCFNumberSInt32Type          = ctypes.c_int(3)

# Function signatures
_iokit.IONotificationPortCreate.restype  = _c_IONotificationPortRef
_iokit.IONotificationPortCreate.argtypes = [_c_io_object_t]

_iokit.IONotificationPortGetRunLoopSource.restype  = ctypes.c_void_p
_iokit.IONotificationPortGetRunLoopSource.argtypes = [_c_IONotificationPortRef]

_iokit.IOServiceMatching.restype  = ctypes.c_void_p
_iokit.IOServiceMatching.argtypes = [ctypes.c_char_p]

_iokit.IOServiceAddMatchingNotification.restype  = _c_IOReturn
_iokit.IOServiceAddMatchingNotification.argtypes = [
    _c_IONotificationPortRef, ctypes.c_char_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_c_io_iterator_t),
]

_iokit.IOIteratorNext.restype  = _c_io_service_t
_iokit.IOIteratorNext.argtypes = [_c_io_iterator_t]

_iokit.IOObjectRelease.restype  = _c_IOReturn
_iokit.IOObjectRelease.argtypes = [_c_io_object_t]

_cf.CFRunLoopGetCurrent.restype  = ctypes.c_void_p
_cf.CFRunLoopGetCurrent.argtypes = []

_cf.CFRunLoopAddSource.restype  = None
_cf.CFRunLoopAddSource.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

_cf.CFRunLoopRun.restype  = None
_cf.CFRunLoopRun.argtypes = []

_cf.CFStringCreateWithCString.restype  = ctypes.c_void_p
_cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

_cf.CFNumberCreate.restype  = ctypes.c_void_p
_cf.CFNumberCreate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

_cf.CFDictionarySetValue.restype  = None
_cf.CFDictionarySetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

_cf.CFRelease.restype  = None
_cf.CFRelease.argtypes = [ctypes.c_void_p]

_cf.CFAllocatorGetDefault.restype  = ctypes.c_void_p
_cf.CFAllocatorGetDefault.argtypes = []

_iokit.IOHIDDeviceCreate.restype  = ctypes.c_void_p
_iokit.IOHIDDeviceCreate.argtypes = [ctypes.c_void_p, _c_io_service_t]

_iokit.IOHIDDeviceOpen.restype  = _c_IOReturn
_iokit.IOHIDDeviceOpen.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

_iokit.IOHIDDeviceClose.restype  = _c_IOReturn
_iokit.IOHIDDeviceClose.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

_iokit.IOHIDDeviceScheduleWithRunLoop.restype  = None
_iokit.IOHIDDeviceScheduleWithRunLoop.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

_iokit.IOHIDDeviceUnscheduleFromRunLoop.restype  = None
_iokit.IOHIDDeviceUnscheduleFromRunLoop.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

_iokit.IOHIDDeviceGetReport.restype  = _c_IOReturn
_iokit.IOHIDDeviceGetReport.argtypes = [
    ctypes.c_void_p, ctypes.c_int, _c_CFIndex,
    ctypes.c_void_p, ctypes.POINTER(_c_CFIndex),
]

_kIOHIDReportTypeFeature = ctypes.c_int(2)

_IOKIT_REFS = []  # keep ctypes objects alive for the process lifetime


def _iokit_activate(service: int, run_loop, rl_mode) -> bool:
    """Open device (non-exclusive), send feature report 0x05, close."""
    alloc  = _cf.CFAllocatorGetDefault()
    device = _iokit.IOHIDDeviceCreate(alloc, service)
    if not device:
        log.debug("iokit: IOHIDDeviceCreate returned null")
        return False
    try:
        ret = _iokit.IOHIDDeviceOpen(device, ctypes.c_uint32(0))
        if ret != _kIOReturnSuccess:
            log.debug("iokit: IOHIDDeviceOpen failed: 0x%08x", ret & 0xFFFFFFFF)
            return False
        try:
            _iokit.IOHIDDeviceScheduleWithRunLoop(device, run_loop, rl_mode)
            buf    = (ctypes.c_uint8 * FEATURE_REPORT_CALIBRATION_SIZE)()
            length = _c_CFIndex(FEATURE_REPORT_CALIBRATION_SIZE)
            ret = _iokit.IOHIDDeviceGetReport(
                device, _kIOHIDReportTypeFeature,
                _c_CFIndex(FEATURE_REPORT_CALIBRATION),
                buf, ctypes.byref(length),
            )
            _iokit.IOHIDDeviceUnscheduleFromRunLoop(device, run_loop, rl_mode)
        finally:
            _iokit.IOHIDDeviceClose(device, ctypes.c_uint32(0))
        if ret == _kIOReturnSuccess:
            log.info("iokit: enhanced mode activated")
            return True
        log.debug("iokit: IOHIDDeviceGetReport failed: 0x%08x", ret & 0xFFFFFFFF)
        return False
    finally:
        _cf.CFRelease(device)


def _cf_str(s: str) -> ctypes.c_void_p:
    return _cf.CFStringCreateWithCString(None, s.encode(), _kCFStringEncodingUTF8)


def _cf_int32(v: int) -> ctypes.c_void_p:
    n = ctypes.c_int32(v)
    return _cf.CFNumberCreate(None, _kCFNumberSInt32Type, ctypes.byref(n))


def _hid_matching_dict(vid: int, pid: int) -> ctypes.c_void_p:
    d = _iokit.IOServiceMatching(b"IOHIDDevice")
    k_vid = _cf_str("VendorID");  v_vid = _cf_int32(vid)
    k_pid = _cf_str("ProductID"); v_pid = _cf_int32(pid)
    _cf.CFDictionarySetValue(d, k_vid, v_vid)
    _cf.CFDictionarySetValue(d, k_pid, v_pid)
    for ref in (k_vid, v_vid, k_pid, v_pid):
        _cf.CFRelease(ref)
    return d


# ── IOKit HID watcher ─────────────────────────────────────────────────────────

_IOSERVICE_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, _c_io_iterator_t)


def start_iokit_hid_watcher(target_pids: set, on_activated, on_removed, on_error=None) -> None:
    """
    Register IOServiceAddMatchingNotification for Sony DualSense PIDs:
      - kIOFirstMatchNotification: call on_activated() when a device is ready.
      - kIOTerminatedNotification: call on_removed() on disconnect.
    Runs on a dedicated CFRunLoop thread. No Bluetooth permission required.

    on_activated() — called when a matching device appears (watcher thread).
    on_removed()   — called when a matching device leaves IOKit (watcher thread).
    on_error()     — called when a device is seen but activation fails (watcher thread).
    """
    port = _iokit.IONotificationPortCreate(0)  # 0 = kIOMainPortDefault
    if not port:
        log.error("iokit watcher: IONotificationPortCreate failed")
        return

    source = _iokit.IONotificationPortGetRunLoopSource(port)
    _IOKIT_REFS.extend([port, source])

    rl_mode = _cf_str("kCFRunLoopDefaultMode")
    _IOKIT_REFS.append(rl_mode)

    def _thread():
        run_loop = _cf.CFRunLoopGetCurrent()
        _cf.CFRunLoopAddSource(run_loop, source, rl_mode)

        iterators = []

        def _on_matched(_, iterator):
            svc = _iokit.IOIteratorNext(iterator)
            while svc:
                ok = _iokit_activate(svc, run_loop, rl_mode)
                _iokit.IOObjectRelease(svc)
                if ok:
                    on_activated()
                elif on_error:
                    on_error()
                svc = _iokit.IOIteratorNext(iterator)

        def _on_removed(_, iterator):
            svc = _iokit.IOIteratorNext(iterator)
            while svc:
                log.info("iokit watcher: device removed")
                _iokit.IOObjectRelease(svc)
                on_removed()
                svc = _iokit.IOIteratorNext(iterator)

        cb         = _IOSERVICE_CALLBACK(_on_matched)
        cb_removed = _IOSERVICE_CALLBACK(_on_removed)
        _IOKIT_REFS.extend([cb, cb_removed])

        for pid in target_pids:
            matching = _hid_matching_dict(SONY_VID, pid)
            it = _c_io_iterator_t(0)
            ret = _iokit.IOServiceAddMatchingNotification(
                port, _kIOFirstMatchNotification, matching,
                cb, None, ctypes.byref(it),
            )
            if ret != _kIOReturnSuccess:
                log.error("iokit watcher: AddMatchingNotification failed → 0x%08x", ret & 0xFFFFFFFF)
                continue
            iterators.append(it)
            _IOKIT_REFS.append(it)
            _on_matched(None, it)  # drain existing devices (arms the notification)

        # Also watch for device removal to trigger UI updates.
        _kIOTerminatedNotification = b"IOServiceTerminate"
        for pid in target_pids:
            matching = _hid_matching_dict(SONY_VID, pid)
            it = _c_io_iterator_t(0)
            ret = _iokit.IOServiceAddMatchingNotification(
                port, _kIOTerminatedNotification, matching,
                cb_removed, None, ctypes.byref(it),
            )
            if ret != _kIOReturnSuccess:
                log.error("iokit watcher: AddMatchingNotification(removed) failed → 0x%08x", ret & 0xFFFFFFFF)
                continue
            iterators.append(it)
            _IOKIT_REFS.append(it)
            # Drain to arm (no existing terminated devices, but required)
            while _iokit.IOIteratorNext(it):
                pass

        log.debug("iokit watcher: CFRunLoop running (watching %s PIDs)", len(iterators))
        _cf.CFRunLoopRun()

    t = threading.Thread(target=_thread, daemon=True, name="iokit-watcher")
    t.start()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                                           datefmt="%H:%M:%S"))
    log.addHandler(handler)
    log.setLevel(level)


# ── Device helpers ───────────────────────────────────────────────────────────

def device_label(info: dict) -> str:
    pid  = info.get("product_id", 0)
    name = "DualSense Edge" if pid == DS_EDGE_PID else "DualSense"
    serial = info.get("serial_number") or "no-serial"
    return f"{name} [{serial}]"


def find_target_devices(target_pids: set) -> list:
    """
    Return all connected HID devices matching the target PIDs.
    Filters for the primary gamepad interface; falls back to usage 0/0
    which is common for Bluetooth HID on macOS.
    """
    results = []
    seen_serials: set = set()

    try:
        all_devices = hid.enumerate()
    except Exception as e:
        log.error("hid.enumerate() failed: %s", e)
        return results

    for d in all_devices:
        if d.get("vendor_id") != SONY_VID:
            continue
        if d.get("product_id") not in target_pids:
            continue

        usage_page = d.get("usage_page", 0)
        usage      = d.get("usage", 0)

        # Accept the gamepad interface (Generic Desktop / Gamepad) and the
        # 0/0 fallback that macOS Bluetooth often reports.
        if not (
            (usage_page == 0x01 and usage == 0x05) or
            (usage_page == 0xFF00)                 or
            (usage_page == 0 and usage == 0)
        ):
            log.debug("Skipping interface: usage_page=0x%04x usage=0x%04x path=%s",
                      usage_page, usage, d.get("path", ""))
            continue

        serial = d.get("serial_number") or d.get("path", "")
        if serial in seen_serials:
            continue
        seen_serials.add(serial)

        results.append(d)
        log.debug("Found: %s  path=%s", device_label(d), d.get("path", ""))

    return results


# ── Core activation ──────────────────────────────────────────────────────────

def activate_enhanced_mode(info: dict) -> bool:
    """
    Open the controller, trigger enhanced mode, verify, and close.
    Returns True on success.
    """
    label = device_label(info)
    path  = info["path"]

    dev = hid.device()
    try:
        log.debug("Opening %s at %s", label, path)
        dev.open_path(path)

        log.debug("Requesting calibration report from %s", label)
        try:
            calibration = dev.get_feature_report(FEATURE_REPORT_CALIBRATION,
                                                  FEATURE_REPORT_CALIBRATION_SIZE)
            log.debug("Calibration report (%d bytes): %s ...",
                      len(calibration),
                      " ".join(f"{b:02x}" for b in calibration[:8]))
        except Exception as e:
            log.warning("Calibration report request failed for %s: %s", label, e)

        log.debug("Verifying enhanced mode for %s …", label)
        dev.set_nonblocking(False)
        report = dev.read(INPUT_REPORT_ENHANCED_SIZE, timeout_ms=1500)

        if not report:
            log.warning("%-40s  no input report received (timeout)", label)
            return False

        report_id = report[0]
        log.debug("Input report ID: 0x%02x", report_id)

        if report_id == INPUT_REPORT_ENHANCED_ID:
            log.info("✓  %-40s  full input active", label)
            return True
        elif report_id == INPUT_REPORT_SIMPLE_ID:
            log.warning("%-40s  still in limited mode", label)
            log.warning("   → If Steam is running with PS controller support enabled,")
            log.warning("     it may be holding an exclusive lock. Try quitting Steam.")
            return False
        else:
            log.warning("%-40s  unexpected report ID: 0x%02x", label, report_id)
            return False

    except OSError as e:
        err = str(e)
        log.error("Cannot open %s: %s", label, err)
        if "errno 1" in err.lower() or "permission" in err.lower():
            log.error("   → Another process (Steam?) may be holding an exclusive lock.")
            log.error("     Quit Steam or any PS5 controller app and retry.")
        return False

    finally:
        try:
            dev.close()
        except Exception:
            pass


# ── One-shot mode ─────────────────────────────────────────────────────────────

def run_once(target_pids: set) -> int:
    devices = find_target_devices(target_pids)

    if not devices:
        log.info("No PS5 controller found.")
        log.info("Make sure the controller is paired and connected via Bluetooth.")
        return 1

    log.info("Found %d controller(s). Activating…", len(devices))
    success_count = sum(1 for d in devices if activate_enhanced_mode(d))

    if success_count == len(devices):
        log.info("Done. %d/%d controller(s) activated.", success_count, len(devices))
        return 0
    else:
        log.warning("Done. %d/%d controller(s) activated.", success_count, len(devices))
        return 1


# ── Auto mode ─────────────────────────────────────────────────────────────────

def run_auto(target_pids: set, interval: float) -> None:
    """
    Poll for controllers and activate them as they connect or reconnect.
    Runs until SIGINT or SIGTERM.
    """
    activated: set = set()
    running = True

    def handle_signal(sig, frame):
        nonlocal running
        log.info("Shutting down.")
        running = False

    signal.signal(signal.SIGINT,  handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log.info("Auto mode active (interval: %.0fs). Waiting for controllers…", interval)

    while running:
        devices = find_target_devices(target_pids)

        for d in devices:
            key = d.get("serial_number") or d.get("path", "")
            if key not in activated:
                log.info("Controller connected: %s", device_label(d))
                if activate_enhanced_mode(d):
                    activated.add(key)

        # Remove devices that have disconnected so they're re-activated on reconnect
        if activated:
            current = {d.get("serial_number") or d.get("path", "") for d in find_target_devices(target_pids)}
            gone = activated - current
            for k in gone:
                log.debug("Controller disconnected — will re-activate on reconnect.")
                activated.discard(k)

        time.sleep(interval)

    log.info("dsfm stopped.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dsfm",
        description="Unlock the full input surface of PS5 controllers on macOS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 dsfm.py                    One-shot activation
  python3 dsfm.py --auto             Auto mode: activate on every connect
  python3 dsfm.py --auto -v          Auto mode with debug output
  python3 dsfm.py --edge-only        DualSense Edge only
""")

    parser.add_argument("--auto", action="store_true",
                        help="Stay running and activate controllers as they connect.")
    parser.add_argument("--interval", type=float, default=2.0, metavar="N",
                        help="Poll interval in seconds for --auto mode (default: 2).")
    parser.add_argument("--edge-only", action="store_true",
                        help="Target DualSense Edge only (skip standard DualSense).")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug output.")

    args = parser.parse_args()
    setup_logging(args.verbose)

    target_pids = {DS_EDGE_PID} if args.edge_only else {DS_EDGE_PID, DS_STD_PID}

    log.debug("hidapi version: %s", hid.__version__ if hasattr(hid, "__version__") else "unknown")
    log.debug("Target PIDs: %s", [f"0x{p:04X}" for p in target_pids])

    if args.auto:
        run_auto(target_pids, args.interval)
    else:
        sys.exit(run_once(target_pids))


if __name__ == "__main__":
    main()
