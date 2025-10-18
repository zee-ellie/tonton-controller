# main.py
import os
import sys
import tkinter as tk
from pathlib import Path
from gui.gui import ClientControlGUI

def get_application_path():
    """Get the directory where the application is running from"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent

def get_resource_path(relative_path):
    """Get absolute path to bundled resource"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    else:
        # Running as script
        base_path = Path(__file__).parent
    
    return base_path / relative_path

def initialize_config():
    """Initialize config.ini if it doesn't exist (editable by user)"""
    app_dir = get_application_path()
    config_file = app_dir / 'config.ini'
    
    # Complete default config with ALL required sections
    default_config = """[GLOBAL]
    instance = Onmyoji
    width = 1152
    party = True
    bounty = True
    mute = False

    [REFERENCE]
    width = 1152
    height = 679

    [REALM_RAID]
    target_hwnd = 0
    """
    
    # Create config.ini if it doesn't exist
    if not config_file.exists():
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(default_config)
            print(f"✓ Created default config.ini at {config_file}")
        except Exception as e:
            print(f"✗ ERROR creating config.ini: {e}")
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        print(f"✓ Using existing config.ini at {config_file}")
    
    return config_file

def verify_templates():
    """Verify that template images exist"""
    template_dir = get_resource_path('cogs/ref')
    
    required_templates = ['rr_ko.png', 'rr_fail.png', 'rr_froglet.png']
    
    if not template_dir.exists():
        print(f"⚠️  WARNING: Template directory not found at {template_dir}")
        print("Realm Raid mode will not work without template images.")
        return False
    
    missing = []
    for template in required_templates:
        template_path = template_dir / template
        if not template_path.exists():
            missing.append(template)
    
    if missing:
        print(f"⚠️  WARNING: Missing template images: {', '.join(missing)}")
        print(f"Template directory: {template_dir}")
        print("Realm Raid mode will not work without these images.")
        return False
    
    print(f"✓ All template images found at {template_dir}")
    return True

def main():
    try:
        # Get paths
        config_path = initialize_config()  # External, editable
        coords_path = get_resource_path('cogs/coords.ini')  # Bundled, read-only
        ref_path = get_resource_path('cogs/ref') # Template images
        
        # Verify coords.ini exists
        if not coords_path.exists():
            print(f"✗ ERROR: coords.ini not found at {coords_path}")
            print("Make sure coords.ini is in the cogs folder.")
            input("Press Enter to exit...")
            sys.exit(1)
        
        print(f"✓ Using coords.ini at {coords_path}")
        
        # Verify templates exist (NEW)
        verify_templates()
        
        # Initialize GUI
        root = tk.Tk()
        app = ClientControlGUI(root, str(config_path), str(coords_path))
        root.mainloop()
        
    except Exception as e:
        print(f"✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()