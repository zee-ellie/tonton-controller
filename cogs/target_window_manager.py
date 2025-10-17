import configparser
from cogs.window_fetcher import WindowFetcher

class TargetWindowManager:
    def __init__(self, config_path):
        self.CONFIG_PATH = config_path
        self.window_fetcher = WindowFetcher(config_path)
        self.target_hwnd = None
        
        # ALWAYS default to Client #1 on launch
        # HWNDs are temporary and change every game restart
        self.auto_set_first_window()
    
    def get_window_list(self):
        """Get formatted list of windows (sorted)"""
        return self.window_fetcher.get_window_info_list()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string"""
        return self.window_fetcher.parse_hwnd_from_selection(selection_string)
    
    def auto_set_first_window(self):
        """
        Automatically set the first available window as the target.
        Called on initialization - ALWAYS defaults to Client #1 (top-left).
        Returns True if successful, False otherwise.
        """
        try:
            # Get sorted windows (Client #1 will be top-left)
            windows = self.window_fetcher.get_all_windows_sorted()
            
            if windows and len(windows) > 0:
                # Get first window (Client #1 - top left)
                first_window = windows[0]
                hwnd = first_window._hWnd
                
                if hwnd:
                    self.target_hwnd = hwnd
                    print(f"[TargetWindowManager] Auto-selected Client #1 (top-left): HWND={hwnd}, Position=({first_window.left}, {first_window.top})")
                    return True
            
            print(f"[TargetWindowManager] No windows available for auto-selection")
            return False
            
        except Exception as e:
            print(f"[TargetWindowManager] Error during auto-selection: {e}")
            return False
    
    def set_target_window(self, selection_string):
        """
        Set the target window from dropdown selection.
        This is only called when user MANUALLY selects a different window.
        """
        try:
            if not selection_string:
                return False, "No window selected"
            
            hwnd = self.parse_hwnd_from_selection(selection_string)
            if hwnd is None:
                return False, "Error parsing HWND from selection"
            
            # Verify window exists
            window = self.window_fetcher.get_window_by_hwnd(hwnd)
            if not window:
                return False, "Selected window not found"
            
            self.target_hwnd = hwnd
            
            # Log which client number this is
            sorted_windows = self.window_fetcher.get_all_windows_sorted()
            for idx, win in enumerate(sorted_windows, 1):
                if win._hWnd == hwnd:
                    print(f"[TargetWindowManager] User selected Client #{idx}: HWND={hwnd}, Position=({win.left}, {win.top})")
                    return True, f"Target window set to Client #{idx}: HWND={hwnd}"
            
            return True, f"Target window set: HWND={hwnd}"
            
        except Exception as e:
            return False, f"Error setting target window: {e}"
    
    def get_target_hwnd(self):
        """Get the current target HWND"""
        return self.target_hwnd
    
    def get_target_window_string(self):
        """
        Get the formatted string for the current target window.
        Useful for displaying in the GUI combobox.
        Returns None if no target or window not found.
        
        Format: "Client #1 - Top Left (234, 156) | HWND: 12345"
        
        This searches by HWND to find which client it is.
        """
        if not self.target_hwnd:
            return None
        
        try:
            # Get sorted windows
            sorted_windows = self.window_fetcher.get_all_windows_sorted()
            
            # Find the window with matching HWND
            for idx, win in enumerate(sorted_windows, 1):
                if win._hWnd == self.target_hwnd:
                    # Build the display string manually to match get_window_info_list() format
                    position_label = self.window_fetcher.get_position_label(win.left, win.top)
                    display_string = f"Client #{idx} - {position_label} ({win.left}, {win.top}) | HWND: {win._hWnd}"
                    return display_string
            
            # Target HWND not found in current window list
            return None
            
        except Exception as e:
            print(f"[TargetWindowManager] Error getting target window string: {e}")
            return None
    
    def has_target_window(self):
        """Check if a target window is set"""
        return self.target_hwnd is not None
    
    def refresh_windows(self):
        """Refresh window list (sorted)"""
        return self.window_fetcher.refresh_windows()