import configparser
import os

class WindowSettingsManager:
    def __init__(self, config_path):
        self.CONFIG_PATH = config_path
        self.MIN_WIDTH = 700
    
    def get_max_width_from_config(self):
        """Get maximum width from config.ini [REFERENCE] section"""
        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            return config.getint('REFERENCE', 'width', fallback=2000)
        except Exception:
            return 2000  # Default fallback
    
    def get_default_width(self):
        """Get default width from [REFERENCE] section"""
        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            return config.getint('REFERENCE', 'width', fallback=1152)
        except Exception:
            return 1152  # Default fallback
    
    def get_current_width(self):
        """Get current width from [GLOBAL] section"""
        try:
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            return config.getint('GLOBAL', 'width', fallback=self.get_default_width())
        except Exception:
            return self.get_default_width()
    
    def validate_width_input(self, value):
        """Validate that width input is a number between MIN_WIDTH and max_width"""
        if value == "":
            return True  # Allow empty field
        try:
            width = int(value)
            max_width = self.get_max_width_from_config()  # Remove the extra .window_settings_manager
            return self.MIN_WIDTH <= width <= max_width
        except ValueError:
            return False
    
    def set_window_width(self, width):
        """Set the window width in config.ini
        
        Args:
            width (int): Width value to set
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if not isinstance(width, int):
                return False, "Width must be an integer"
            
            max_width = self.get_max_width_from_config()
            
            if width < self.MIN_WIDTH or width > max_width:
                return False, f"Width must be between {self.MIN_WIDTH} and {max_width}"
            
            # Update config
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            
            if not config.has_section('GLOBAL'):
                config.add_section('GLOBAL')
                
            config.set('GLOBAL', 'width', str(width))
            
            with open(self.CONFIG_PATH, 'w') as configfile:
                config.write(configfile)
                
            return True, f"Window width set to {width}"
            
        except Exception as e:
            return False, f"Error setting window width: {e}"
    
    def reset_window_width(self):
        """Reset window width to default from [REFERENCE] section
        
        Returns:
            tuple: (success: bool, message: str, default_width: int)
        """
        try:
            default_width = self.get_default_width()
            
            # Update config
            config = configparser.ConfigParser()
            config.read(self.CONFIG_PATH)
            
            if not config.has_section('GLOBAL'):
                config.add_section('GLOBAL')
                
            config.set('GLOBAL', 'width', str(default_width))
            
            with open(self.CONFIG_PATH, 'w') as configfile:
                config.write(configfile)
                
            return True, f"Window width reset to default: {default_width}", default_width
            
        except Exception as e:
            return False, f"Error resetting window width: {e}", None
    
    def get_window_settings(self):
        """Get all window settings for display
        
        Returns:
            dict: Current window settings
        """
        return {
            'current_width': self.get_current_width(),
            'default_width': self.get_default_width(),
            'max_width': self.get_max_width_from_config(),
            'min_width': self.MIN_WIDTH
        }