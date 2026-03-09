import time
import threading
import configparser
import ctypes
from ctypes import wintypes
import win32api
import win32con
import pygetwindow as gw
from datetime import datetime

_stop_event = threading.Event()

def parse_coord(coord_str):
    """Parse coordinate string like '370, 150' to tuple"""
    parts = coord_str.split(',')
    return (int(parts[0].strip()), int(parts[1].strip()))

def click_in_window(hwnd, rel_x, rel_y):
    lParam = win32api.MAKELONG(rel_x, rel_y)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
    time.sleep(0.02)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, None, lParam)

def solo_click_loop(log_action, config_path, coords_path):
    _stop_event.clear()
    # Use DPI-unaware context so GetClientRect and WM_LBUTTONDOWN coordinates are always
    # in the game's 96-DPI virtual space, consistent on any monitor DPI or screen resolution.
    try:
        # Pass as c_void_p so ctypes sends a 64-bit HANDLE, not a truncated 32-bit int.
        # DPI_AWARENESS_CONTEXT_UNAWARE = (HANDLE)-1 = 0xFFFFFFFFFFFFFFFF on 64-bit Windows.
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-1))
    except Exception:
        pass

    # Load coordinates from coords.ini
    coords = configparser.ConfigParser()
    coords.read(coords_path, encoding='utf-8')

    # Parse click_solo coordinate (new format: "x, y")
    click_solo_str = coords.get("SOLO", "click_solo", fallback="1040, 575")
    base_x, base_y = parse_coord(click_solo_str)

    # Get interval
    interval = coords.getfloat("SOLO", "interval", fallback=1.5)

    # Load config
    cfg = configparser.ConfigParser()
    cfg.read(config_path, encoding='utf-8')
    instance_name = cfg.get("GLOBAL", "instance", fallback="")

    if not instance_name:
        log_action("Error: No instance name configured in config.ini", "error")
        return

    # Load reference resolution
    reference_width = cfg.getint("REFERENCE", "width", fallback=1136)
    reference_height = cfg.getint("REFERENCE", "height", fallback=640)

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_action(f"SOLO mode thread started at {start_time}", "system")
    log_action(f"SOLO click loop started at {start_time}", "system")

    try:
        windows = gw.getWindowsWithTitle(instance_name)
        if not windows:
            log_action("No windows found to determine click position", "error")
            return

        win = windows[0]
        hwnd = win._hWnd

        # Use GetClientRect so the scale ratio matches the CLIENT-relative
        # coordinate space used by WM_LBUTTONDOWN and coords.ini.
        # pygetwindow .width/.height returns WINDOW size (includes borders/title bar),
        # which inflates the scale factor and shifts all clicks down-right.
        _client_rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(_client_rect))
        actual_width  = _client_rect.right  - _client_rect.left
        actual_height = _client_rect.bottom - _client_rect.top

        # Calculate scaling factors
        scale_x = actual_width / reference_width
        scale_y = actual_height / reference_height

        # Scale coordinates
        rel_x = int(base_x * scale_x)
        rel_y = int(base_y * scale_y)

        log_action(f"Click position set to {rel_x}x{rel_y} (scaled from {base_x}x{base_y})", "system")

    except Exception as e:
        log_action(f"Error determining click position: {e}", "error")
        return

    # Main click loop
    while not _stop_event.is_set():
        windows = gw.getWindowsWithTitle(instance_name)
        for win in windows:
            try:
                hwnd = win._hWnd
                click_in_window(hwnd, rel_x, rel_y)
            except Exception as e:
                log_action(f"Error clicking window: {e}", "error")
        # Use event wait so Stop is responsive during the interval sleep
        _stop_event.wait(interval)

    stop_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_action(f"SOLO mode stopped at {stop_time}", "system")

def run_solo_mode(log_action, config_path, coords_path):
    thread = threading.Thread(target=solo_click_loop, args=(log_action, config_path, coords_path), daemon=True)
    thread.start()

def stop_solo_mode():
    _stop_event.set()
    return True
