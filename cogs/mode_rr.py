import threading
import time
import configparser
import ctypes
from ctypes import wintypes
import win32gui
import win32ui
import win32api
import win32con
import cv2
import numpy as np
import os
from ctypes import windll

# Global control flags
_rr_running = False
_rr_thread = None
_rr_automation_instance = None

# Windows API setup
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

class RealmRaidAutomation:
    # ==================== TIMING CONFIGURATION ====================
    CLICK_DELAY = 0.05
    EXPANSION_WAIT = 1.0
    JOIN_WAIT = 1.0
    MATCH_CHECK_INTERVAL = 1.0
    LOBBY_RETURN_WAIT = 1.5
    LOBBY_VERIFY_WAIT = 1.0
    REFRESH_CLICK_WAIT = 1.0
    CONFIRM_CLICK_WAIT = 1.0
    PAGE_CYCLE_WAIT = 1.0
    REWARD_OVERLAY_CHECK_DELAY = 1.0
    REWARD_OVERLAY_VERIFY_DELAY = 1.0
    REFRESH_BUTTON_CHECK_INTERVAL = 1.0
    CONFIRM_COOLDOWN_CHECK_INTERVAL = 1.0
    FROGLET_CLICK_DELAY = 0.2
    FROGLET_CLICK_COUNT = 3
    FROGLET_LOAD_TIME = 2.0
    # ==============================================================
    
    def __init__(self, log_func, config_path, coords_path, target_hwnd):
        """
        Args:
            log_func: Logging function
            config_path: Path to config.ini
            coords_path: Path to coords.ini
            target_hwnd: The HWND of the specific window to automate (integer)
        """
        self.log_func = log_func
        self.config_path = config_path
        self.coords_path = coords_path
        self.target_hwnd = target_hwnd  # Store the specific target HWND
        self.running = False
        
        # Initialize templates dict FIRST
        self.templates = {}
        
        # Load configuration
        self.load_config()
        
        # Match tracking
        self.ko_matches = []
        self.fail_matches = []
        self.froglet_matches = []
        self.available_matches = []
        self.completed_count = 0
        self.total_complete = 0
        
        # Retry counters
        self.max_retries = 3
        
        # Window size tracking
        self.original_window_width = None
        self.original_window_height = None
        self.hwnd_for_resize = None
        
        # Load template images
        self.load_templates()
    
    def log(self, message, tag='system'):
        """Log to both GUI and console"""
        print(f"[{tag.upper()}] {message}")
        self.log_func(message, tag)
    
    def load_templates(self):
        """Load template images for detection"""
        template_dir = os.path.join('cogs', 'ref')
        
        print(f"\n📂 Loading template images from: {template_dir}")
        
        if not os.path.exists(template_dir):
            error_msg = f"Template directory not found: {template_dir}"
            print(f"\n❌ {error_msg}")
            print(f"Please create the directory: mkdir {template_dir}")
            self.log(f"ERROR: {error_msg}", 'error')
            raise FileNotFoundError(error_msg)
        
        templates = {
            'ko': 'rr_ko.png',
            'fail': 'rr_fail.png',
            'froglet': 'rr_froglet.png'
        }
        
        missing_files = []
        
        for key, filename in templates.items():
            filepath = os.path.join(template_dir, filename)
            
            if not os.path.exists(filepath):
                print(f"  ❌ Template not found: {filepath}")
                missing_files.append(filepath)
                continue
            
            template = cv2.imread(filepath)
            if template is None:
                print(f"  ❌ Failed to load: {filepath}")
                self.log(f"ERROR: Failed to load template: {filepath}", 'error')
                raise ValueError(f"Failed to load template: {filepath}")
            
            self.templates[key] = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            h, w = self.templates[key].shape[:2]
            print(f"  ✓ Loaded '{key}': {filename} ({w}x{h})")
        
        if missing_files:
            error_msg = f"Missing {len(missing_files)} template file(s):\n"
            for filepath in missing_files:
                error_msg += f"  - {filepath}\n"
            print(f"\n❌ {error_msg}")
            self.log(f"ERROR: {error_msg}", 'error')
            raise FileNotFoundError(error_msg)
        
        self.log(f"Loaded {len(self.templates)} template images", 'success')
    
    def capture_full_window(self, hwnd):
        """Capture the entire window - NON-INTRUSIVE"""
        try:
            left, top, right, bot = win32gui.GetClientRect(hwnd)
            width = right - left
            height = bot - top
            
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(bitmap)
            
            result = windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
            
            bmpstr = bitmap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))
            
            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
            
        except Exception as e:
            print(f"  ❌ Error capturing full window: {e}")
            return None
    
    def capture_window_region(self, hwnd, x, y, width, height):
        """Capture a specific region of the window"""
        try:
            full_img = self.capture_full_window(hwnd)
            if full_img is None:
                return None
            
            h, w = full_img.shape[:2]
            
            x1 = max(0, min(x, w))
            y1 = max(0, min(y, h))
            x2 = max(0, min(x + width, w))
            y2 = max(0, min(y + height, h))
            
            region = full_img[y1:y2, x1:x2]
            return region
            
        except Exception as e:
            print(f"  ❌ Error capturing region: {e}")
            return None
    
    def detect_template_near_coord(self, hwnd, x, y, template_key, search_radius=100, threshold=0.75):
        """Detect if a template matches near a coordinate"""
        try:
            template = self.templates.get(template_key)
            if template is None:
                print(f"  ❌ Template '{template_key}' not loaded")
                return False, 0.0
            
            th, tw = template.shape[:2]
            
            capture_w = max(tw + 40, search_radius * 2)
            capture_h = max(th + 40, search_radius * 2)
            capture_x = x - capture_w // 2
            capture_y = y - capture_h // 2
            
            region = self.capture_window_region(hwnd, capture_x, capture_y, capture_w, capture_h)
            if region is None:
                return False, 0.0
            
            region_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            
            result = cv2.matchTemplate(region_gray, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            matched = max_val >= threshold
            
            if matched:
                print(f"    ✓ '{template_key}' matched (confidence: {max_val:.3f})")
            else:
                print(f"    ○ '{template_key}' not matched (confidence: {max_val:.3f} < {threshold})")
            
            return matched, max_val
            
        except Exception as e:
            print(f"  ❌ Error in template detection: {e}")
            return False, 0.0
    
    def interruptible_sleep(self, seconds):
        """Sleep that can be interrupted by stop signal"""
        global _rr_running
        
        end_time = time.time() + seconds
        check_count = 0
        while time.time() < end_time:
            check_count += 1
            if check_count % 10 == 0:
                print(f"[SLEEP] Sleeping... {int(end_time - time.time())}s remaining")
            
            if not self.running or not _rr_running:
                print(f"[STOP] Stop detected in sleep!")
                return False
            
            time.sleep(0.1)
        return True
    
    def load_config(self):
        """Load coordinates and colors from coords.ini"""
        config = configparser.ConfigParser()
        config.read(self.config_path, encoding='utf-8')
        
        ref = config['REFERENCE']
        self.reference_width = int(ref['width'])
        self.reference_height = int(ref['height'])
        
        global_section = config['GLOBAL']
        self.target_restore_width = int(global_section.get('width', self.reference_width))
        
        print(f"\n📐 Reference Resolution: {self.reference_width}x{self.reference_height}")
        print(f"📐 Restore Target Width: {self.target_restore_width}")
        
        cfg = configparser.ConfigParser()
        cfg.read(self.coords_path, encoding='utf-8')
        
        rr = cfg['REALM RAID']
        
        self.end_timeout = int(rr.get('end_timeout', 25))
        self.match_timeout = int(rr.get('match_timeout', 120))
        
        self.color_1 = self.hex_to_rgb(rr['1_color'])
        self.color_btn = self.hex_to_rgb(rr['btn_color'])
        self.color_cd = self.hex_to_rgb(rr['cd_color'])
        self.color_fail = self.hex_to_rgb(rr['fail_color'])
        self.color_success = self.hex_to_rgb(rr['success_color'])
        
        self.grid_positions = {}
        for row in range(1, 4):
            for col in range(1, 4):
                key = f"{row}{col}"
                coord_1 = self.parse_coord(rr[f'click_{key}_1'])
                coord_2 = self.parse_coord(rr[f'click_{key}_2'])
                self.grid_positions[key] = {'coord_1': coord_1, 'coord_2': coord_2}
        
        self.coord_check_end = self.parse_coord(rr['check_end'])
        self.coord_click_end = self.parse_coord(rr['click_end'])
        self.coord_click_refresh = self.parse_coord(rr['click_refresh'])
        self.coord_click_confirm = self.parse_coord(rr['click_confirm'])
        
        solo = cfg['SOLO']
        self.coord_froglet_click = self.parse_coord(solo['click_solo'])
        print(f"📍 Froglet click coordinate: {self.coord_froglet_click}")
    
    def hex_to_rgb(self, hex_str):
        """Convert hex color string to RGB tuple"""
        hex_str = hex_str.lstrip('#')
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    
    def parse_coord(self, coord_str):
        """Parse coordinate string like '370, 150' to tuple"""
        parts = coord_str.split(',')
        return (int(parts[0].strip()), int(parts[1].strip()))
    
    def get_pixel_color(self, hwnd, client_x, client_y, force_refresh=True):
        """Get pixel color from a window's client area using BitBlt"""
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
        """Get current window outer dimensions"""
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return width, height
    
    def resize_window_to_reference(self, hwnd):
        """Resize window to reference resolution if needed"""
        self.hwnd_for_resize = hwnd
        
        current_window_width, current_window_height = self.get_window_outer_size(hwnd)
        current_client_width, current_client_height = self.get_window_size(hwnd)
        
        self.original_window_width = current_window_width
        self.original_window_height = current_window_height
        
        print(f"\n📐 Window Size Check:")
        print(f"   Current WINDOW size:  {current_window_width}x{current_window_height}")
        print(f"   Current CLIENT size:  {current_client_width}x{current_client_height}")
        print(f"   Reference WINDOW:     {self.reference_width}x{self.reference_height}")
        
        if current_window_width != self.reference_width:
            print(f"\n⚠️  Window width mismatch detected!")
            self.log(f"Window width is {current_window_width}, resizing to {self.reference_width}", 'system')
            
            window_rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            
            success = user32.SetWindowPos(
                hwnd, 0,
                window_rect.left, window_rect.top,
                self.reference_width, self.reference_height,
                0x0004
            )
            
            if success:
                time.sleep(0.5)
                
                new_window_width, new_window_height = self.get_window_outer_size(hwnd)
                
                print(f"\n✓ Window resized successfully!")
                print(f"   New WINDOW size: {new_window_width}x{new_window_height}")
                self.log(f"Window resized to {new_window_width}x{new_window_height}", 'success')
                
                print(f"\n⏳ Waiting for game to re-render UI...")
                self.log("Waiting 1 second for game UI to stabilize", 'system')
                time.sleep(1.0)
                
                user32.InvalidateRect(hwnd, None, True)
                user32.UpdateWindow(hwnd)
                gdi32.GdiFlush()
                time.sleep(0.5)
                
                self.log("Game UI re-render complete", 'success')
            else:
                print(f"\n✗ Failed to resize window")
                self.log("Failed to resize window", 'error')
                return False
        else:
            print(f"✓ Window size is correct")
            self.log("Window size matches reference resolution", 'success')
        
        return True
    
    def restore_window_size(self):
        """Restore window to target width from config.ini"""
        if not self.hwnd_for_resize or not self.original_window_width:
            print(f"\n⚠️  No window resize data available")
            return
        
        hwnd = self.hwnd_for_resize
        
        print(f"\n🔄 RESTORING WINDOW SIZE")
        
        aspect_ratio = self.original_window_height / self.original_window_width
        target_height = int(self.target_restore_width * aspect_ratio)
        
        current_window_width, current_window_height = self.get_window_outer_size(hwnd)
        
        if current_window_width == self.target_restore_width:
            print(f"✓ Window already at target width")
            self.log("Window already at target width", 'success')
        else:
            self.log(f"Restoring window to {self.target_restore_width}x{target_height}", 'system')
            
            window_rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
            
            success = user32.SetWindowPos(
                hwnd, 0,
                window_rect.left, window_rect.top,
                self.target_restore_width, target_height,
                0x0004
            )
            
            if success:
                time.sleep(0.3)
                print(f"✓ Window restored successfully!")
                self.log(f"Window restored", 'success')
            else:
                print(f"✗ Failed to restore window")
                self.log("Failed to restore window size", 'error')
    
    def check_initial_grid(self, hwnd):
        """Check all 9 grid positions using hybrid image detection"""
        global _rr_running
        
        print("\n" + "="*60)
        print("🔍 HYBRID GRID STATE CHECK")
        print("="*60)
        self.log("Checking initial grid state with hybrid detection...", 'system')
        
        self.ko_matches = []
        self.fail_matches = []
        self.froglet_matches = []
        self.available_matches = []
        
        print(f"\nDetection settings:")
        print(f"  • KO threshold: 0.75")
        print(f"  • Fail threshold: 0.85 (stricter)")
        print(f"  • Froglet threshold: 0.75\n")
        
        for key in ['11', '12', '13', '21', '22', '23', '31', '32', '33']:
            if not self.running or not _rr_running:
                print(f"[STOP] Stop detected during grid check")
                return False
            
            coord = self.grid_positions[key]['coord_1']
            x, y = coord
            print(f"\n📍 Position {key}: Checking around ({x:4d}, {y:4d})")
            
            is_ko, ko_conf = self.detect_template_near_coord(hwnd, x, y, 'ko', threshold=0.75)
            if is_ko:
                self.ko_matches.append(key)
                print(f"   ✓ KO - Match completed")
                self.log(f"Position {key}: KO (completed)", 'success')
                continue
            
            is_fail, fail_conf = self.detect_template_near_coord(hwnd, x, y, 'fail', threshold=0.85)
            if is_fail:
                self.fail_matches.append(key)
                print(f"   ✗ FAIL - Match attempted but failed")
                self.log(f"Position {key}: FAIL (attempted)", 'error')
                continue
            
            is_froglet, froglet_conf = self.detect_template_near_coord(hwnd, x, y, 'froglet', threshold=0.75)
            if is_froglet:
                self.froglet_matches.append(key)
                self.available_matches.append(key)
                print(f"   🐸 FROGLET - Available (needs extra clicks)")
                self.log(f"Position {key}: FROGLET (needs extra clicks)", 'system')
                continue
            
            self.available_matches.append(key)
            print(f"   ✓ AVAILABLE - Normal active match")
            self.log(f"Position {key}: AVAILABLE (normal)", 'success')
        
        total_ko = len(self.ko_matches)
        total_fail = len(self.fail_matches)
        total_froglet = len(self.froglet_matches)
        total_normal_available = len(self.available_matches) - total_froglet
        total_available = len(self.available_matches)
        total_cleared = total_ko + total_fail
        run_position = total_cleared + 1
        
        print("\n" + "-"*60)
        print(f"GRID SUMMARY:")
        print(f"  • KO:        {total_ko} - {self.ko_matches if self.ko_matches else 'None'}")
        print(f"  • Fail:      {total_fail} - {self.fail_matches if self.fail_matches else 'None'}")
        print(f"  • Froglet:   {total_froglet} - {self.froglet_matches if self.froglet_matches else 'None'}")
        print(f"  • Available: {total_available} - {self.available_matches if self.available_matches else 'None'}")
        print(f"    └─ Normal: {total_normal_available}, Froglet: {total_froglet}")
        print(f"  • Run position: {run_position}/9")
        print("-"*60)
        
        self.log(f"Grid check complete:", 'system')
        self.log(f"  KO: {total_ko} - {self.ko_matches}", 'success')
        self.log(f"  Fail: {total_fail} - {self.fail_matches}", 'error')
        self.log(f"  Froglet: {total_froglet} - {self.froglet_matches}", 'system')
        self.log(f"  Available: {total_available} (Normal: {total_normal_available}, Froglet: {total_froglet})", 'system')
        
        return True
    
    def process_single_match(self, hwnd, position_key):
        """Process a single match from start to completion"""
        global _rr_running
        
        print(f"\n{'='*60}")
        print(f"🎮 PROCESSING MATCH: Position {position_key}")
        print(f"{'='*60}")
        self.log(f"Processing match at position {position_key}", 'control')
        
        coord_1 = self.grid_positions[position_key]['coord_1']
        coord_2 = self.grid_positions[position_key]['coord_2']
        
        is_froglet = position_key in self.froglet_matches
        
        print(f"\nCoordinates for position {position_key}:")
        print(f"  • Click coord: ({coord_1[0]:4d}, {coord_1[1]:4d})")
        print(f"  • Join button: ({coord_2[0]:4d}, {coord_2[1]:4d})")
        if is_froglet:
            print(f"  • 🐸 FROGLET MATCH - Will click continuously during match")
        
        # Step 1: Expand match
        print(f"\n🔹 STEP 1: Expanding match")
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                return False
            
            self.send_click(hwnd, coord_1[0], coord_1[1])
            
            if not self.interruptible_sleep(self.EXPANSION_WAIT):
                return False
            
            color = self.get_pixel_color(hwnd, coord_2[0], coord_2[1])
            
            if self.color_matches(color, self.color_btn):
                print(f"     ✓ Match expanded!")
                self.log(f"Match expanded successfully", 'success')
                break
            else:
                if attempt == self.max_retries - 1:
                    self.log("Failed to expand match", 'error')
                    return False
        
        # Step 2: Join match
        print(f"\n🔹 STEP 2: Joining match")
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                return False
            
            self.send_click(hwnd, coord_2[0], coord_2[1])
            
            if not self.interruptible_sleep(self.JOIN_WAIT):
                return False
            
            color = self.get_pixel_color(hwnd, coord_2[0], coord_2[1])
            
            if self.color_matches(color, self.color_btn):
                if attempt == self.max_retries - 1:
                    print(f"     ✗ ENTRY COUNT EXHAUSTED")
                    
                    # Click coord_1 to collapse expanded window before stopping
                    print(f"\n🔹 Collapsing expanded match before stopping")
                    self.log("Collapsing expanded match window", 'system')
                    self.send_click(hwnd, coord_1[0], coord_1[1])
                    time.sleep(0.5)  # Brief wait for collapse animation
                    
                    self.log("Entry count exhausted - stopping automation", 'error')
                    return "ENTRY_EXHAUSTED"
            else:
                print(f"     ✓ Successfully joined match")
                self.log("Successfully joined match", 'success')
                break
        
        # Step 2.5: Wait for loading screen to finish (for froglet matches)
        if is_froglet:
            print(f"\n🔹 STEP 2.5: Froglet Match - Waiting for loading screen")
            self.log(f"Froglet match detected - waiting 3s for loading screen", 'system')
            
            if not self.interruptible_sleep(3.0):
                return False
            
            print(f"     ✓ Loading screen buffer complete")
        
        # Step 3: Wait for match completion (with continuous froglet clicks if needed)
        print(f"\n🔹 STEP 3: Waiting for match to complete")
        if is_froglet:
            print(f"   🐸 Froglet mode: Will click continuously every {self.FROGLET_CLICK_DELAY}s")
        
        start_time = time.time()
        match_ended = False
        check_count = 0
        froglet_click_count = 0
        
        froglet_x, froglet_y = self.coord_froglet_click if is_froglet else (None, None)
        
        while time.time() - start_time < self.match_timeout:
            if not self.running or not _rr_running:
                return False
            
            # For froglet matches, click continuously
            if is_froglet:
                froglet_click_count += 1
                print(f"   🐸 Froglet click #{froglet_click_count}")
                self.send_click(hwnd, froglet_x, froglet_y)
                
                # Use shorter sleep interval for froglet (FROGLET_CLICK_DELAY)
                if not self.interruptible_sleep(self.FROGLET_CLICK_DELAY):
                    return False
            else:
                # Normal matches use longer check interval
                if not self.interruptible_sleep(self.MATCH_CHECK_INTERVAL):
                    return False
            
            check_count += 1
            elapsed = int(time.time() - start_time)
            
            # Check for match end every check
            color = self.get_pixel_color(hwnd, self.coord_check_end[0], self.coord_check_end[1])
            
            if self.color_matches(color, self.color_fail) or self.color_matches(color, self.color_success):
                result = "fail" if self.color_matches(color, self.color_fail) else "success"
                print(f"     {'✗' if result == 'fail' else '✓'} Match {result.upper()} (after {elapsed}s)")
                if is_froglet:
                    print(f"     Total froglet clicks: {froglet_click_count}")
                    self.log(f"Froglet match completed after {froglet_click_count} clicks", 'success')
                self.log(f"Match ended: {result}", 'error' if result == 'fail' else 'success')
                self.send_click(hwnd, self.coord_click_end[0], self.coord_click_end[1])
                match_ended = True
                self.total_complete += 1
                break
        
        if not match_ended:
            print(f"     ✗ TIMEOUT - No end signal detected after {self.match_timeout}s")
            if is_froglet:
                print(f"     Total froglet clicks attempted: {froglet_click_count}")
            self.log("Match timeout reached - no end signal detected", 'error')
            return False
        
        # Step 4: Return to lobby
        if not self.wait_for_lobby_return(hwnd):
            return False
        
        print(f"{'='*60}\n")
        return True


    def run(self):
        """Main automation loop"""
        global _rr_running
        
        self.running = True
        _rr_running = True
        
        print("\n" + "="*60)
        print("[START] Realm Raid Automation Starting")
        print("="*60)
        self.log("Starting Realm Raid automation", 'system')
        
        hwnd = self.target_hwnd
        self.log(f"Using target HWND: {hwnd}", 'system')
        
        # Verify the window still exists
        import win32gui
        try:
            if not win32gui.IsWindow(hwnd):
                self.log("Target window no longer exists!", 'error')
                self.running = False
                _rr_running = False
                return
        except:
            self.log("Cannot access target window", 'error')
            self.running = False
            _rr_running = False
            return
        
        if not self.resize_window_to_reference(hwnd):
            self.log("Window resize failed", 'error')
            self.running = False
            _rr_running = False
            return
        
        try:
            while self.running and _rr_running:
                if not self.running or not _rr_running:
                    break
                
                self.log("Starting new page scan...", 'system')
                if not self.check_initial_grid(hwnd):
                    break
                
                self.log(f"Found {len(self.available_matches)} available matches", 'system')
                
                if not self.available_matches:
                    if self.fail_matches:
                        if not self.refresh_page_if_needed(hwnd):
                            break
                        
                        if not self.interruptible_sleep(self.PAGE_CYCLE_WAIT):
                            break
                        
                        if not self.check_initial_grid(hwnd):
                            break
                        
                        if not self.available_matches:
                            self.log("All matches completed", 'success')
                            break
                    else:
                        self.log("All matches completed", 'success')
                        break
                
                for idx, position in enumerate(self.available_matches[:], 1):
                    if not self.running or not _rr_running:
                        break
                    
                    self.log(f"Match {idx}/{len(self.available_matches)}: Position {position}", 'control')
                    
                    result = self.process_single_match(hwnd, position)
                    
                    if result == "ENTRY_EXHAUSTED":
                        # Stop flag already set in process_single_match
                        # Just restore window and exit cleanly
                        self.running = False
                        _rr_running = False
                        break  # Exit the for loop
                    elif not result:
                        self.log(f"Failed to process {position}", 'error')
                        continue
                
                # Check if we broke out due to entry exhaustion
                if not self.running or not _rr_running:
                    break
                
                if self.running and _rr_running:
                    if self.fail_matches:
                        if not self.refresh_page_if_needed(hwnd):
                            break
                
                self.ko_matches = []
                self.fail_matches = []
                self.froglet_matches = []
                self.available_matches = []
                
                if self.running and _rr_running:
                    if not self.interruptible_sleep(self.PAGE_CYCLE_WAIT):
                        break
                
        except Exception as e:
            self.log(f"Error in automation: {e}", 'error')
            import traceback
            traceback.print_exc()
        finally:
            # Only restore window once
            self.restore_window_size()
            
            self.running = False
            _rr_running = False
            
            # Single final log message
            print("\n" + "="*60)
            print(f"[END] Realm Raid automation stopped - Total matches: {self.total_complete}")
            print("="*60)
            self.log(f"Realm Raid automation stopped - Total matches: {self.total_complete}", 'system')
    
    def send_click(self, hwnd, x, y):
        """Send non-intrusive click to window"""
        try:
            lparam = win32api.MAKELONG(x, y)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(self.CLICK_DELAY)
            win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            return True
        except Exception as e:
            self.log(f"Error sending click: {e}", 'error')
            return False
    
    def log_color_mismatch(self, location, expected_color, actual_color, expected_name="expected"):
        """Log detailed color mismatch"""
        self.log(
            f"Color mismatch at {location}: "
            f"{expected_name}={self.rgb_to_hex(expected_color)}, "
            f"found={self.rgb_to_hex(actual_color)}", 
            'error'
        )
    
    def wait_for_lobby_return(self, hwnd):
        """Wait for return to lobby"""
        global _rr_running
        
        print(f"\n🔹 Returning to lobby...")
        self.log("Waiting for return to lobby", 'system')
        
        max_attempts = 10
        for attempt in range(max_attempts):
            if not self.running or not _rr_running:
                return False
            
            color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
            
            if self.color_matches(color, self.color_btn) or self.color_matches(color, self.color_cd):
                self.log("Successfully returned to lobby", 'success')
                return True
            else:
                self.send_click(hwnd, self.coord_click_end[0], self.coord_click_end[1])
                
                if not self.interruptible_sleep(self.REFRESH_BUTTON_CHECK_INTERVAL):
                    return False
        
        self.log("Failed to return to lobby", 'error')
        return False
    
    def refresh_page_if_needed(self, hwnd):
        """Check if refresh needed based on Fail matches"""
        global _rr_running
        
        if not self.fail_matches:
            self.log("No Fail matches - skipping refresh check", 'system')
            return True
        
        self.log(f"Fail matches detected: {self.fail_matches}", 'system')
        
        color = self.get_pixel_color(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
        
        if self.color_matches(color, self.color_btn):
            self.log("Clicking refresh button", 'control')
            self.send_click(hwnd, self.coord_click_refresh[0], self.coord_click_refresh[1])
            
            if not self.interruptible_sleep(self.REFRESH_CLICK_WAIT):
                return False
            
            return self.handle_confirm_button(hwnd)
            
        elif self.color_matches(color, self.color_cd):
            self.log("Refresh on cooldown - waiting", 'system')
            return self.wait_for_confirm_cooldown(hwnd)
        else:
            self.log("Page may have auto-refreshed", 'system')
            return True
    
    def handle_confirm_button(self, hwnd):
        """Click confirm button with retry"""
        global _rr_running
        
        for attempt in range(self.max_retries):
            if not self.running or not _rr_running:
                return False
            
            color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
            
            if self.color_matches(color, self.color_btn):
                self.send_click(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.interruptible_sleep(self.CONFIRM_CLICK_WAIT):
                    return False
                
                verify_color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.color_matches(verify_color, self.color_btn):
                    self.log("Page refreshed successfully", 'success')
                    return True
                    
            elif self.color_matches(color, self.color_cd):
                return self.wait_for_confirm_cooldown(hwnd)
        
        return True
    
    def wait_for_confirm_cooldown(self, hwnd):
        """Wait for confirm button cooldown"""
        global _rr_running
        
        self.log("Waiting for confirm cooldown...", 'system')
        
        while self.running and _rr_running:
            color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
            
            if self.color_matches(color, self.color_btn):
                self.send_click(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.interruptible_sleep(self.CONFIRM_CLICK_WAIT):
                    return False
                
                verify_color = self.get_pixel_color(hwnd, self.coord_click_confirm[0], self.coord_click_confirm[1])
                
                if not self.color_matches(verify_color, self.color_btn):
                    self.log("Page refreshed successfully", 'success')
                    return True
                    
                if not self.interruptible_sleep(self.CONFIRM_COOLDOWN_CHECK_INTERVAL):
                    return False
            else:
                if not self.interruptible_sleep(self.CONFIRM_COOLDOWN_CHECK_INTERVAL):
                    return False
        
        return False
    
def run_rr_mode(log_func, config_path, coords_path, target_hwnd):
    """Start Realm Raid mode with the specified target window
    
    Args:
        log_func: Logging function
        config_path: Path to config.ini
        coords_path: Path to coords.ini
        target_hwnd: The HWND of the window to automate (integer)
    """
    global _rr_running, _rr_thread, _rr_automation_instance
    
    if _rr_running:
        log_func("Realm Raid already running", 'error')
        return
    
    _rr_running = True
    _rr_automation_instance = RealmRaidAutomation(
        log_func, 
        config_path, 
        coords_path, 
        target_hwnd  # Pass the specific HWND, not a list!
    )
    
    def thread_target():
        global _rr_running
        _rr_automation_instance.run()
        _rr_running = False
    
    _rr_thread = threading.Thread(target=thread_target, daemon=True)
    _rr_thread.start()
    
    log_func(f"Realm Raid mode started on HWND: {target_hwnd}", 'system')


def stop_rr_mode():
    """Stop Realm Raid mode"""
    global _rr_running, _rr_automation_instance
    
    if _rr_running and _rr_automation_instance:
        _rr_automation_instance.running = False
        _rr_running = False
        return True
    
    return False