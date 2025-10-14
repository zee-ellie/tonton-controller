import pyautogui
import win32gui
import ctypes
from ctypes import wintypes
import keyboard
from cogs.window_fetcher import WindowFetcher

class CoordinateFinder:
    """Utility class for finding client-relative mouse coordinates"""
    
    def __init__(self, config_path, window_fetcher=None):
        self.config_path = config_path
        self.window_fetcher = window_fetcher or WindowFetcher(config_path)
        self.hotkey_listening = False
        self.user32 = ctypes.windll.user32
        
    def get_screen_position(self):
        """Get current mouse position in screen coordinates"""
        return pyautogui.position()
    
    def get_pixel_color(self, x, y, hwnd=None):
        """Get pixel color at screen coordinates OR from window DC if hwnd provided
        
        Args:
            x: X coordinate (screen if hwnd is None, client if hwnd provided)
            y: Y coordinate (screen if hwnd is None, client if hwnd provided)
            hwnd: Window handle (optional). If provided, reads from window DC using client coords
            
        Returns:
            tuple: (hex_color, rgb_color) or (None, None) on error
        """
        try:
            if hwnd is not None:
                # NEW METHOD: Read directly from window DC (works behind other windows)
                # x, y are CLIENT coordinates
                print(f"[COLOR] Using win32gui.GetPixel() - Window DC method")
                print(f"[COLOR] Reading from HWND {hwnd} at client coords ({x}, {y})")
                
                hdc = win32gui.GetDC(hwnd)
                
                # Get pixel color from window's device context
                bgr_color = win32gui.GetPixel(hdc, x, y)
                
                # Cleanup
                win32gui.ReleaseDC(hwnd, hdc)
                
                # Convert BGR to RGB
                b = (bgr_color >> 16) & 0xFF
                g = (bgr_color >> 8) & 0xFF
                r = bgr_color & 0xFF
                
                rgb_color = (r, g, b)
                hex_color = '#{:02X}{:02X}{:02X}'.format(r, g, b)
                
                print(f"[COLOR] ✓ Window DC result: {hex_color} RGB{rgb_color}")
                print(f"[COLOR] This works even when window is behind other applications")
                
                return hex_color, rgb_color
            else:
                # OLD METHOD: Read from screen (x, y are screen coordinates)
                # Kept for backward compatibility
                print(f"[COLOR] Using pyautogui.pixel() - Screen capture method")
                print(f"[COLOR] Reading from screen coords ({x}, {y})")
                print(f"[COLOR] ⚠️  This only works when window is visible on screen")
                
                color = pyautogui.pixel(x, y)
                hex_color = '#{:02X}{:02X}{:02X}'.format(*color)
                
                print(f"[COLOR] ✓ Screen capture result: {hex_color} RGB{color}")
                
                return hex_color, color
                
        except Exception as e:
            print(f"[COLOR] ✗ Error getting pixel color: {e}")
            return None, None
    
    def get_client_coordinates(self, hwnd):
        """Get cursor position relative to CLIENT area only (excludes borders/title bar)
        
        Args:
            hwnd: Window handle
            
        Returns:
            tuple: (client_x, client_y) or (None, None) on error
        """
        try:
            point = wintypes.POINT()
            # Get current cursor position in screen coordinates
            self.user32.GetCursorPos(ctypes.byref(point))
            
            # Convert screen coordinates to CLIENT coordinates
            # This automatically excludes window borders, title bar, menu bars, etc.
            result = self.user32.ScreenToClient(hwnd, ctypes.byref(point))
            
            if result:
                # Verify coordinates are within client area
                client_rect = wintypes.RECT()
                self.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
                
                # Client coordinates are always relative to (0,0) of the client area
                if (0 <= point.x <= client_rect.right and 
                    0 <= point.y <= client_rect.bottom):
                    return point.x, point.y
                else:
                    # Coordinates are outside client area but still valid for reference
                    return point.x, point.y
                
            return None, None
            
        except Exception:
            return None, None
    
    def get_window_info(self, hwnd):
        """Get window information for debugging"""
        try:
            # Get window rectangle (includes borders)
            window_rect = wintypes.RECT()
            self.user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            
            # Get client rectangle (content area only)
            client_rect = wintypes.RECT()
            self.user32.GetClientRect(hwnd, ctypes.byref(client_rect))
            
            # Calculate border sizes
            border_width = (window_rect.right - window_rect.left - client_rect.right) // 2
            title_bar_height = (window_rect.bottom - window_rect.top - client_rect.bottom) - (border_width * 2)
            
            return {
                'window_rect': (window_rect.left, window_rect.top, window_rect.right, window_rect.bottom),
                'client_rect': (client_rect.left, client_rect.top, client_rect.right, client_rect.bottom),
                'border_width': border_width,
                'title_bar_height': title_bar_height,
                'client_size': (client_rect.right, client_rect.bottom)
            }
        except Exception:
            return None
    
    def capture_client_position_data(self, hwnd=None):
        """Capture complete position data using client coordinates
        
        Args:
            hwnd: Window handle. If None, only screen coordinates are returned
            
        Returns:
            dict: Dictionary containing screen and client coordinates, color data, and window info
        """
        print("\n" + "="*60)
        print("[CAPTURE] Starting position and color capture")
        print("="*60)
        
        screen_x, screen_y = self.get_screen_position()
        print(f"[CAPTURE] Mouse screen position: ({screen_x}, {screen_y})")
        
        result = {
            'screen_x': screen_x,
            'screen_y': screen_y,
            'hex_color': None,
            'rgb_color': None,
            'hwnd': hwnd,
            'client_x': None,
            'client_y': None,
            'window_info': None,
            'color_method': 'none'
        }
        
        if hwnd is not None:
            print(f"[CAPTURE] Window selected (HWND: {hwnd})")
            
            # Get client-relative coordinates (excludes borders/title bar)
            client_x, client_y = self.get_client_coordinates(hwnd)
            result['client_x'] = client_x
            result['client_y'] = client_y
            
            print(f"[CAPTURE] Converted to client coords: ({client_x}, {client_y})")
            
            # Get color using window DC method (works behind other windows)
            if client_x is not None and client_y is not None:
                hex_color, rgb_color = self.get_pixel_color(client_x, client_y, hwnd)
                result['hex_color'] = hex_color
                result['rgb_color'] = rgb_color
                result['color_method'] = 'window_dc'
                print(f"[CAPTURE] Color method: Window DC (non-intrusive)")
            else:
                print(f"[CAPTURE] ✗ Failed to get client coordinates")
            
            # Get window information for debugging
            result['window_info'] = self.get_window_info(hwnd)
        else:
            print(f"[CAPTURE] No window selected - using screen capture method")
            # No window selected - use screen method
            hex_color, rgb_color = self.get_pixel_color(screen_x, screen_y)
            result['hex_color'] = hex_color
            result['rgb_color'] = rgb_color
            result['color_method'] = 'screen'
        
        print("="*60 + "\n")
        return result
    
    def get_window_info_list(self):
        """Get formatted list of windows for dropdown"""
        return self.window_fetcher.get_window_info_list()
    
    def parse_hwnd_from_selection(self, selection_string):
        """Parse HWND from selection string"""
        return self.window_fetcher.parse_hwnd_from_selection(selection_string)
    
    def get_window_by_hwnd(self, hwnd):
        """Get window object by HWND"""
        return self.window_fetcher.get_window_by_hwnd(hwnd)
    
    @staticmethod
    def format_position_string(data):
        """Format position data emphasizing client coordinates"""
        lines = [f"Screen: X={data['screen_x']}, Y={data['screen_y']}"]
        
        if data.get('client_x') is not None and data.get('client_y') is not None:
            lines.append(f"Client-relative: X={data['client_x']}, Y={data['client_y']}")
            lines.append("✓ Excludes borders and title bar")
        else:
            lines.append("Client-relative: (no window selected)")
        
        if data['hex_color']:
            color_method = data.get('color_method', 'unknown')
            method_label = {
                'window_dc': '(Window DC - works behind windows)',
                'screen': '(Screen capture)',
                'none': ''
            }.get(color_method, '')
            lines.append(f"Color: {data['hex_color']} {method_label}")
        else:
            lines.append("Color: Error reading color")
        
        # Add window info for debugging
        if data.get('window_info'):
            info = data['window_info']
            lines.append(f"Client size: {info['client_size'][0]}x{info['client_size'][1]}")
        
        return '\n'.join(lines)
    
    def toggle_hotkey_listener(self, callback):
        """Toggle F8 hotkey listener for capturing mouse positions"""
        try:
            if not self.hotkey_listening:
                keyboard.add_hotkey('f8', callback)
                self.hotkey_listening = True
                self.current_callback = callback
                return True
            else:
                if hasattr(self, 'current_callback'):
                    keyboard.remove_hotkey(self.current_callback)
                self.hotkey_listening = False
                return False
        except Exception as e:
            raise Exception(f"Error toggling hotkey listener: {e}")
    
    def is_hotkey_listening(self):
        """Check if hotkey listener is active"""
        return self.hotkey_listening
    
    def get_live_update(self, hwnd=None):
        """Get current position data for live tracking"""
        return self.capture_client_position_data(hwnd)
    
    def verify_window_access(self, hwnd):
        """Verify we can access the window and get client coordinates"""
        try:
            test_x, test_y = self.get_client_coordinates(hwnd)
            return test_x is not None and test_y is not None
        except Exception:
            return False
        
    def debug_coordinate_conversion(self, hwnd):
        """Test method to debug coordinate conversion issues"""
        try:
            print(f"Testing HWND: {hwnd}")
            
            # Test if window exists and is accessible
            window = self.window_fetcher.get_window_by_hwnd(hwnd)
            if not window:
                print("❌ Window not found in window list")
                return False
                
            print(f"✅ Window found: {window.title}")
            print(f"   Position: ({window.left}, {window.top})")
            print(f"   Size: {window.width}x{window.height}")
            print(f"   Visible: {window.visible}")
            
            # Test client coordinate conversion
            screen_x, screen_y = self.get_screen_position()
            print(f"📌 Screen position: ({screen_x}, {screen_y})")
            
            client_x, client_y = self.get_client_coordinates(hwnd)
            print(f"🎯 Client coordinates: ({client_x}, {client_y})")
            
            if client_x is None or client_y is None:
                print("❌ Client coordinate conversion failed")
                return False
            
            # Test color reading from window DC
            hex_color, rgb_color = self.get_pixel_color(client_x, client_y, hwnd)
            print(f"🎨 Color from Window DC: {hex_color} RGB{rgb_color}")
            print(f"   This method works even when window is behind other applications")
                
            print("✅ Client coordinate conversion and color reading successful")
            return True
            
        except Exception as e:
            print(f"❌ Error during debug: {e}")
            return False