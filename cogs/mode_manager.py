import configparser

class ModeManager:
    def __init__(self, target_window_manager, config_path):
        self.target_window_manager = target_window_manager
        self.config_path = config_path
        self.current_mode = None
        self.mode_requirements = {
            'Solo': {'needs_target_window': False},
            'Team Host (2P)': {'needs_target_window': False},
            'Team Join': {'needs_target_window': False},
            'Realm Raid': {'needs_target_window': True},
            'Guild Realm Raid': {'needs_target_window': True},
            'Ultra Encounter': {'needs_target_window': False},
            'Encounter': {'needs_target_window': False}
        }
    
    def set_mode(self, mode_name):
        """Set the current mode and handle mode-specific setup
        
        Args:
            mode_name (str): Name of the mode to set
            
        Returns:
            dict: Mode information including requirements status
        """
        self.current_mode = mode_name
        
        requirements = self.get_mode_requirements(mode_name)
        
        if requirements.get('needs_target_window', False):
            has_target = self.target_window_manager.has_target_window()
            return {
                'needs_target_window': True,
                'has_target_window': has_target,
                'can_start': has_target
            }
        else:
            return {
                'needs_target_window': False,
                'has_target_window': False,
                'can_start': True
            }
    
    def get_mode_requirements(self, mode_name):
        """Get requirements for a specific mode
        
        Args:
            mode_name (str): Name of the mode
            
        Returns:
            dict: Requirements for the mode
        """
        return self.mode_requirements.get(mode_name, {'needs_target_window': False})
    
    def can_start_mode(self, mode_name):
        """Check if all requirements are met to start a mode
        
        Args:
            mode_name (str): Name of the mode to check
            
        Returns:
            bool: True if mode can be started, False otherwise
        """
        requirements = self.get_mode_requirements(mode_name)
        
        if requirements.get('needs_target_window', False):
            return self.target_window_manager.has_target_window()
        
        return True
    
    def get_current_mode(self):
        """Get the currently selected mode
        
        Returns:
            str: Current mode name or None if no mode set
        """
        return self.current_mode
    
    def get_mode_config(self, mode_name):
        """Get configuration specific to a mode
        
        Args:
            mode_name (str): Name of the mode
            
        Returns:
            dict: Mode-specific configuration
        """
        config = configparser.ConfigParser()
        config.read(self.config_path)
        
        mode_config = {}
        
        # Note: REALM_RAID section removed from config.ini
        # No need to store HWND - it's managed in memory by TargetWindowManager
        
        if mode_name == "Solo":
            # Solo mode specific configuration
            if config.has_section('SOLO'):
                mode_config.update(dict(config.items('SOLO')))
        
        # Add common configuration
        if config.has_section('GLOBAL'):
            mode_config.update(dict(config.items('GLOBAL')))
        
        return mode_config
    
    def validate_mode_setup(self, mode_name):
        """Validate all setup requirements for a mode
        
        Args:
            mode_name (str): Name of the mode to validate
            
        Returns:
            tuple: (bool, str) - (is_valid, message)
        """
        if not self.can_start_mode(mode_name):
            requirements = self.get_mode_requirements(mode_name)
            
            if requirements.get('needs_target_window', False):
                return False, f"{mode_name} requires a target window to be set"
            
            return False, f"Unable to start {mode_name}: requirements not met"
        
        # Additional validations for Realm Raid modes
        if mode_name in ["Realm Raid", "Guild Realm Raid"]:
            target_hwnd = self.target_window_manager.get_target_hwnd()
            if target_hwnd:
                # Verify the target window still exists
                window = self.target_window_manager.window_fetcher.get_window_by_hwnd(target_hwnd)
                if not window:
                    return False, "Target window no longer exists. Please refresh windows."
        
        return True, f"{mode_name} mode is ready to start"
    
    def get_supported_modes(self):
        """Get list of all supported modes
        
        Returns:
            list: List of mode names
        """
        return list(self.mode_requirements.keys())
    
    def is_multi_client_mode(self, mode_name):
        """Check if a mode requires multiple clients
        
        Args:
            mode_name (str): Name of the mode
            
        Returns:
            bool: True if mode requires multiple clients
        """
        multi_client_modes = ["Realm Raid", "Guild Realm Raid", "Team Host (2P)"]
        return mode_name in multi_client_modes
    
    def get_recommended_client_count(self, mode_name):
        """Get recommended number of clients for a mode
        
        Args:
            mode_name (str): Name of the mode
            
        Returns:
            int: Recommended number of clients
        """
        recommendations = {
            'Solo': 1,
            'Team Host (2P)': 2,
            'Team Join': 1,
            'Realm Raid': 3,
            'Guild Realm Raid': 3,
            'Ultra Encounter': 1,
            'Encounter': 1
        }
        return recommendations.get(mode_name, 1)