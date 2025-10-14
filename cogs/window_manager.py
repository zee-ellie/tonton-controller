import configparser
import pygetwindow as gw
import time

def resize_all_clients(log_action, *, action_label="Resizing client windows"):
    log_action(action_label, 'control')

    try:
        # Load configuration
        config = configparser.ConfigParser()
        config.read('config.ini')

        instance_name = config.get('GLOBAL', 'instance', fallback='Onmyoji')
        target_width = config.getint('GLOBAL', 'width', fallback=900)

        if not instance_name:
            log_action("Error: No instance name configured in config.ini", 'error')
            return False

        windows = gw.getWindowsWithTitle(instance_name)
        if not windows:
            log_action(f"No windows found with the title: {instance_name}", 'error')
            return False

        resized_count = 0
        for window in windows:
            try:
                if window.isMinimized:
                    window.restore()

                # Resize width only
                window.resizeTo(target_width, window.height)

                # Let the OS & client adjust
                time.sleep(0.1)  # 100ms delay

                # Read actual height after resize
                actual_height = window.height

                resized_count += 1
                log_action(
                    f"Resized '{window.title}' to {target_width}x{actual_height} "
                    "(height auto-adjusted)", 'info'
                )

            except Exception as e:
                log_action(f"Error resizing window '{window.title}': {str(e)}", 'error')
                continue

        log_action(f"Successfully resized {resized_count} window(s)", 'success')
        return resized_count > 0

    except Exception as e:
        log_action(f"Error during resize operation: {str(e)}", 'error')
        return False
