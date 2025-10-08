# main.py
import os
import sys
import tkinter as tk
from gui.gui import ClientControlGUI

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # For .exe
    return os.path.dirname(os.path.abspath(__file__))  # For .py

BASE_DIR = get_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
COORDS_PATH = os.path.join(BASE_DIR, "cogs", "coords.ini")

def main():
    root = tk.Tk()
    app = ClientControlGUI(root, CONFIG_PATH, COORDS_PATH)  # pass the paths!
    root.mainloop()

if __name__ == "__main__":
    main()
