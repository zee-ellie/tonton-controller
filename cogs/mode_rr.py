import configparser
import time
import threading
import win32gui
import win32con
import win32api
import pyautogui
from cogs.coord_finder import CoordinateFinder

# Global control flag
_running = False
_thread = None

def parse_coords(coord_str):
    """Parse coordinate string 'x, y' into tuple (x, y)"""
    try:
        x, y = coord_str.split(',')
        return int(x.strip()), int(y.strip())
    except Exception:
        return None

def parse_color(color_str):
    """Parse color string '#RRGGBB' and normalize"""
    return color_str.strip().upper()

def click_window_coords(hwnd, x, y, log_func=None):
    """Send a non-intrusive click to window at relative coordinates using Windows messages
    
    Args:
        hwnd: Window handle
        x, y: Window-relative coordinates (client area)
        log_func: Optional logging function
    """
    try:
        # Pack coordinates into lParam
        lParam = win32api.MAKELONG(x, y)
        
        # Send mouse down message
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        
        # Send mouse up message
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        
        if log_func:
            log_func(f"Clicked HWND {hwnd} at relative ({x}, {y})", "system")
            
    except Exception as e:
        if log_func:
            log_func(f"Click error on HWND {hwnd}: {e}", "error")

def get_pixel_color_at_window(hwnd, rel_x, rel_y):
    """Get pixel color at window-relative coordinates
    
    Returns:
        str: Hex color string '#RRGGBB' or None on error
    """
    try:
        screen_x, screen_y = win32gui.ClientToScreen(hwnd, (rel_x, rel_y))
        color = pyautogui.pixel(screen_x, screen_y)
        return '#{:02X}{:02X}{:02X}'.format(*color)
    except Exception:
        return None

def check_color_match(color1, color2, tolerance=5):
    """Check if two hex colors match within tolerance
    
    Args:
        color1, color2: Hex color strings '#RRGGBB'
        tolerance: Allowed difference per RGB channel
        
    Returns:
        bool: True if colors match within tolerance
    """
    if not color1 or not color2:
        return False
    
    try:
        # Remove '#' and convert to RGB
        r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
        r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
        
        # Check each channel within tolerance
        return (abs(r1 - r2) <= tolerance and 
                abs(g1 - g2) <= tolerance and 
                abs(b1 - b2) <= tolerance)
    except Exception:
        return False

def check_slot_status(hwnd, coord_1, colors, log_func, set_name=""):
    """Check slot status at coordinate
    
    Returns:
        str: '1_color', 'err_color', or 'completed'
    """
    x1, y1 = coord_1
    current_color = get_pixel_color_at_window(hwnd, x1, y1)
    
    if check_color_match(current_color, colors['1_color']):
        return '1_color'
    elif check_color_match(current_color, colors['err_color']):
        return 'err_color'
    else:
        return 'completed'

