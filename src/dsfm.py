#!/usr/bin/env python3
"""
dsfm — DualSense for Mac
Core library: IOKit watcher and HID device enumeration.
"""

import ctypes
import logging
import threading

import hid

# ── Device identifiers ──────────────────────────────────────────────────────
SONY_VID    = 0x054C
DS_EDGE_PID = 0x0DF2   # DualSense Edge
DS_STD_PID  = 0x0CE6   # DualSense (standard)

# ── HID report constants ────────────────────────────────────────────────────
FEATURE_REPORT_CALIBRATION      = 0x05
FEATURE_REPORT_CALIBRATION_SIZE = 41

# ── Logging ─────────────────────────────────────────────────────────────────
log = logging.getLogger("dsfm")

# ── IOKit / CoreFoundation ctypes bindings ───────────────────────────────────

_iokit = ctypes.CDLL("/System/Library/Frameworks/IOKit.framework/IOKit")
_cf    = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

_c_io_object_t           = ctypes.c_uint32
_c_io_service_t          = ctypes.c_uint32
_c_io_iterator_t         = ctypes.c_uint32
_c_IOReturn              = ctypes.c_int32
_c_IONotificationPortRef = ctypes.c_void_p
_c_CFIndex               = ctypes.c_long
_kIOReturnSuccess        = 0
_kIOFirstMatchNotification   = b"IOServiceFirstMatch"
_kCFStringEncodingUTF8       = ctypes.c_uint32(0x08000100)
_kCFNumberSInt32Type         = ctypes.c_int(3)

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
    Register IOServiceAddMatchingNotification for Sony DualSense PIDs.
    Runs on a dedicated CFRunLoop thread.

    on_activated() — called when a matching device is successfully activated.
    on_removed()   — called when a matching device disconnects.
    on_error()     — called when a device is seen but activation fails.
    """
    port = _iokit.IONotificationPortCreate(0)
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
            while _iokit.IOIteratorNext(it):
                pass

        log.debug("iokit watcher: CFRunLoop running (watching %d PIDs)", len(iterators))
        _cf.CFRunLoopRun()

    threading.Thread(target=_thread, daemon=True, name="iokit-watcher").start()


# ── Device enumeration ────────────────────────────────────────────────────────

def find_target_devices(target_pids: set) -> list:
    """Return all connected HID devices matching the target PIDs."""
    results = []
    seen: set = set()

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

        if not (
            (usage_page == 0x01 and usage == 0x05) or
            (usage_page == 0xFF00)                 or
            (usage_page == 0 and usage == 0)
        ):
            continue

        key = d.get("serial_number") or d.get("path", "")
        if key in seen:
            continue
        seen.add(key)
        results.append(d)

    return results
