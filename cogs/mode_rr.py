import threading
import time
import configparser
import ctypes
from ctypes import wintypes
import win32gui
import win32api
import win32con

# Global control flags
_rr_running = False
_rr_thread = None
_rr_automation_instance = None

# Windows API setup
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class RealmRaidAutomation:
    # ==================== TIMING CONFIGURATION ====================
    # Adjust these values to fine-tune automation timing
    
    CLICK_DELAY = 0.05              # Delay between mouse down and up (seconds)
    EXPANSION_WAIT = 1.0            # Wait time after clicking to expand match (seconds)
    JOIN_WAIT = 1.0                 # Wait time after clicking join button (seconds)
    MATCH_CHECK_INTERVAL = 3.0      # How often to check if match ended (seconds)
    LOBBY_RETURN_WAIT = 3.0         # Wait time for returning to lobby after match (seconds)
    LOBBY_VERIFY_WAIT = 2.0         # Wait time when retrying lobby verification (seconds)
    REFRESH_CLICK_WAIT = 1.0        # Wait time after clicking refresh button (seconds)
    CONFIRM_CLICK_WAIT = 1.0        # Wait time after clicking confirm button (seconds)
    PAGE_CYCLE_WAIT = 2.0           # Wait time before starting next page cycle (seconds)
    REWARD_OVERLAY_CHECK_DELAY = 1.0  # Initial delay when checking reward overlay (seconds)
    REWARD_OVERLAY_VERIFY_DELAY = 1.0 # Wait after dismissing reward overlay (seconds)
    REFRESH_BUTTON_CHECK_INTERVAL = 1.0  # How often to check refresh button during overlay (seconds)
    CONFIRM_COOLDOWN_CHECK_INTERVAL = 1.0  # How often to check confirm button cooldown (seconds)
    
    # ==============================================================
    
    def __init__(self, log_func, config_path, coords_path, hwnd_list):
        self.log_func = log_func
        self.config_path = config_path
        self.coords_path = coords_path
        self.hwnd_list = hwnd_list
        self.running = False
        
        # Load configuration
        self.load_config()
        
        # Match tracking - simplified (no fail_count)
        self.active_matches = []
        self.completed_count = 0
        self.total_complete = 0
        
        # Retry counters
        self.max_retries = 3
        
        # Window size tracking for restoration
        self.original_window_width = None
        self.original_window_height = None
        self.hwnd_for_resize = None
    
    def log(self, message, tag='system'):
        """Log to both GUI and console"""
        print(f"[{tag.upper()}] {message}")
        self.log_func(message, tag)
    
    def interruptible_sleep(self, seconds):
        """Sleep that can be interrupted by stop signal - checks every 100ms"""
        global _rr_running
        end_time = time.time() + seconds
        check_count = 0
        while time.time() < end_time:
            check_count += 1
            if check_count % 10 == 0:  # Log every 1 second
                print(f"[SLEEP] Sleeping... {int(end_time - time.time())}s remaining (running={self.running}, global={_rr_running})")
            
            if not self.running or not _rr_running:
                print(f"[STOP] Stop detected in sleep! self.running={self.running}, _rr_running={_rr_running}")
                return False
            
            time.sleep(0.1)
        return True
        
    def load_config(self):
        """Load coordinates and colors from coords.ini"""
        # Load reference resolution from config.ini
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        
        # Load reference resolution
        ref = config['REFERENCE']
        self.reference_width = int(ref['width'])
        self.reference_height = int(ref['height'])
        
        # Load target width for restoration (from [GLOBAL] width)
        global_section = config['GLOBAL']
        self.target_restore_width = int(global_section.get('width', self.reference_width))
        
        print(f"\n📐 Reference Resolution: {self.reference_width}x{self.reference_height}")
        print(f"📐 Restore Target Width: {self.target_restore_width}")
        
        cfg = configparser.ConfigParser()
        cfg.read(self.coords_path, encoding='utf-8')
        
        rr = cfg['REALM RAID']
        
        # Timeouts
        self.end_timeout = int(rr.get('end_timeout', 25))
        self.match_timeout = int(rr.get('match_timeout', 120))
        
        # Colors
        self.color_1 = self.hex_to_rgb(rr['1_color'])
        self.color_btn = self.hex_to_rgb(rr['btn_color'])
        self.color_cd = self.hex_to_rgb(rr['cd_color'])
        self.color_fail = self.hex_to_rgb(rr['fail_color'])
        self.color_success = self.hex_to_rgb(rr['success_color'])
        
        # Coordinates - Grid positions
        self.grid_positions = {}
        for row in range(1, 4):
            for col in range(1, 4):
                key = f"{row}{col}"
                coord_1 = self.parse_coord(rr[f'click_{key}_1'])
                coord_2 = self.parse_coord(rr[f'click_{key}_2'])
                self.grid_positions[key] = {'coord_1': coord_1, 'coord_2': coord_2}
        
        # Control coordinates
        self.coord_check_end = self.parse_coord(rr['check_end'])
        self.coord_click_end = self.parse_coord(rr['click_end'])
        self.coord_click_refresh = self.parse_coord(rr['click_refresh'])
        self.coord_click_confirm = self.parse_coord(rr['click_confirm'])
        
    def hex_to_rgb(self, hex_str):
        """Convert hex color string to RGB tuple"""
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    def parse_coord(self, coord_str):
        """Parse coordinate string like '370, 150' to tuple"""
        parts = coord_str.split(',')
        return (int(parts[0].strip()), int(parts[1].strip()))
    
    def get_pixel_color(self, hwnd, client_x, client_y, force_refresh=True):
        """
        Get pixel color from a window's client area using BitBlt.
        Works even if the window is covered or unfocused.
        """
        import ctypes
        from ctypes import wintypes
        import time

        CAPTUREBLT = 0x40000000

        if force_refresh:
            rect = wintypes.RECT()
            rect.left = client_x - 5
            rect.top = client_y - 5
            rect.right = client_x + 5
            rect.bottom = client_y + 5
            user32.InvalidateRect(hwnd, ctypes.byref(rect), False)
            user32.UpdateWindow(hwnd)
            time.sleep(0.05)

        hdc_window = user32.GetDC(hwnd)
        if not hdc_window:
            self.log("Failed to get DC for window", "error")
            return None

        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        if not hdc_mem:
            user32.ReleaseDC(hwnd, hdc_window)
            self.log("Failed to create compatible DC", "error")
            return None

        hbm = gdi32.CreateCompatibleBitmap(hdc_window, 1, 1)
        if not hbm:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_window)
            self.log("Failed to create compatible bitmap", "error")
            return None

        gdi32.SelectObject(hdc_mem, hbm)

        success = gdi32.BitBlt(
            hdc_mem, 0, 0, 1, 1, 
            hdc_window, client_x, client_y, 
            win32con.SRCCOPY | CAPTUREBLT
        )
        
        if not success:
            self.log(f"BitBlt failed at ({client_x},{client_y})", "error")

        pixel = gdi32.GetPixel(hdc_mem, 0, 0)
        r = pixel & 0xFF
        g = (pixel >> 8) & 0xFF
        b = (pixel >> 16) & 0xFF
        rgb = (r, g, b)

        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_window)

        print(f"  🎨 BitBlt color: client({client_x},{client_y}) → RGB{rgb}")
        return rgb
    
    def color_matches(self, color1, color2, tolerance=10):
        """Check if two colors match within tolerance"""
        if color1 is None or color2 is None:
            return False
        return all(abs(c1 - c2) <= tolerance for c1, c2 in zip(color1, color2))
    
    def rgb_to_hex(self, rgb):
        """Convert RGB tuple to hex string for logging"""
        if rgb is None:
            return "None"
        return '#{:02X}{:02X}{:02X}'.format(rgb[0], rgb[1], rgb[2])
    
    def get_window_size(self, hwnd):
        """Get current window client area dimensions"""
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return width, height
    
    def get_window_outer_size(self, hwnd):
        """Get current window outer dimensions (including borders and title bar)"""
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return width, height
    
    def resize_window_to_reference(self, hwnd):
        """
        Resize window to reference resolution if needed.
        Does NOT modify config.ini - only resizes the window temporarily.
        Stores original window size for later restoration.
        
        NOTE: reference_width is WINDOW size (includes borders/title bar), NOT client size.
        """
        self.hwnd_for_resize = hwnd  # Store hwnd for later restoration
        
        # Get WINDOW size (outer dimensions including borders)
        current_window_width, current_window_height = self.get_window_outer_size(hwnd)
        
        # Get CLIENT size (drawable area) for info
        current_client_width, current_client_height = self.get_window_size(hwnd)
        
        # Store original WINDOW size before any resizing
        self.original_window_width = current_window_width
        self.original_window_height = current_window_height
        
        print(f"\n📐 Window Size Check:")
        print(f"   Current WINDOW size:  {current_window_width}x{current_window_height} (outer)")
        print(f"   Current CLIENT size:  {current_client_width}x{current_client_height} (drawable)")
        print(f"   Reference WINDOW:     {self.reference_width}x{self.reference_height}")
        print(f"   Will restore to:      {self.target_restore_width}x??? (from config.ini)")
        
        if current_window_width != self.reference_width:
            print(f"\n⚠️  Window width mismatch detected!")
            self.log(f"Window width is {current_window_width}, resizing to {self.reference_width}", 'system')
            
            # Get current window position
            window_rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            
            # Resize window directly to reference dimensions (WINDOW size, not client)
            success = user32.SetWindowPos(
                hwnd,
                0,  # HWND_TOP
                window_rect.left,  # Keep current X position
                window_rect.top,   # Keep current Y position
                self.reference_width,   # WINDOW width (includes borders)
                self.reference_height,  # WINDOW height (includes borders)
                0x0004  # SWP_NOZORDER
            )
            
            if success:
                time.sleep(0.5)  # Wait for resize to complete
                
                # Verify resize
                new_window_width, new_window_height = self.get_window_outer_size(hwnd)
                new_client_width, new_client_height = self.get_window_size(hwnd)
                
                print(f"\n✓ Window resized successfully!")
                print(f"   New WINDOW size: {new_window_width}x{new_window_height}")
                print(f"   New CLIENT size: {new_client_width}x{new_client_height}")
                self.log(f"Window resized to {new_window_width}x{new_window_height} (outer)", 'success')
                
                if new_window_width != self.reference_width:
                    print(f"\n⚠️  Warning: Resize may not be exact (got {new_window_width}, expected {self.reference_width})")
                    self.log(f"Warning: Window width is {new_window_width}, expected {self.reference_width}", 'error')
                
                # CRITICAL: Wait for game to re-render UI at new resolution
                print(f"\n⏳ Waiting for game to re-render UI at new resolution...")
                self.log("Waiting 3 seconds for game UI to stabilize after resize", 'system')
                time.sleep(3.0)  # Give game time to fully redraw UI elements
                
                # Force window refresh to clear any cached rendering
                user32.InvalidateRect(hwnd, None, True)
                user32.UpdateWindow(hwnd)
                gdi32.GdiFlush()
                time.sleep(0.5)
                
                print(f"✓ Game UI should be ready")
                self.log("Game UI re-render complete", 'success')
                
                # Optional: Verify UI is ready by checking a known position
                # This helps catch cases where the game needs even more time
                print(f"\n🔍 Verifying UI is ready by checking refresh button...")
                try:
                    test_color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
                    if test_color:
                        print(f"   ✓ UI verification successful - color detected: {self.rgb_to_hex(test_color)}")
                        self.log("UI ready verification successful", 'success')
                    else:
                        print(f"   ⚠️  Warning: Could not verify UI readiness")
                        self.log("UI verification failed - proceeding anyway", 'error')
                except Exception as e:
                    print(f"   ⚠️  UI verification error: {e}")
                    self.log(f"UI verification error: {e}", 'error')
            else:
                print(f"\n✗ Failed to resize window")
                self.log("Failed to resize window", 'error')
                return False
        else:
            print(f"✓ Window size is correct")
            self.log("Window size matches reference resolution", 'success')
        
        print("="*20)
        return True
    
    def restore_window_size(self):
        """
        Restore window to the target width from config.ini [GLOBAL] width.
        Called when automation stops (button clicked, tickets exhausted, or error).
        
        NOTE: Restoration uses WINDOW size (includes borders/title bar).
        """
        if not self.hwnd_for_resize or not self.original_window_width:
            print(f"\n⚠️  No window resize data available - skipping restoration")
            return
        
        hwnd = self.hwnd_for_resize
        
        print(f"\n" + "="*20)
        print(f"🔄 RESTORING WINDOW SIZE")
        print(f"="*20)
        
        # Get current WINDOW size
        current_window_width, current_window_height = self.get_window_outer_size(hwnd)
        current_client_width, current_client_height = self.get_window_size(hwnd)
        
        print(f"   Current WINDOW size:  {current_window_width}x{current_window_height}")
        print(f"   Current CLIENT size:  {current_client_width}x{current_client_height}")
        print(f"   Original WINDOW size: {self.original_window_width}x{self.original_window_height}")
        print(f"   Target WINDOW width:  {self.target_restore_width} (from config.ini)")
        
        # Calculate target height maintaining aspect ratio
        aspect_ratio = self.original_window_height / self.original_window_width
        target_height = int(self.target_restore_width * aspect_ratio)
        
        if current_window_width == self.target_restore_width:
            print(f"\n✓ Window already at target width")
            self.log("Window already at target width - no restoration needed", 'success')
        else:
            self.log(f"Restoring window to {self.target_restore_width}x{target_height}", 'system')
            
            # Get current window position
            window_rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            
            # Resize window directly (WINDOW size, not client)
            success = user32.SetWindowPos(
                hwnd,
                0,  # HWND_TOP
                window_rect.left,  # Keep current X position
                window_rect.top,   # Keep current Y position
                self.target_restore_width,  # WINDOW width
                target_height,              # WINDOW height
                0x0004  # SWP_NOZORDER
            )
            
            if success:
                time.sleep(0.3)  # Wait for resize to complete
                
                # Verify resize
                restored_window_width, restored_window_height = self.get_window_outer_size(hwnd)
                restored_client_width, restored_client_height = self.get_window_size(hwnd)
                
                print(f"\n✓ Window restored successfully!")
                print(f"   Restored WINDOW size: {restored_window_width}x{restored_window_height}")
                print(f"   Restored CLIENT size: {restored_client_width}x{restored_client_height}")
                self.log(f"Window restored to {restored_window_width}x{restored_window_height}", 'success')
            else:
                print(f"\n✗ Failed to restore window")
                self.log("Failed to restore window size", 'error')
        
        print("="*20)
    
    def log_color_mismatch(self, location, expected_color, actual_color, expected_name="expected"):
        """Log detailed color mismatch for debugging"""
        self.log(
            f"Color mismatch at {location}: "
            f"{expected_name}={self.rgb_to_hex(expected_color)}, "
            f"found={self.rgb_to_hex(actual_color)}", 
            'error'
        )
    
    def send_click(self, hwnd, x, y):
        """Send non-intrusive click to window at client coordinates"""
        try:
            print(f"\n  🖱️  CLICKING at position ({x:4d}, {y:4d})")
            print(f"     └─ HWND: {hwnd}")
            
            lparam = win32api.MAKELONG(x, y)
            
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(self.CLICK_DELAY)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            
            print(f"     └─ ✓ Click sent")
            return True
        except Exception as e:
            print(f"     └─ ✗ Click failed: {e}")
            self.log(f"Error sending click: {e}", 'error')
            return False
    
    def check_initial_grid(self, hwnd):
        """Check all 9 grid positions - categorize as active (1_color) or completed/attempted"""
        global _rr_running
        
        print("\n" + "="*20)
        print("🔍 CHECKING GRID STATE")
        print("="*20)
        self.log("Checking initial grid state...", 'system')
        self.active_matches = []
        attempted_count = 0
        
        print(f"\nExpected colors:")
        print(f"  • Active (1_color):    {self.rgb_to_hex(self.color_1)}")
        print(f"  • Completed/Attempted: NOT 1_color\n")
        
        for key in ['11', '12', '13', '21', '22', '23', '31', '32', '33']:
            if not self.running or not _rr_running:
                print(f"[STOP] Stop detected during grid check")
                return False
            
            coord = self.grid_positions[key]['coord_1']
            print(f"\n📍 Position {key}: Checking ({coord[0]:4d}, {coord[1]:4d})")
            
            color = self.get_pixel_color(hwnd, coord[0], coord[1])
            
            if self.color_matches(color, self.color_1):
                self.active_matches.append(key)
                print(f"   ✓ ACTIVE - color matches 1_color")
                self.log(f"Position {key}: Active (color={self.rgb_to_hex(color)})", 'system')
            else:
                attempted_count += 1
                print(f"   ○ COMPLETED/ATTEMPTED - color doesn't match 1_color")
                self.log(f"Position {key}: Completed/Attempted (color={self.rgb_to_hex(color)})", 'success')
        
        # Calculate run position
        run_position = attempted_count + 1 if self.active_matches else 9
        total_runs = 9
        
        print("\n" + "-"*60)
        print(f"GRID SUMMARY:")
        print(f"  • Active matches:        {len(self.active_matches)} - {self.active_matches}")
        print(f"  • Completed/Attempted:   {attempted_count}")
        print(f"  • Run position:          {run_position}/{total_runs}")
        print("-"*60)
        
        self.log(f"Grid check complete: {len(self.active_matches)} active, {attempted_count} completed/attempted, run {run_position}/{total_runs}", 'system')
        return True
    
    def wait_for_lobby_return(self, hwnd):
        """
        Wait for return to lobby by checking for refresh button.
        Keeps clicking end button until refresh button appears.
        """
        print(f"\n🔹 Returning to lobby...")
        self.log("Waiting for return to lobby", 'system')
        
        max_attempts = 10
        for attempt in range(max_attempts):
            if not self.running or not _rr_running:
                print("[STOP] Stop signal during lobby return")
                return False
            
            print(f"\n  Attempt {attempt + 1}/{max_attempts}: Checking for refresh button")
            color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
            
            if self.color_matches(color, self.color_btn) or self.color_matches(color, self.color_cd):
                print(f"     ✓ Refresh button detected - Back in lobby!")
                self.log("Successfully returned to lobby", 'success')
                return True
            else:
                print(f"     ✗ Not in lobby yet - clicking end button")
                self.send_click(hwnd, self.coord_click_end[0], self.coord_click_end[1])
                
                if not self.interruptible_sleep(self.REFRESH_BUTTON_CHECK_INTERVAL):
                    print("[STOP] Stop signal during lobby wait")
                    return False
        
        print(f"     ✗ Failed to return to lobby after {max_attempts} attempts")
        self.log("Failed to return to lobby", 'error')
        return False
    
    def refresh_page_if_needed(self, hwnd):
        """
        Check if refresh is needed and perform it.
        Handles both active refresh button and cooldown wait.
        Verifies refresh click was successful before proceeding.
        """
        self.log("Checking if page refresh is needed...", 'system')
        
        # Check refresh button state
        color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
        
        if self.color_matches(color, self.color_btn):
            # Refresh button is active - click it
            self.log("Refresh button active - clicking refresh", 'control')
            self.send_click(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
            
            if not self.interruptible_sleep(self.REFRESH_CLICK_WAIT):
                return False
            
            # VERIFY: Check if refresh click was successful
            print(f"\n  🔍 Verifying refresh click...")
            refresh_color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
            confirm_color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
            
            # Check if overlay opened (refresh button disappeared, confirm button appeared)
            if not (self.color_matches(refresh_color, self.color_btn) or self.color_matches(refresh_color, self.color_cd)):
                if self.color_matches(confirm_color, self.color_btn):
                    print(f"     ✓ Confirm overlay detected - refresh click successful")
                    self.log("Refresh overlay opened successfully", 'success')
                    # Handle confirm button
                    return self.handle_confirm_button(hwnd)
                else:
                    print(f"     ⚠️  Refresh click might have been missed - retrying")
                    self.log("Refresh click verification failed - retrying", 'error')
                    # Retry the whole refresh process
                    return self.refresh_page_if_needed(hwnd)
            else:
                # Refresh button still visible - might be on cooldown now
                if self.color_matches(refresh_color, self.color_cd):
                    self.log("Refresh button now on cooldown", 'system')
                    return self.wait_for_confirm_cooldown(hwnd)
                else:
                    # Button still active but overlay didn't open - retry
                    print(f"     ⚠️  Overlay didn't open - retrying")
                    self.log("Refresh overlay didn't open - retrying", 'error')
                    return self.refresh_page_if_needed(hwnd)
            
        elif self.color_matches(color, self.color_cd):
            # Refresh on cooldown - wait for it to become active
            self.log("Refresh button on cooldown - waiting for it to become active", 'system')
            return self.wait_for_confirm_cooldown(hwnd)
        else:
            # No refresh needed (page auto-refreshed)
            self.log("No manual refresh needed", 'system')
            return True
    
    def handle_confirm_button(self, hwnd):
        """
        Check and click confirm button with retry.
        Verifies the click was successful by checking if button disappeared.
        """
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                print("[STOP] Stop signal during confirm")
                return False
            
            color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
            
            if self.color_matches(color, self.color_btn):
                self.log("Clicking confirm button", 'control')
                self.send_click(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.interruptible_sleep(self.CONFIRM_CLICK_WAIT):
                    return False
                
                # VERIFY: Check if confirm click was successful
                print(f"\n  🔍 Verifying confirm click...")
                verify_color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if self.color_matches(verify_color, self.color_btn):
                    # Button still visible - click might have been missed
                    print(f"     ⚠️  Confirm button still visible - retrying")
                    self.log(f"Confirm click verification failed (attempt {attempt + 1}/{self.max_retries})", 'error')
                    continue
                else:
                    # Button disappeared - refresh successful
                    print(f"     ✓ Confirm button disappeared - refresh successful")
                    self.log("Page refreshed successfully", 'success')
                    return True
                
            elif self.color_matches(color, self.color_cd):
                # Confirm is on cooldown - wait
                self.log(f"Confirm button on cooldown (attempt {attempt + 1}/{self.max_retries})", 'system')
                return self.wait_for_confirm_cooldown(hwnd)
            else:
                self.log(f"Confirm button not available (attempt {attempt + 1}/{self.max_retries})", 'error')
                if not self.interruptible_sleep(self.REFRESH_CLICK_WAIT):
                    return False
        
        self.log("Failed to click confirm button after max attempts - ending refresh process", 'error')
        return True  # Return True to go back to initial page check
    
    def wait_for_confirm_cooldown(self, hwnd):
        """
        Wait for confirm button cooldown to finish, then click it.
        Does NOT timeout - keeps waiting until button becomes active.
        Verifies the click was successful.
        """
        self.log("Waiting for confirm button cooldown to finish...", 'system')
        
        check_count = 0
        while self.running and _rr_running:
            check_count += 1
            print(f"\n  Cooldown check #{check_count}: Checking confirm button")
            
            color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
            
            if self.color_matches(color, self.color_btn):
                print(f"     ✓ Cooldown finished - clicking confirm")
                self.log("Confirm button cooldown finished", 'success')
                self.send_click(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.interruptible_sleep(self.CONFIRM_CLICK_WAIT):
                    return False
                
                # VERIFY: Check if confirm click was successful
                print(f"\n  🔍 Verifying confirm click...")
                verify_color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if self.color_matches(verify_color, self.color_btn):
                    # Button still visible - click might have been missed, retry
                    print(f"     ⚠️  Confirm button still visible - continuing to wait")
                    self.log("Confirm click verification failed - continuing to wait", 'error')
                    if not self.interruptible_sleep(self.CONFIRM_COOLDOWN_CHECK_INTERVAL):
                        return False
                    continue
                else:
                    # Button disappeared - refresh successful
                    print(f"     ✓ Confirm button disappeared - refresh successful")
                    self.log("Page refreshed successfully", 'success')
                    return True
            else:
                print(f"     ○ Still on cooldown - waiting...")
                if not self.interruptible_sleep(self.CONFIRM_COOLDOWN_CHECK_INTERVAL):
                    print("[STOP] Stop signal during cooldown wait")
                    return False
        
        return False
    
    def process_single_match(self, hwnd, position_key):
        """Process a single match from start to completion"""
        global _rr_running
        
        print(f"\n{'='*60}")
        print(f"🎮 PROCESSING MATCH: Position {position_key}")
        print(f"{'='*60}")
        self.log(f"Processing match at position {position_key}", 'control')
        
        coord_1 = self.grid_positions[position_key]['coord_1']
        coord_2 = self.grid_positions[position_key]['coord_2']
        
        print(f"\nCoordinates for position {position_key}:")
        print(f"  • Click coord (coord_1): ({coord_1[0]:4d}, {coord_1[1]:4d})")
        print(f"  • Join button (coord_2): ({coord_2[0]:4d}, {coord_2[1]:4d})")
        
        # Step 1: Click to expand match
        print(f"\n🔹 STEP 1: Expanding match")
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                print("[STOP] Stop signal detected during match expansion")
                return False
            
            print(f"\n  Attempt {attempt + 1}/{self.max_retries}")
            self.log(f"Clicking match at position {position_key} (attempt {attempt + 1})", 'control')
            self.send_click(hwnd, coord_1[0], coord_1[1])
            
            print(f"\n  ⏱️  Waiting {self.EXPANSION_WAIT}s for expansion...")
            if not self.interruptible_sleep(self.EXPANSION_WAIT):
                print("[STOP] Stop signal during expansion wait")
                return False
            
            print(f"\n  🔍 Checking for join button:")
            print(f"     Expected color: {self.rgb_to_hex(self.color_btn)}")
            color = self.get_pixel_color(hwnd, coord_2[0], coord_2[1])
            
            if self.color_matches(color, self.color_btn):
                print(f"     ✓ Match expanded! Join button detected")
                self.log(f"Match expanded successfully, join button detected", 'success')
                break
            else:
                print(f"     ✗ Button not found - Color mismatch")
                self.log(f"Match didn't expand, retrying...", 'error')
                self.log_color_mismatch(f"position {position_key} join button", self.color_btn, color, "btn_color")
                if attempt == self.max_retries - 1:
                    print(f"     ✗ FAILED after {self.max_retries} attempts")
                    self.log("Failed to expand match after max attempts", 'error')
                    return False
        
        # Step 2: Click join button
        print(f"\n🔹 STEP 2: Joining match")
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                print("[STOP] Stop signal detected during join")
                return False
            
            print(f"\n  Attempt {attempt + 1}/{self.max_retries}")
            self.log("Clicking join button", 'control')
            self.send_click(hwnd, coord_2[0], coord_2[1])
            
            print(f"\n  ⏱️  Waiting {self.JOIN_WAIT}s...")
            if not self.interruptible_sleep(self.JOIN_WAIT):
                print("[STOP] Stop signal during join wait")
                return False
            
            print(f"\n  🔍 Checking if button disappeared:")
            color = self.get_pixel_color(hwnd, coord_2[0], coord_2[1])
            
            if self.color_matches(color, self.color_btn):
                print(f"     ⚠️  Button still visible!")
                if attempt == self.max_retries - 1:
                    print(f"     ✗ ENTRY COUNT EXHAUSTED")
                    self.log("Entry Count Exhausted - button still visible after max attempts", 'error')
                    return "ENTRY_EXHAUSTED"
            else:
                print(f"     ✓ Button disappeared - Successfully joined match")
                self.log("Successfully joined match", 'success')
                break
        
        # Step 3: Wait for match completion
        print(f"\n🔹 STEP 3: Waiting for match to complete (timeout: {self.match_timeout}s)")
        self.log(f"Waiting for match completion (timeout: {self.match_timeout}s)", 'system')
        start_time = time.time()
        match_ended = False
        check_count = 0
        
        while time.time() - start_time < self.match_timeout:
            if not self.running or not _rr_running:
                print("[STOP] Stop signal detected during match")
                return False
            
            check_count += 1
            elapsed = int(time.time() - start_time)
            print(f"\n  Check #{check_count} at {elapsed}s - Checking for match end signal:")
            print(f"     Expected: {self.rgb_to_hex(self.color_fail)} (fail) or {self.rgb_to_hex(self.color_success)} (success)")
            
            if not self.interruptible_sleep(self.MATCH_CHECK_INTERVAL):
                print("[STOP] Stop signal during match wait")
                return False
            
            color = self.get_pixel_color(hwnd, self.coord_check_end[0], self.coord_check_end[1])
            
            if self.color_matches(color, self.color_fail) or self.color_matches(color, self.color_success):
                result = "fail" if self.color_matches(color, self.color_fail) else "success"
                print(f"     {'✗' if result == 'fail' else '✓'} Match {result.upper()}")
                self.log(f"Match ended: {result}", 'error' if result == 'fail' else 'success')
                self.send_click(hwnd, self.coord_click_end[0], self.coord_click_end[1])
                match_ended = True
                self.total_complete += 1
                break
            else:
                print(f"     ○ Match still in progress...")
        
        if not match_ended:
            print(f"     ✗ TIMEOUT - No end signal detected after {self.match_timeout}s")
            self.log("Match timeout reached - no end signal detected", 'error')
            return False
        
        # Step 4: Wait for return to lobby (handles reward overlays)
        if not self.wait_for_lobby_return(hwnd):
            return False
        
        print(f"{'='*60}\n")
        return True
    
    def run(self):
        """Main automation loop"""
        global _rr_running
        
        self.running = True
        _rr_running = True
        
        print("\n" + "="*20)
        print("[START] Realm Raid Automation Starting")
        print("="*20)
        self.log("Starting Realm Raid automation", 'system')
        self.log("=" * 20, 'system')
        
        if not self.hwnd_list:
            self.log("No windows available", 'error')
            self.running = False
            _rr_running = False
            return
        
        hwnd = self.hwnd_list[0]._hWnd
        print(f"[DEBUG] Using HWND: {hwnd}")
        self.log(f"Using HWND: {hwnd}", 'system')
        self.log("=" * 20, 'system')
        
        # Check and resize window if needed
        print("\n" + "="*20)
        print("🔧 PRE-AUTOMATION WINDOW CHECK")
        print("="*20)
        if not self.resize_window_to_reference(hwnd):
            self.log("Window resize failed - stopping automation", 'error')
            self.running = False
            _rr_running = False
            return
        
        try:
            while self.running and _rr_running:
                print(f"\n[LOOP] Flags check - self.running={self.running}, _rr_running={_rr_running}")
                
                if not self.running or not _rr_running:
                    print("[STOP] Stop detected at loop start")
                    break
                
                # Check grid state
                self.log("Starting new page scan...", 'system')
                if not self.check_initial_grid(hwnd):
                    self.log("Grid check failed or stopped by user", 'error')
                    break
                
                self.log("=" * 20, 'system')
                self.log(f"SUMMARY: Found {len(self.active_matches)} active matches to process", 'system')
                self.log(f"Active match positions: {', '.join(self.active_matches) if self.active_matches else 'None'}", 'system')
                self.log("=" * 20, 'system')
                
                # Check if there are matches to process
                if not self.active_matches:
                    self.log("No active matches found on this page", 'system')
                    
                    # Check if refresh is needed
                    if not self.refresh_page_if_needed(hwnd):
                        self.log("Failed to refresh page", 'error')
                        break
                    
                    # Check grid again
                    if not self.interruptible_sleep(self.PAGE_CYCLE_WAIT):
                        break
                    
                    if not self.check_initial_grid(hwnd):
                        break
                    
                    if not self.active_matches:
                        self.log("All matches completed for this session", 'success')
                        break
                    else:
                        self.log(f"Page refreshed, found {len(self.active_matches)} new matches", 'system')
                
                # Process each active match
                self.log(f"Beginning to process {len(self.active_matches)} matches...", 'control')
                for idx, position in enumerate(self.active_matches[:], 1):
                    if not self.running or not _rr_running:
                        print("[STOP] Stop requested by user during match processing")
                        self.log("Stop requested by user", 'system')
                        break
                    
                    self.log("=" * 20, 'control')
                    self.log(f"Match {idx}/{len(self.active_matches)}: Position {position}", 'control')
                    self.log("=" * 20, 'control')
                    
                    result = self.process_single_match(hwnd, position)
                    
                    if result == "ENTRY_EXHAUSTED":
                        self.log("Stopping: Entry count exhausted", 'error')
                        self.running = False
                        _rr_running = False
                        # Restore window before stopping
                        self.restore_window_size()
                        break
                    elif not result:
                        self.log(f"Failed to process match {position}, continuing to next", 'error')
                        continue
                
                # After processing all matches, check if refresh needed
                if self.running and _rr_running:
                    self.log("Page processing complete, checking for refresh...", 'system')
                    if not self.refresh_page_if_needed(hwnd):
                        self.log("Failed to refresh page", 'error')
                        break
                
                # Reset for next iteration
                self.active_matches = []
                self.completed_count = 0
                
                # Small delay before next cycle
                if self.running and _rr_running:
                    self.log("Preparing for next page cycle...", 'system')
                    if not self.interruptible_sleep(self.PAGE_CYCLE_WAIT):
                        print("[STOP] Stop during cycle preparation")
                        break
                else:
                    print(f"[STOP] Stop detected before next cycle")
                    break
                
        except Exception as e:
            self.log(f"Error in automation loop: {e}", 'error')
            import traceback
            error_trace = traceback.format_exc()
            self.log(f"Traceback: {error_trace}", 'error')
            print(f"\n[ERROR] Exception occurred:")
            print(error_trace)
        finally:
            # Restore window size before stopping
            self.restore_window_size()
            
            self.running = False
            _rr_running = False
            print("\n" + "="*20)
            print("[END] Realm Raid automation stopped")
            print("="*20)
            self.log("=" * 20, 'system')
            self.log("Realm Raid automation stopped", 'system')
            self.log("=" * 20, 'system')

def run_rr_mode(log_func, config_path, coords_path, hwnd_list):
    """Start Realm Raid mode in a separate thread"""
    global _rr_running, _rr_thread, _rr_automation_instance
    
    if _rr_running:
        log_func("Realm Raid mode already running", 'error')
        return
    
    _rr_running = True
    _rr_automation_instance = RealmRaidAutomation(log_func, config_path, coords_path, hwnd_list)
    
    def thread_target():
        global _rr_running
        _rr_automation_instance.run()
        _rr_running = False
    
    _rr_thread = threading.Thread(target=thread_target, daemon=True)
    _rr_thread.start()
    
    log_func("Realm Raid mode thread started", 'system')

def stop_rr_mode():
    """Stop Realm Raid mode"""
    global _rr_running, _rr_automation_instance
    
    print("\n" + "!"*60)
    print("[STOP] STOP BUTTON PRESSED - Stopping automation...")
    print("!"*60)
    
    if _rr_running and _rr_automation_instance:
        print(f"[STOP] Setting automation.running to False")
        _rr_automation_instance.running = False
        _rr_running = False
        print(f"[STOP] Flags set: _rr_running={_rr_running}, automation.running={_rr_automation_instance.running}")
        
        # Note: Window restoration will be handled by the finally block in run()
        # No need to call restore_window_size() here as it will be called automatically
        
        return True
    else:
        print("[STOP] No active automation found")
    
    return False