def process_single_set(hwnd, set_name, coord_1, coord_2, colors, check_end_coord, click_end_coord, log_func, match_timeout, coords_config, click_refresh_coord):
    """Process a single match set
    
    Returns:
        str: 'played_success', 'played_fail', 'previous_fail', 'already_complete', 'no_tickets', or 'error'
    """
    if not _running:
        return 'error'
    
    try:
        x1, y1 = coord_1
        x2, y2 = coord_2
        
        # Step 1 & 2: Check slot status
        log_func(f"HWND {hwnd} - {set_name}: Checking slot status at ({x1}, {y1})", "system")
        slot_status = check_slot_status(hwnd, coord_1, colors, log_func, set_name)
        
        if slot_status == 'err_color':
            # Previous failed run
            log_func(f"HWND {hwnd} - {set_name}: err_color detected - previous failed run, fail +1", "error")
            time.sleep(0.5)  # Buffer before moving to next set
            return 'previous_fail'
        elif slot_status == 'completed':
            # Already completed successfully
            log_func(f"HWND {hwnd} - {set_name}: Already completed - success +1, skipping", "system")
            time.sleep(0.5)  # Buffer before moving to next set
            return 'already_complete'
        elif slot_status != '1_color':
            # Unexpected state
            log_func(f"HWND {hwnd} - {set_name}: Unexpected slot state, skipping", "error")
            time.sleep(0.5)  # Buffer before moving to next set
            return 'error'
        
        # Step 3: 1_color matched, expand window
        log_func(f"HWND {hwnd} - {set_name}: 1_color matched - available run, expanding window", "control")
        click_window_coords(hwnd, x1, y1, log_func)
        time.sleep(1.5)  # Wait for expansion animation (increased from 1.5s)
        
        if not _running:
            return 'error'
        
        # Check for btn_color at _2 coordinate
        expanded = False
        max_expand_attempts = 3
        
        for attempt in range(max_expand_attempts):
            if not _running:
                return 'error'
            
            btn_color_check = get_pixel_color_at_window(hwnd, x2, y2)
            
            if check_color_match(btn_color_check, colors['btn_color']):
                log_func(f"HWND {hwnd} - {set_name}: Window expanded (btn_color detected at button position)", "success")
                expanded = True
                break
            else:
                log_func(f"HWND {hwnd} - {set_name}: Window not expanded, retry {attempt + 1}/{max_expand_attempts}", "system")
                click_window_coords(hwnd, x1, y1, log_func)
                time.sleep(1.5)  # Wait for animation before next check (increased from 1.5s)
        
        if not expanded:
            log_func(f"HWND {hwnd} - {set_name}: Failed to expand window after {max_expand_attempts} attempts", "error")
            return 'error'
        
        if not _running:
            return 'error'
        
        # Step 4: Click button to start match with ticket verification
        time.sleep(0.5)  # Buffer before clicking start button
        log_func(f"HWND {hwnd} - {set_name}: Starting match at ({x2}, {y2})", "control")
        
        # Try to start match, verify button disappears (has tickets)
        max_ticket_attempts = 3
        match_started = False
        
        for ticket_attempt in range(max_ticket_attempts):
            if not _running:
                return 'error'
            
            click_window_coords(hwnd, x2, y2, log_func)
            time.sleep(2.0)  # Wait for match to start loading
            
            # Check if button still exists (means insufficient tickets)
            btn_check = get_pixel_color_at_window(hwnd, x2, y2)
            
            if check_color_match(btn_check, colors['btn_color']):
                # Button still visible - insufficient tickets or didn't register
                log_func(f"HWND {hwnd} - {set_name}: Button still visible after click [Attempt {ticket_attempt + 1}/{max_ticket_attempts}]", "system")
                
                if ticket_attempt == max_ticket_attempts - 1:
                    # Last attempt failed - out of tickets
                    log_func(f"HWND {hwnd} - {set_name}: Out of tickets - button persists after {max_ticket_attempts} attempts", "error")
                    return 'no_tickets'
                
                time.sleep(1.0)  # Brief wait before retry
            else:
                # Button disappeared - match started successfully
                log_func(f"HWND {hwnd} - {set_name}: Match started successfully (button disappeared)", "success")
                match_started = True
                break
        
        if not match_started:
            log_func(f"HWND {hwnd} - {set_name}: Failed to start match", "error")
            return 'no_tickets'
        
        if not _running:
            return 'error'
        
        # Wait for match to end
        log_func(f"HWND {hwnd} - {set_name}: Waiting for match to end (match timeout: {match_timeout}s)", "system")
        check_x, check_y = check_end_coord
        
        start_time = time.time()
        match_ended = False
        
        while _running and (time.time() - start_time) < match_timeout:
            end_color = get_pixel_color_at_window(hwnd, check_x, check_y)
            
            if check_color_match(end_color, colors['fail_color']) or check_color_match(end_color, colors['success_color']):
                match_ended = True
                log_func(f"HWND {hwnd} - {set_name}: Match ended (end screen detected)", "success")
                break
            
            time.sleep(1.0)  # Check every 1 second
        
        if not match_ended:
            log_func(f"HWND {hwnd} - {set_name}: Match timeout reached", "error")
            return 'error'
        
        if not _running:
            return 'error'
        
        # Step 5: Click click_end to exit, then verify we're back in lobby
        time.sleep(0.5)  # Buffer before clicking exit
        end_x, end_y = click_end_coord
        
        log_func(f"HWND {hwnd} - {set_name}: Match complete, clicking exit at ({end_x}, {end_y})", "control")
        click_window_coords(hwnd, end_x, end_y, log_func)
        
        # Wait and check if we're back in lobby by checking refresh button
        time.sleep(2.0)  # Wait for screen transition
        
        refresh_x, refresh_y = click_refresh_coord
        
        # Check refresh button for btn_color or cd_color
        max_exit_attempts = 5
        in_lobby = False
        
        for exit_attempt in range(max_exit_attempts):
            if not _running:
                return 'error'
            
            refresh_color = get_pixel_color_at_window(hwnd, refresh_x, refresh_y)
            
            # Check if we're in lobby (refresh button visible with btn_color or cd_color)
            if check_color_match(refresh_color, colors['btn_color']) or check_color_match(refresh_color, colors.get('cd_color', '#FFFFFF')):
                log_func(f"HWND {hwnd} - {set_name}: Back in lobby (refresh button detected)", "success")
                in_lobby = True
                break
            else:
                # Still in end screen or reward overlay, click exit again
                log_func(f"HWND {hwnd} - {set_name}: Still in end/reward screen, clicking exit again [Attempt {exit_attempt + 1}/{max_exit_attempts}]", "system")
                click_window_coords(hwnd, end_x, end_y, log_func)
                time.sleep(1.0)  # Wait before next check
        
        if not in_lobby:
            log_func(f"HWND {hwnd} - {set_name}: Failed to return to lobby after {max_exit_attempts} attempts", "error")
            return 'error'
        
        if not _running:
            return 'error'
        
        # Step 6: Check outcome by re-checking the slot status
        time.sleep(1.0)  # Brief wait before checking outcome
        log_func(f"HWND {hwnd} - {set_name}: Checking match outcome", "system")
        
        final_status = check_slot_status(hwnd, coord_1, colors, log_func, set_name)
        
        if final_status == 'err_color':
            # Match was lost
            log_func(f"HWND {hwnd} - {set_name}: Match outcome: FAILED (err_color detected)", "error")
            time.sleep(0.5)  # Buffer before next set
            return 'played_fail'
        elif final_status == 'completed':
            # Match was won
            log_func(f"HWND {hwnd} - {set_name}: Match outcome: SUCCESS (completed state detected)", "success")
            time.sleep(0.5)  # Buffer before next set
            return 'played_success'
        elif final_status == '1_color':
            # Should never happen - unexpected state
            log_func(f"HWND {hwnd} - {set_name}: Unexpected 1_color after match completion", "error")
            time.sleep(0.5)  # Buffer before next set
            return 'error'
        else:
            log_func(f"HWND {hwnd} - {set_name}: Unknown outcome state", "error")
            time.sleep(0.5)  # Buffer before next set
            return 'error'
        
    except Exception as e:
        log_func(f"HWND {hwnd} - {set_name}: Error processing set: {e}", "error")
        return 'error'

