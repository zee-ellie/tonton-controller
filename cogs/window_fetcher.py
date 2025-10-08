import pygetwindow as gw
import configparser
import win32gui

class WindowFetcher:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)
        self.instance_name = self.config.get('GLOBAL', 'instance', fallback='')
    
    def get_all_windows(self):
        """Get all windows matching the instance name"""
        try:
            windows = gw.getWindowsWithTitle(self.instance_name)
            return [win for win in windows if win.visible and win._hWnd]
        except Exception:
            return []
    
    def get_window_info_list(self):
        """Get formatted list for dropdown (HWND | x,y)"""
        windows = self.get_all_windows()
        return [f"{win._hWnd} | {win.left},{win.top}" for win in windows]
    
    def get_window_treeview_data(self):
        """Get data for Treeview in Clients tab"""
        windows = self.get_all_windows()
        return [(win._hWnd, f"{win.left},{win.top}") for win in windows]
    
    def get_window_objects(self):
        """Get raw window objects"""
        return self.get_all_windows()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string in format 'HWND | x,y'"""
        try:
            hwnd_str = selection_string.split('|')[0].strip()
            return int(hwnd_str)
        except Exception:
            return None
    
    def get_window_by_hwnd(self, hwnd):
        """Get window object by HWND"""
        try:
            windows = self.get_all_windows()
            for win in windows:
                if win._hWnd == hwnd:
                    return win
            return None
        except Exception:
            return None
    
    def refresh_windows(self):
        """Force refresh of window list"""
        return self.get_all_windows()
    
    def get_window_count(self):
        """Get count of available windows"""
        return len(self.get_all_windows())