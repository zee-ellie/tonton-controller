import ctypes
import sys

class SleepManager:
    """Manages Windows sleep/screen saver prevention during automation"""
    
    # Windows API constants
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002
    ES_AWAYMODE_REQUIRED = 0x00000040
    
    def __init__(self):
        self.is_prevented = False
        self.original_state = None
        
    def prevent_sleep(self):
        """Prevent Windows from sleeping or turning off display
        
        Returns:
            bool: True if successfully prevented sleep, False otherwise
        """
        if self.is_prevented:
            print("[SleepManager] Sleep already prevented")
            return True
        
        try:
            if sys.platform == 'win32':
                # ES_CONTINUOUS: Informs the system that the state being set should remain in effect
                # ES_SYSTEM_REQUIRED: Forces the system to be in the working state
                # ES_DISPLAY_REQUIRED: Forces the display to be on
                # ES_AWAYMODE_REQUIRED: Enables away mode (for media playback)
                result = ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS | 
                    self.ES_SYSTEM_REQUIRED | 
                    self.ES_DISPLAY_REQUIRED |
                    self.ES_AWAYMODE_REQUIRED
                )
                
                if result:
                    self.is_prevented = True
                    print("[SleepManager] ✓ Sleep prevention enabled")
                    print("[SleepManager]   - System sleep: PREVENTED")
                    print("[SleepManager]   - Display sleep: PREVENTED")
                    print("[SleepManager]   - Away mode: ENABLED")
                    return True
                else:
                    print("[SleepManager] ✗ Failed to prevent sleep")
                    return False
            else:
                print("[SleepManager] Sleep prevention only supported on Windows")
                return False
                
        except Exception as e:
            print(f"[SleepManager] Error preventing sleep: {e}")
            return False
    
    def allow_sleep(self):
        """Allow Windows to sleep normally again
        
        Returns:
            bool: True if successfully restored, False otherwise
        """
        if not self.is_prevented:
            print("[SleepManager] Sleep already allowed")
            return True
        
        try:
            if sys.platform == 'win32':
                # Reset to default behavior by calling with ES_CONTINUOUS only
                result = ctypes.windll.kernel32.SetThreadExecutionState(
                    self.ES_CONTINUOUS
                )
                
                if result:
                    self.is_prevented = False
                    print("[SleepManager] ✓ Sleep prevention disabled")
                    print("[SleepManager]   - System sleep: ALLOWED")
                    print("[SleepManager]   - Display sleep: ALLOWED")
                    return True
                else:
                    print("[SleepManager] ✗ Failed to restore sleep settings")
                    return False
            else:
                return False
                
        except Exception as e:
            print(f"[SleepManager] Error restoring sleep: {e}")
            return False
    
    def get_status(self):
        """Get current sleep prevention status
        
        Returns:
            dict: Status information
        """
        return {
            'is_prevented': self.is_prevented,
            'system_sleep': 'PREVENTED' if self.is_prevented else 'ALLOWED',
            'display_sleep': 'PREVENTED' if self.is_prevented else 'ALLOWED'
        }
    
    def __del__(self):
        """Ensure sleep is restored when object is destroyed"""
        if self.is_prevented:
            print("[SleepManager] Cleanup: Restoring sleep settings")
            self.allow_sleep()