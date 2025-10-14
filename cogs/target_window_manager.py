import configparser
from cogs.window_fetcher import WindowFetcher

class TargetWindowManager:
    def __init__(self, config_path):
        self.CONFIG_PATH = config_path
        self.window_fetcher = WindowFetcher(config_path)
        self.target_hwnd = None
        
        # Try to load saved target from config first
        loaded = self.load_target_window()
        
        # If no saved target, automatically set first available window as default
        if not loaded:
            self.auto_set_first_window()
    
    def get_window_list(self):
        """Get formatted list of windows"""
        return self.window_fetcher.get_window_info_list()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string"""
        return self.window_fetcher.parse_hwnd_from_selection(selection_string)
    
    def auto_set_first_window(self):
        """
        Automatically set the first available window as the target.
        Called on initialization if no saved target exists.
        Returns True if successful, False otherwise.
        """
        try:
            windows = self.window_fetcher.get_window_info_list()
            if windows and len(windows) > 0:
                # Get first window from list
                first_window_string = windows[0]
                
                # Parse HWND from the selection string
                hwnd = self.parse_hwnd_from_selection(first_window_string)
                
                if hwnd:
                    self.target_hwnd = hwnd
                    self.save_target_window_to_config()
                    print(f"[TargetWindowManager] Auto-selected first window: HWND={hwnd}")
                    return True
            
            print(f"[TargetWindowManager] No windows available for auto-selection")
            return False
            
        except Exception as e:
            print(f"[TargetWindowManager] Error during auto-selection: {e}")
            return False
    
    def set_target_window(self, selection_string):
        """Set and save the target window"""
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
            self.save_target_window_to_config()
            return True, f"Target window set: HWND={hwnd}"
            
        except Exception as e:
            return False, f"Error setting target window: {e}"
    
    def save_target_window_to_config(self):
        """Save target window to config file"""
        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            
            if not config.has_section('REALM_RAID'):
                config.add_section('REALM_RAID')
                
            config.set('REALM_RAID', 'target_hwnd', str(self.target_hwnd))
            
            with open(self.CONFIG_PATH, 'w') as configfile:
                config.write(configfile)
                
        except Exception as e:
            raise Exception(f"Error saving target window to config: {e}")
    
    def load_target_window(self):
        """Load target window from config file"""
        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            
            if config.has_option('REALM_RAID', 'target_hwnd'):
                hwnd_str = config.get('REALM_RAID', 'target_hwnd')
                self.target_hwnd = int(hwnd_str)
                print(f"[TargetWindowManager] Loaded saved target: HWND={self.target_hwnd}")
                return True
            return False
        except Exception:
            return False
    
    def get_target_hwnd(self):
        """Get the current target HWND"""
        return self.target_hwnd
    
    def get_target_window_string(self):
        """
        Get the formatted string for the current target window.
        Useful for displaying in the GUI combobox.
        Returns None if no target or window not found.
        """
        if not self.target_hwnd:
            return None
        
        try:
            window = self.window_fetcher.get_window_by_hwnd(self.target_hwnd)
            if window:
                # Format: "Title - HWND=12345" (matching get_window_info_list format)
                return f"{window.title} - HWND={window._hWnd}"
            return None
        except Exception:
            return None
    
    def has_target_window(self):
        """Check if a target window is set"""
        return self.target_hwnd is not None
    
    def refresh_windows(self):
        """Refresh window list"""
        return self.window_fetcher.refresh_windows()