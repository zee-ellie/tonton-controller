import pyautogui
import win32gui
import pygetwindow as gw
import configparser

class CoordinateFinder:
    """Utility class for finding and converting mouse coordinates relative to windows"""
    
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(self.config_path)
        self.instance_name = self.config.get('GLOBAL', 'instance', fallback='')
    
    def get_screen_position(self):
        """Get current mouse position in screen coordinates"""
        return pyautogui.position()
    
    def get_pixel_color(self, x, y):
        """Get pixel color at screen coordinates (x, y)
        
        Returns:
            tuple: (hex_string, rgb_tuple) or (None, None) on error
        """
        try:
            color = pyautogui.pixel(x, y)
            hex_color = '#{:02X}{:02X}{:02X}'.format(*color)
            return hex_color, color
        except Exception as e:
            return None, None
    
    def get_window_client_offset(self, hwnd):
        """Calculate the offset between window origin and client area
        
        Args:
            hwnd: Window handle
            
        Returns:
            tuple: (offset_x, offset_y)
        """
        try:
            left, top = win32gui.ClientToScreen(hwnd, (0, 0))
            window_rect = win32gui.GetWindowRect(hwnd)
            offset_x = left - window_rect[0]
            offset_y = top - window_rect[1]
            return offset_x, offset_y
        except Exception:
            return 0, 0
    
    def screen_to_window_relative(self, screen_x, screen_y, hwnd):
        """Convert screen coordinates to window-relative coordinates
        
        Args:
            screen_x: X coordinate in screen space
            screen_y: Y coordinate in screen space
            hwnd: Window handle
            
        Returns:
            tuple: (relative_x, relative_y) or (None, None) on error
        """
        try:
            client_origin_x, client_origin_y = win32gui.ClientToScreen(hwnd, (0, 0))
            rel_x = screen_x - client_origin_x
            rel_y = screen_y - client_origin_y
            return rel_x, rel_y
        except Exception:
            return None, None
    
    def capture_position_data(self, hwnd=None):
        """Capture complete position data including screen coords, window-relative coords, and color
        
        Args:
            hwnd: Optional window handle. If None, only screen coordinates are returned
            
        Returns:
            dict: Dictionary containing 'screen_x', 'screen_y', 'rel_x', 'rel_y', 'hex_color', 'rgb_color'
        """
        screen_x, screen_y = self.get_screen_position()
        hex_color, rgb_color = self.get_pixel_color(screen_x, screen_y)
        
        result = {
            'screen_x': screen_x,
            'screen_y': screen_y,
            'rel_x': None,
            'rel_y': None,
            'hex_color': hex_color,
            'rgb_color': rgb_color,
            'hwnd': hwnd
        }
        
        if hwnd is not None:
            rel_x, rel_y = self.screen_to_window_relative(screen_x, screen_y, hwnd)
            result['rel_x'] = rel_x
            result['rel_y'] = rel_y
        
        return result
    
    def get_all_instance_windows(self):
        """Get all windows matching the configured instance name
        
        Returns:
            list: List of window objects
        """
        try:
            windows = gw.getWindowsWithTitle(self.instance_name)
            return [win for win in windows if win.visible]
        except Exception:
            return []
    
    def get_window_info_list(self):
        """Get formatted list of windows with their HWND and position
        
        Returns:
            list: List of strings formatted as "HWND | x,y"
        """
        windows = self.get_all_instance_windows()
        return [f"{win._hWnd} | {win.left},{win.top}" for win in windows]
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from a selection string in format "HWND | x,y"
        
        Args:
            selection_string: String in format "HWND | x,y"
            
        Returns:
            int: HWND value or None on error
        """
        try:
            hwnd_str = selection_string.split('|')[0].strip()
            return int(hwnd_str)
        except Exception:
            return None
    
    @staticmethod
    def format_position_string(data):
        """Format position data dictionary into a readable string
        
        Args:
            data: Dictionary from capture_position_data()
            
        Returns:
            str: Formatted string for display
        """
        lines = [f"Screen: X={data['screen_x']}, Y={data['screen_y']}"]
        
        if data['rel_x'] is not None and data['rel_y'] is not None:
            lines.append(f"Window-relative: X={data['rel_x']}, Y={data['rel_y']}")
        else:
            lines.append("Window-relative: (no window selected)")
        
        if data['hex_color']:
            lines.append(f"Color: {data['hex_color']}")
        else:
            lines.append("Color: Error reading color")
        
        return '\n'.join(lines)