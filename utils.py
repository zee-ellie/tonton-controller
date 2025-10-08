import pyautogui
import configparser
import os


def get_pixel_color(x, y):
    """Get RGB color at (x, y) on screen."""
    try:
        r, g, b = pyautogui.pixel(int(x), int(y))
        return (r, g, b)
    except Exception:
        return (-1, -1, -1)  # Return invalid color on error


def load_coordinates(path):
    """
    Load all click_xxx_yyy coordinates from coords.ini.
    Returns a dict like {'click_11_1': (370, 140), ...}
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Coordinates file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    coords = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            if key.startswith("click_"):
                parts = [v.strip() for v in value.split(",")]
                if len(parts) == 2:
                    try:
                        coords[key] = (int(float(parts[0])), int(float(parts[1])))
                    except ValueError:
                        pass
    return coords


def load_colors(path):
    """
    Load all color values (#xxxxxx) from [REALM RAID] section of coords.ini.
    Returns a dict like {'1_color': 'DACDBD', 'refresh_color': 'F3B25E'}
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Coordinates file not found: {path}")

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    colors = {}
    if parser.has_section("REALM RAID"):
        for key, value in parser.items("REALM RAID"):
            if value.startswith("#"):
                colors[key] = value.lstrip("#").upper()
    return colors
