import pygetwindow as gw
import configparser
import win32gui

class WindowFetcher:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path, encoding='utf-8') 
        self.instance_name = self.config.get('GLOBAL', 'instance', fallback='')
    
    def get_all_windows(self):
        """Get all windows matching the EXACT instance name"""
        try:
            all_windows = gw.getAllWindows()
            windows = [win for win in all_windows 
                      if win.title == self.instance_name 
                      and win.visible 
                      and win._hWnd]
            return windows
        except Exception:
            return []
    
    def get_all_windows_sorted(self):
        """Get all windows sorted by position (top to bottom, left to right)
        
        Sorting logic:
        1. Primary sort: Y position (top to bottom)
        2. Secondary sort: X position (left to right)
        
        This ensures consistent ordering like reading a book:
        Row 1: [Client #1] [Client #2] [Client #3]
        Row 2: [Client #4] [Client #5] [Client #6]
        """
        windows = self.get_all_windows()
        
        def sort_key(win):
            row = win.top // 100
            return (row, win.left)
        
        return sorted(windows, key=sort_key)
    
    def get_position_label(self, x, y):
        """Generate a friendly position label based on screen coordinates"""
        # Horizontal position
        if x < 800:
            h_pos = "Left"
        elif x < 1600:
            h_pos = "Center"
        else:
            h_pos = "Right"
        
        # Vertical position
        if y < 300:
            v_pos = "Top"
        elif y < 600:
            v_pos = "Middle"
        else:
            v_pos = "Bottom"
        
        return f"{v_pos} {h_pos}"
    
    def get_window_info_list(self):
        """Get formatted list for dropdown with user-friendly display
        Format: "Client #1 - Top Left (234, 156) | HWND: 12345"
        
        This format is used in:
        - Control tab: Target Window dropdown
        - Debug tab: Mouse Position Finder dropdown
        
        Windows are sorted by position (top-left to bottom-right)
        """
        windows = self.get_all_windows_sorted()
        result = []
        
        for idx, win in enumerate(windows, 1):
            position_label = self.get_position_label(win.left, win.top)
            # Format: "Client #1 - Top Left (234, 156) | HWND: 12345"
            display_text = f"Client #{idx} - {position_label} ({win.left}, {win.top}) | HWND: {win._hWnd}"
            result.append(display_text)
        
        return result
    
    def get_window_treeview_data(self):
        """Get data for Treeview in Clients tab with friendly labels
        Returns: list of tuples (client_label, position_text, hwnd)
        
        Windows are sorted by position (top-left to bottom-right)
        """
        windows = self.get_all_windows_sorted()
        result = []
        
        for idx, win in enumerate(windows, 1):
            position_label = self.get_position_label(win.left, win.top)
            client_label = f"Client #{idx}"
            position_text = f"{position_label} ({win.left}, {win.top})"
            hwnd_text = str(win._hWnd)
            result.append((client_label, position_text, hwnd_text))
        
        return result
    
    def get_window_objects(self):
        """Get raw window objects sorted by position"""
        return self.get_all_windows_sorted()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string
        Handles multiple formats:
        - "Client #1 - Top Left (234, 156) | HWND: 12345"
        - "12345 | 234,156" (legacy format)
        """
        try:
            # New format: contains "HWND: "
            if "HWND:" in selection_string:
                hwnd_str = selection_string.split("HWND:")[1].strip()
                return int(hwnd_str)
            
            # Alternative format: contains "HWND="
            if "HWND=" in selection_string:
                hwnd_str = selection_string.split("HWND=")[1].strip()
                return int(hwnd_str)
            
            # Legacy format: "12345 | 234,156"
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
        """Force refresh of window list (sorted)"""
        return self.get_all_windows_sorted()
    
    def get_window_count(self):
        """Get count of available windows"""
        return len(self.get_all_windows())