def realm_raid_loop(log_func, config_path, coords_path, hwnd_list):
    """Main realm raid automation loop"""
    global _running
    
    try:
        # Load coordinates and settings
        coords_config = configparser.ConfigParser()
        coords_config.read(coords_path)
        
        # Load config for reference dimensions
        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        
        # Get reference dimensions for scaling
        reference_width = cfg.getint("REFERENCE", "width", fallback=1152)
        reference_height = cfg.getint("REFERENCE", "height", fallback=679)
        
        log_func(f"Reference dimensions: {reference_width}x{reference_height}", "system")
        
        # Parse colors
        colors = {
            '1_color': parse_color(coords_config.get('REALM RAID', '1_color')),
            'btn_color': parse_color(coords_config.get('REALM RAID', 'btn_color')),
            'err_color': parse_color(coords_config.get('REALM RAID', 'err_color')),
            'fail_color': parse_color(coords_config.get('REALM RAID', 'fail_color')),
            'success_color': parse_color(coords_config.get('REALM RAID', 'success_color')),
            'cd_color': parse_color(coords_config.get('REALM RAID', 'cd_color', fallback='#808080'))
        }
        
        match_timeout = coords_config.getint('REALM RAID', 'match_timeout', fallback=120)
        
        # Parse all match coordinates (base coordinates)
        match_sets = []
        for row in [1, 2, 3]:
            for col in [1, 2, 3]:
                key_1 = f'click_{row}{col}_1'
                key_2 = f'click_{row}{col}_2'
                
                coords_1 = parse_coords(coords_config.get('REALM RAID', key_1))
                coords_2 = parse_coords(coords_config.get('REALM RAID', key_2))
                
                if coords_1 and coords_2:
                    match_sets.append({
                        'name': f'Set {row}{col}',
                        'coords_1': coords_1,
                        'coords_2': coords_2
                    })
        
        # Parse end screen coordinates (base coordinates)
        check_end = parse_coords(coords_config.get('REALM RAID', 'check_end'))
        click_end = parse_coords(coords_config.get('REALM RAID', 'click_end'))
        click_refresh = parse_coords(coords_config.get('REALM RAID', 'click_refresh'))
        
        log_func(f"Loaded {len(match_sets)} match sets (9 sets = 1 round)", "system")
        log_func(f"Processing {len(hwnd_list)} windows", "system")
        
        # Single round mode - process each window once through all 9 sets
        log_func(f"=== Starting Realm Raid Round (9 sets per window) ===", "control")
        
        # Track how many windows ran out of tickets
        windows_out_of_tickets = 0
        total_windows = len(hwnd_list)
        
        # Process each window
        for window in hwnd_list:
            if not _running:
                break
            
            hwnd = window._hWnd
            
            # Calculate scaling for this specific window
            actual_width = window.width
            actual_height = window.height
            
            scale_x = actual_width / reference_width
            scale_y = actual_height / reference_height
            
            log_func(f"Processing HWND {hwnd} - Size: {actual_width}x{actual_height}, Scale: {scale_x:.2f}x{scale_y:.2f}", "system")
            
            # Scale all coordinates for this window
            scaled_sets = []
            for match_set in match_sets:
                base_x1, base_y1 = match_set['coords_1']
                base_x2, base_y2 = match_set['coords_2']
                
                scaled_sets.append({
                    'name': match_set['name'],
                    'coords_1': (int(base_x1 * scale_x), int(base_y1 * scale_y)),
                    'coords_2': (int(base_x2 * scale_x), int(base_y2 * scale_y))
                })
            
            scaled_check_end = (int(check_end[0] * scale_x), int(check_end[1] * scale_y))
            scaled_click_end = (int(click_end[0] * scale_x), int(click_end[1] * scale_y))
            scaled_click_refresh = (int(click_refresh[0] * scale_x), int(click_refresh[1] * scale_y))
            
            # Track statistics for this round
            fail_count = 0
            success_count = 0
            error_count = 0
            
            # Process all 9 sets in order
            for set_idx, match_set in enumerate(scaled_sets):
                if not _running:
                    break
                
                # Check if we should stop due to fail count
                if fail_count >= 3:
                    log_func(f"HWND {hwnd}: Fail count reached 3, stopping this window's round", "error")
                    break
                
                log_func(f"HWND {hwnd}: Processing {match_set['name']} ({set_idx + 1}/{len(scaled_sets)})", "control")
                
                result = process_single_set(
                    hwnd,
                    match_set['name'],
                    match_set['coords_1'],
                    match_set['coords_2'],
                    colors,
                    scaled_check_end,
                    scaled_click_end,
                    log_func,
                    match_timeout,
                    coords_config,
                    scaled_click_refresh
                )
                
                # Update counters based on result
                if result == 'played_success':
                    # Won the match
                    success_count += 1
                elif result == 'played_fail':
                    # Lost the match
                    fail_count += 1
                    log_func(f"HWND {hwnd}: Fail count: {fail_count}/3", "error")
                elif result == 'previous_fail':
                    # Previous failed run (err_color before match)
                    fail_count += 1
                    log_func(f"HWND {hwnd}: Fail count: {fail_count}/3", "error")
                elif result == 'already_complete':
                    # Already completed (counted as success)
                    success_count += 1
                elif result == 'no_tickets':
                    # Out of tickets - stop THIS window only
                    log_func(f"HWND {hwnd}: OUT OF TICKETS - Stopping this window (other windows will continue)", "error")
                    break  # Exit loop for this window, continue to next window
                elif result == 'error':
                    # Technical error
                    error_count += 1
                
                # Small delay between sets
                time.sleep(1.0)  # Increased buffer between sets (was 0.5s)
            
            # Log round statistics for this window
            log_func(
                f"HWND {hwnd} - Round complete: "
                f"Success={success_count}, Fail={fail_count}, Error={error_count}",
                "success"
            )
        
        log_func(f"=== Realm Raid Round completed for all windows ===", "success")
        _running = False  # Auto-stop after completing one round
        log_func("Realm Raid mode stopped", "control")
        
    except Exception as e:
        log_func(f"Fatal error in Realm Raid loop: {e}", "error")
        _running = False

def run_rr_mode(log_func, config_path, coords_path, hwnd_list):
    """Start Realm Raid mode in a separate thread"""
    global _running, _thread
    
    if _running:
        log_func("Realm Raid mode already running", "error")
        return
    
    _running = True
    _thread = threading.Thread(
        target=realm_raid_loop,
        args=(log_func, config_path, coords_path, hwnd_list),
        daemon=True
    )
    _thread.start()
    log_func("Realm Raid mode started", "success")

def stop_rr_mode():
    """Stop Realm Raid mode"""
    global _running
    _running = False
    if _thread:
        _thread.join(timeout=2.0)