import threading
import configparser
import pygetwindow as gw
from cogs.mode_rr import RealmRaidAutomation, _rr_stop_event

_rr_all_running = False
_rr_all_instances = {}   # hwnd → RealmRaidAutomation
_rr_all_threads = {}     # hwnd → Thread


def run_rr_all_mode(log_func, config_path, coords_path, ref_path):
    global _rr_all_running, _rr_all_instances, _rr_all_threads

    if _rr_all_running:
        log_func("Realm Raid-All is already running", "error")
        return False

    cfg = configparser.ConfigParser()
    cfg.read(config_path, encoding='utf-8')
    instance_name = cfg.get("GLOBAL", "instance", fallback="")

    if not instance_name:
        log_func("Error: No instance name configured in config.ini", "error")
        return False

    windows = gw.getWindowsWithTitle(instance_name)
    if not windows:
        log_func(f"No windows found matching: '{instance_name}'", "error")
        log_func("Please make sure the game is running and not minimized", "error")
        return False

    log_func(f"Found {len(windows)} window(s) — starting Realm Raid-All", "system")

    _rr_stop_event.clear()
    _rr_all_instances.clear()
    _rr_all_threads.clear()

    for win in windows:
        hwnd = win._hWnd
        instance = RealmRaidAutomation(log_func, config_path, coords_path, hwnd, ref_path)
        thread = threading.Thread(
            target=instance.run,
            daemon=True,
            name=f"RR-All-{hwnd}"
        )
        _rr_all_instances[hwnd] = instance
        _rr_all_threads[hwnd] = thread
        log_func(f"Launching automation for HWND={hwnd}", "system")
        thread.start()

    _rr_all_running = True

    monitor = threading.Thread(target=_monitor_threads, daemon=True, name="RR-All-Monitor")
    monitor.start()
    return True


def _monitor_threads():
    """Wait for all automation threads to finish, then clean up."""
    for thread in list(_rr_all_threads.values()):
        thread.join()
    _cleanup()


def _cleanup():
    global _rr_all_running, _rr_all_instances, _rr_all_threads
    _rr_all_running = False
    _rr_all_instances.clear()
    _rr_all_threads.clear()


def stop_rr_all_mode():
    global _rr_all_running

    if not _rr_all_running:
        return False

    for instance in list(_rr_all_instances.values()):
        instance.running = False

    _rr_all_running = False
    _rr_stop_event.set()
    return True


def is_rr_all_running():
    return _rr_all_running
