import configparser
import pygetwindow as gw
import time
import ctypes
from ctypes import wintypes

def resize_all_clients(log_action, config_path=None, *, action_label="Resizing client windows"):
    """Resize windows to target CLIENT width (not window width)
    
    Args:
        log_action: Logging callback function
        config_path: Path to config.ini (optional, defaults to 'config.ini')
        action_label: Label for the action in logs
    """
    log_action(action_label, 'control')

    try:
        # Use provided config_path or default to 'config.ini'
        if config_path is None:
            config_path = 'config.ini'
        
        # Load configuration
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')

        instance_name = config.get('GLOBAL', 'instance', fallback='Onmyoji')
        target_client_width = config.getint('GLOBAL', 'width', fallback=1136)

        if not instance_name:
            log_action("Error: No instance name configured in config.ini", 'error')
            return False

        # Use getWindowsWithTitle for PARTIAL matching (substring search)
        windows = gw.getWindowsWithTitle(instance_name)
        
        if not windows:
            log_action(f"No windows found with title containing: '{instance_name}'", 'error')
            log_action("Please make sure the game is running and not minimized", 'error')
            return False

        # Get reference aspect ratio
        ref_width = config.getint('REFERENCE', 'width', fallback=1136)
        ref_height = config.getint('REFERENCE', 'height', fallback=640)
        aspect_ratio = ref_height / ref_width
        
        target_client_height = int(target_client_width * aspect_ratio)
        
        log_action(
            f"Target CLIENT dimensions: {target_client_width}x{target_client_height}", 
            'system'
        )
        log_action(f"Found {len(windows)} window(s) matching: '{instance_name}'", 'system')

        resized_count = 0
        user32 = ctypes.windll.user32
        
        for window in windows:
            try:
                if window.isMinimized:
                    window.restore()
                    time.sleep(0.1)

                hwnd = window._hWnd
                
                # Get current CLIENT rect
                client_rect = wintypes.RECT()
                user32.GetClientRect(hwnd, ctypes.byref(client_rect))
                current_client_w = client_rect.right - client_rect.left
                current_client_h = client_rect.bottom - client_rect.top
                
                # Get current WINDOW rect
                window_rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(window_rect))
                current_window_w = window_rect.right - window_rect.left
                current_window_h = window_rect.bottom - window_rect.top
                
                # Calculate border sizes
                border_total_w = current_window_w - current_client_w
                border_total_h = current_window_h - current_client_h
                
                # Calculate required WINDOW size to achieve target CLIENT size
                target_window_w = target_client_width + border_total_w
                target_window_h = target_client_height + border_total_h
                
                log_action(
                    f"'{window.title[:30]}...': CLIENT {current_client_w}x{current_client_h} → "
                    f"{target_client_width}x{target_client_height}", 
                    'info'
                )
                
                # Resize using pygetwindow (sets WINDOW size)
                window.resizeTo(target_window_w, target_window_h)
                time.sleep(0.2)
                
                # Verify actual CLIENT size achieved
                user32.GetClientRect(hwnd, ctypes.byref(client_rect))
                actual_client_w = client_rect.right - client_rect.left
                actual_client_h = client_rect.bottom - client_rect.top
                
                resized_count += 1
                
                if actual_client_w == target_client_width and actual_client_h == target_client_height:
                    log_action(
                        f"✓ Window resized: CLIENT {actual_client_w}x{actual_client_h} (exact)", 
                        'success'
                    )
                else:
                    log_action(
                        f"⚠ Window resized: CLIENT {actual_client_w}x{actual_client_h} "
                        f"(off by {actual_client_w - target_client_width}x{actual_client_h - target_client_height})", 
                        'error'
                    )

            except Exception as e:
                log_action(f"Error resizing window '{window.title}': {str(e)}", 'error')
                continue

        if resized_count > 0:
            log_action(f"Successfully resized {resized_count} window(s)", 'success')
            return True
        else:
            log_action("No windows were resized", 'error')
            return False

    except Exception as e:
        log_action(f"Error during resize operation: {str(e)}", 'error')
        import traceback
        traceback.print_exc()
        return False