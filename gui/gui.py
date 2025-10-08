import sys
import os
import tkinter as tk
from tkinter import ttk
from ttkbootstrap import Style, dialogs
import pygetwindow as gw
import configparser
import pyautogui
import keyboard
import win32gui
import pygetwindow as gw
from cogs.window_manager import resize_all_clients
from cogs.mode_solo import run_solo_mode, stop_solo_mode
from cogs.mode_rr import run_rr_mode, stop_rr_mode
from cogs.coord_finder import CoordinateFinder

class ClientControlGUI:
    def __init__(self, root, config_path, coords_path):
        self.CONFIG_PATH = config_path
        self.COORDS_PATH = coords_path
        self.root = root
        self.style = Style(theme='cyborg')
        
        # Initialize coordinate finder
        self.coord_finder = CoordinateFinder(config_path)

        # Check for required window using ttkbootstrap dialogs
        config = configparser.ConfigParser()
        config.read(self.CONFIG_PATH)
        instance_name = config.get('GLOBAL', 'instance', fallback='')
        
        if not instance_name:
            dialogs.Messagebox.show_error(
                title="Config Error",
                message="'instance' not found in config.ini",
                parent=self.root
            )
            self.root.destroy()
            return
            
        windows = gw.getWindowsWithTitle(instance_name)
        if not windows:
            dialogs.Messagebox.show_error(
                title="Window Not Found",
                message=f"No window found with title: '{instance_name}'\nPlease launch the game first.",
                parent=self.root
            )
            self.root.destroy()
            return
            
        # Only proceed if window exists
        self.setup_gui()

    def setup_gui(self):
        self.root.title("吨吨鼠Controls")
        self.root.geometry("300x300")
        self.root.resizable(False, False)
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)
        
        # Create tabs
        self.create_control_tab()
        self.create_settings_tab()
        self.create_clients_tab()
        self.create_logs_tab()
        self.create_coord_tab()
        
        # Initialize client tracking
        self.tracked_clients = {}
        
        # Disable buttons by default
        self.start_btn['state'] = 'disabled'
        self.stop_btn['state'] = 'disabled'
        self.resize_btn['state'] = 'disabled'
        
        # Load settings (placeholder)
        self.load_settings()
        
    def create_control_tab(self):
        self.control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.control_tab, text="Control")
        
        mode_frame = ttk.LabelFrame(self.control_tab, text="Mode Selection", padding=10)
        mode_frame.pack(fill='x', padx=5, pady=5)
        
        self.mode_var = tk.StringVar()
        self.mode_combo = ttk.Combobox(
            mode_frame, 
            textvariable=self.mode_var,
            values=['Solo', 'Team Host (2P)', 'Team Join', "Realm Raid", "Guild Realm Raid", "Ultra Encounter", "Encounter"],
            state='readonly'
        )
        self.mode_combo.current(0)
        self.mode_combo.pack(fill='x')
        
        btn_frame = ttk.LabelFrame(self.control_tab, text="Controls", padding=10)
        btn_frame.pack(fill='x', padx=5, pady=5)
        
        self.set_size_btn = ttk.Button(btn_frame, text="Set Size", command=self.set_size, style='primary.TButton')
        self.start_btn = ttk.Button(btn_frame, text="Start", command=self.start_clicker, style='success.TButton')
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_clicker, style='danger.TButton')
        self.resize_btn = ttk.Button(btn_frame, text="Resize", command=self.resize_clients, style='info.TButton')
        
        self.set_size_btn.pack(side='left', expand=True, padx=2)
        self.start_btn.pack(side='left', expand=True, padx=2)
        self.stop_btn.pack(side='left', expand=True, padx=2)
        self.resize_btn.pack(side='left', expand=True, padx=2)
        
    def create_settings_tab(self):
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        
        settings_frame = ttk.LabelFrame(self.settings_tab, text="Configuration", padding=10)
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.party_default = tk.BooleanVar(value=True)
        self.accept_bounty = tk.BooleanVar(value=True)
        self.mute_clients = tk.BooleanVar()
        self.refresh_raid = tk.BooleanVar()
        
        ttk.Checkbutton(settings_frame, text="Party by default", variable=self.party_default).pack(anchor='w', pady=2)
        ttk.Checkbutton(settings_frame, text="Accept Bounty Invites", variable=self.accept_bounty).pack(anchor='w', pady=2)
        ttk.Checkbutton(settings_frame, text="Mute Clients", variable=self.mute_clients).pack(anchor='w', pady=2)
        ttk.Checkbutton(settings_frame, text="Refresh raid after 3 count", variable=self.refresh_raid).pack(anchor='w', pady=2)
        
        ttk.Button(settings_frame, text="Save Settings", command=self.save_settings, style='success.TButton').pack(pady=10)
        
    def create_clients_tab(self):
        self.clients_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.clients_tab, text="Clients")
        
        self.client_list_frame = ttk.LabelFrame(self.clients_tab, text="Active Clients", padding=10)
        self.client_list_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.tree = ttk.Treeview(self.client_list_frame, columns=('HWND', 'Position'), show='headings')
        self.tree.heading('HWND', text='HWND')
        self.tree.heading('Position', text='Position')
        self.tree.column('HWND', width=100)
        self.tree.column('Position', width=150)
        
        vsb = ttk.Scrollbar(self.client_list_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(fill='both', expand=True)
        
        ttk.Button(self.client_list_frame, text="Refresh List", command=self.refresh_client_list, style='info.TButton').pack(pady=5)
        
    def create_logs_tab(self):
        self.logs_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_tab, text="Logs")
        
        self.log_frame = ttk.LabelFrame(self.logs_tab, text="Action Log", padding=10)
        self.log_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(self.log_frame, wrap='word', state='disabled', height=10)
        self.log_text.tag_config('system', foreground='cyan')
        self.log_text.tag_config('control', foreground='yellow')
        self.log_text.tag_config('error', foreground='red')
        self.log_text.tag_config('success', foreground='green')
        
        vsb = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log_text.yview)
        vsb.pack(side='right', fill='y')
        self.log_text.configure(yscrollcommand=vsb.set)
        self.log_text.pack(fill='both', expand=True)
        
        ttk.Button(self.log_frame, text="Clear Logs", command=self.clear_logs, style='danger.TButton').pack(pady=5)

    def create_coord_tab(self):
        self.coord_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.coord_tab, text="Coordinates")

        coord_frame = ttk.LabelFrame(self.coord_tab, text="Mouse Position Finder", padding=10)
        coord_frame.pack(fill='both', expand=True, padx=5, pady=5)

        ttk.Label(coord_frame, text="Select Target Window:").pack(anchor='w', pady=(0, 2))
        self.selected_hwnd = tk.StringVar()
        self.window_combo = ttk.Combobox(coord_frame, textvariable=self.selected_hwnd, state='readonly')
        self.window_combo.pack(fill='x', pady=(0, 8))

        ttk.Button(coord_frame, text="Refresh Window List", command=self.populate_window_list, style='info.TButton').pack(pady=(0, 10))

        self.coord_label = ttk.Label(
            coord_frame, 
            text="Screen: X=0, Y=0\nWindow-relative: X=0, Y=0\nColor: null", 
            font=('Consolas', 9)
        )
        self.coord_label.pack(pady=10)
        self.make_label_copyable(self.coord_label)

        self.hotkey_listening = tk.BooleanVar(value=True)
        self.toggle_listen_btn = ttk.Checkbutton(
            coord_frame, 
            text="Enable Hotkey Listener (F8)", 
            variable=self.hotkey_listening, 
            command=self.toggle_hotkey_listener
        )
        self.toggle_listen_btn.pack(pady=5)

        self.tracking = tk.BooleanVar(value=False)
        self.toggle_tracking_btn = ttk.Checkbutton(
            coord_frame, 
            text="Enable Live Tracking", 
            variable=self.tracking, 
            command=self.toggle_tracking
        )
        self.toggle_tracking_btn.pack(pady=5)

        if self.hotkey_listening.get():
            self.toggle_hotkey_listener()
    
    def toggle_hotkey_listener(self):
        try:
            if self.hotkey_listening.get():
                keyboard.add_hotkey('f8', self.capture_mouse_position)
                self.log_action("Hotkey listener enabled (Press F8 to capture position)", 'system')
            else:
                keyboard.remove_hotkey('f8')
                self.log_action("Hotkey listener disabled", 'system')
        except Exception as e:
            self.log_action(f"Error toggling hotkey listener: {e}", 'error')

    def capture_mouse_position(self):
        """Capture mouse position using CoordinateFinder utility"""
        try:
            selected = self.selected_hwnd.get()
            hwnd = None
            
            if selected:
                hwnd = self.coord_finder.parse_hwnd_from_selection(selected)
                if hwnd is None:
                    self.log_action("Error parsing HWND from selection", "error")
                    return
            
            # Capture position data
            data = self.coord_finder.capture_position_data(hwnd)
            
            # Format and display
            display_text = self.coord_finder.format_position_string(data)
            self.coord_label.config(text=display_text)
            
            # Log the capture
            if hwnd:
                log_msg = f"Captured HWND={hwnd}, Relative: X={data['rel_x']}, Y={data['rel_y']}, Color: {data['hex_color']}"
            else:
                log_msg = f"Captured Screen: X={data['screen_x']}, Y={data['screen_y']}, Color: {data['hex_color']}"
            
            self.log_action(log_msg, "success")

        except Exception as e:
            self.coord_label.config(text="Error capturing coordinates")
            self.log_action(f"Coordinate capture error: {e}", "error")

    def toggle_tracking(self):
        if self.tracking.get():
            self.log_action("Live coordinate tracking enabled", 'system')
            self.update_mouse_position()
        else:
            self.log_action("Live coordinate tracking stopped", 'system')

    def update_mouse_position(self):
        """Update mouse position display in real-time"""
        if not self.tracking.get():
            return
        
        try:
            x, y = self.coord_finder.get_screen_position()
            self.coord_label.config(text=f"X: {x}, Y: {y}")
        except Exception as e:
            self.coord_label.config(text=f"Error: {e}")
        
        self.root.after(100, self.update_mouse_position)

    def populate_window_list(self):
        """Populate window combobox using CoordinateFinder utility"""
        try:
            window_list = self.coord_finder.get_window_info_list()
            self.window_combo['values'] = window_list
            
            if window_list:
                self.window_combo.current(0)
                self.log_action(f"Loaded {len(window_list)} client(s) into coordinate finder", 'system')
            else:
                self.log_action("No windows found matching instance name", 'error')
                
        except Exception as e:
            self.log_action(f"Error populating window list: {e}", 'error')

    def make_label_copyable(self, label):
        """Allow right-click to copy label text to clipboard"""
        def copy_text(event=None):
            self.root.clipboard_clear()
            self.root.clipboard_append(label.cget("text"))
        label.bind("<Button-3>", copy_text)

    def set_size(self):
        success = resize_all_clients(self.log_action, action_label="Setting window size for all clients")
        if success:
            self.start_btn['state'] = 'normal'
            self.set_size_btn['state'] = 'disabled'
            self.resize_btn['state'] = 'normal'

    def start_clicker(self):
        mode = self.mode_var.get()
        self.log_action(f"Starting mode: {mode}", 'control')
        self.start_btn['state'] = 'disabled'
        self.stop_btn['state'] = 'normal'
        self.resize_btn['state'] = 'disabled'

        if mode == "Solo":
            run_solo_mode(self.log_action, self.CONFIG_PATH, self.COORDS_PATH)

        elif mode == "Realm Raid":
            # Collect HWND list for all active instances
            cfg = configparser.ConfigParser()
            cfg.read(self.CONFIG_PATH, encoding='utf-8')
            instance_name = cfg.get("GLOBAL", "instance", fallback="")

            if not instance_name:
                self.log_action("Error: No instance name configured in config.ini", "error")
                return

            hwnd_list = []
            for win in gw.getWindowsWithTitle(instance_name):
                if win._hWnd and win.visible:
                    hwnd_list.append(win)

            if not hwnd_list:
                self.log_action(f"No active windows found with title: {instance_name}", "error")
                return

            self.log_action(f"Found {len(hwnd_list)} Realm Raid window(s).", "system")
            run_rr_mode(self.log_action, self.CONFIG_PATH, self.COORDS_PATH, hwnd_list)

        else:
           self.log_action(f"Mode '{mode}' not implemented yet.", 'error')

    def stop_clicker(self):
        mode = self.mode_var.get()
        self.log_action(f"Stopping mode: {mode}", 'control')

        if mode == "Solo":
            stop_solo_mode()
        elif mode == "Realm Raid":
            stop_rr_mode()
        else:
            self.log_action(f"Mode '{mode}' not implemented yet.", 'error')

        self.start_btn['state'] = 'normal'
        self.resize_btn['state'] = 'normal'
        self.stop_btn['state'] = 'disabled'

    def resize_clients(self):
        success = resize_all_clients(self.log_action, action_label="Resizing client windows")
        if success:
            self.resize_btn['state'] = 'normal'

    def refresh_client_list(self):
        self.log_action("Refreshing client list", 'system')
        self.tree.delete(*self.tree.get_children())
        config = configparser.ConfigParser()
        config.read(self.CONFIG_PATH)
        instance_name = config.get('GLOBAL', 'instance', fallback='')

        try:
            windows = gw.getWindowsWithTitle(instance_name)
            for i, window in enumerate(windows[:10]):
                hwnd = window._hWnd if hasattr(window, '_hWnd') else hex(id(window))
                pos = f"{window.left},{window.top}"
                self.tree.insert('', 'end', values=(hwnd, pos))
        except Exception as e:
            self.log_action(f"Error refreshing client list: {str(e)}", 'error')

    def log_action(self, message, tag='system'):
        self.log_text.config(state='normal')
        self.log_text.insert('end', f"[{tag.upper()}] {message}\n", tag)
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def clear_logs(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, 'end')
        self.log_text.config(state='disabled')
        self.log_action("Logs cleared", 'system')

    def load_settings(self):
        self.log_action("Loaded settings from config", 'system')

    def save_settings(self):
        settings = {
            'party_default': self.party_default.get(),
            'accept_bounty': self.accept_bounty.get(),
            'mute_clients': self.mute_clients.get(),
            'refresh_raid': self.refresh_raid.get()
        }
        self.log_action(f"Settings saved: {settings}", 'success')