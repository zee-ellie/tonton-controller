import configparser
from cogs.window_fetcher import WindowFetcher

class TargetWindowManager:
    def __init__(self, config_path):
        self.CONFIG_PATH = config_path
        self.window_fetcher = WindowFetcher(config_path)
        self.target_hwnd = None
        self.load_target_window()
    
    def get_window_list(self):
        """Get formatted list of windows"""
        return self.window_fetcher.get_window_info_list()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string"""
        return self.window_fetcher.parse_hwnd_from_selection(selection_string)
    
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
                return True
            return False
        except Exception:
            return False
    
    def get_target_hwnd(self):
        """Get the current target HWND"""
        return self.target_hwnd
    
    def has_target_window(self):
        """Check if a target window is set"""
        return self.target_hwnd is not None
    
    def refresh_windows(self):
        """Refresh window list"""
        return self.window_fetcher.refresh_windows()