import time
import threading
import configparser
import win32api
import win32con
import pygetwindow as gw
from datetime import datetime

stop_flag = False

def click_in_window(hwnd, rel_x, rel_y):
    lParam = win32api.MAKELONG(rel_x, rel_y)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
    time.sleep(0.02)
    win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, None, lParam)

def solo_click_loop(log_action, config_path, coords_path):
    global stop_flag
    stop_flag = False

    coords = configparser.ConfigParser()
    coords.read(coords_path)
    base_x = coords.getint("SOLO", "click_x", fallback=1055)
    base_y = coords.getint("SOLO", "click_y", fallback=61)
    interval = coords.getfloat("SOLO", "interval", fallback=1.5)

    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    instance_name = cfg.get("GLOBAL", "instance", fallback="")

    if not instance_name:
        log_action("Error: No instance name configured in config.ini", "error")
        return

    reference_width = cfg.getint("REFERENCE", "width", fallback=1152)
    reference_height = cfg.getint("REFERENCE", "height", fallback=679)

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
        actual_width = win.width
        actual_height = win.height

        scale_x = actual_width / reference_width
        scale_y = actual_height / reference_height

        rel_x = int(base_x * scale_x)
        rel_y = int(base_y * scale_y)

        log_action(f"Click position set to {rel_x}x{rel_y} (scaled from {base_x}x{base_y})", "system")

    except Exception as e:
        log_action(f"Error determining click position: {e}", "error")
        return

    while not stop_flag:
        windows = gw.getWindowsWithTitle(instance_name)
        for win in windows:
            try:
                hwnd = win._hWnd
                click_in_window(hwnd, rel_x, rel_y)
            except Exception as e:
                log_action(f"Error clicking window: {e}", "error")
        time.sleep(interval)

    stop_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_action(f"SOLO mode stopped at {stop_time}", "system")

def run_solo_mode(log_action, config_path, coords_path):
    thread = threading.Thread(target=solo_click_loop, args=(log_action, config_path, coords_path), daemon=True)
    thread.start()

def stop_solo_mode():
    global stop_flag
    stop_flag = True
