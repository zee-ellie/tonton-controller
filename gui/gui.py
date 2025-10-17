import tkinter as tk
from tkinter import ttk
from ttkbootstrap import Style, dialogs
import configparser
from cogs.window_manager import resize_all_clients
from cogs.mode_solo import run_solo_mode, stop_solo_mode
from cogs.mode_rr import run_rr_mode, stop_rr_mode
from cogs.coord_finder import CoordinateFinder
from cogs.target_window_manager import TargetWindowManager
from cogs.mode_manager import ModeManager
from cogs.window_fetcher import WindowFetcher
from cogs.window_settings_manager import WindowSettingsManager

class ClientControlGUI:
    def __init__(self, root, config_path, coords_path):
        self.CONFIG_PATH = config_path
        self.COORDS_PATH = coords_path
        self.root = root

        try:
            import ctypes
            myappid = 'mycompany.tontontroller.1.0'  # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass        

        self.style = Style(theme='cyborg')

        # Initialize WindowFetcher first
        self.window_fetcher = WindowFetcher(config_path)
        
        # Initialize all managers
        self.coord_finder = CoordinateFinder(config_path)
        self.target_window_manager = TargetWindowManager(config_path)
        self.mode_manager = ModeManager(self.target_window_manager, config_path)
        self.window_settings_manager = WindowSettingsManager(config_path)

        # Initialize stored HWND
        self.current_coord_hwnd = None
        
        # Automation state tracking
        self.automation_running = False

        # Check for required window
        if not self.validate_initial_setup():
            return
            
        self.setup_gui()

    def validate_initial_setup(self):
        """Validate that required windows exist"""
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
            return False
            
        windows = self.window_fetcher.get_all_windows()
        if not windows:
            dialogs.Messagebox.show_error(
                title="Window Not Found",
                message=f"No window found with title: '{instance_name}'\nPlease launch the game first.",
                parent=self.root
            )
            self.root.destroy()
            return False
        
        return True

    def setup_gui(self):
        self.root.title("吨吨鼠Controls")
        self.root.geometry("300x400")
        self.root.resizable(False, False)

        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass  # Fail silently if icon not found
        
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
        
        # Disable mode dropdown initially (since Set Size button is active)
        self.mode_combo['state'] = 'disabled'
        
        # Load settings
        self.load_settings()
        
        # NEW: Initialize target window display BEFORE refreshing all windows
        self.init_target_window_display()
        
        # Refresh all window lists after GUI is fully set up
        self.refresh_all_windows()
        
        # Set up periodic automation status check
        self.check_automation_status()

    def create_control_tab(self):
        self.control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.control_tab, text="Control")
        
        # Mode selection frame
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
        self.mode_combo.bind('<<ComboboxSelected>>', self.on_mode_changed)
        
        # Status indicator frame
        status_frame = ttk.LabelFrame(self.control_tab, text="Status", padding=10)
        status_frame.pack(fill='x', padx=5, pady=5)
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Idle", 
            font=('Arial', 10, 'bold'),
            foreground='gray'
        )
        self.status_label.pack()
        
        # Control buttons frame
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
        
        # Target Window frame (initially hidden)
        self.win_frame = ttk.LabelFrame(self.control_tab, text="Target Window", padding=10)
        
        self.win_var = tk.StringVar()
        self.win_combo = ttk.Combobox(self.win_frame, textvariable=self.win_var, state='readonly')
        self.win_combo.pack(fill='x', pady=(0, 10))
        
        # Buttons frame for centering
        button_frame = ttk.Frame(self.win_frame)
        button_frame.pack(fill='x', pady=(0, 5))
        
        self.refresh_btn = ttk.Button(button_frame, text="Refresh Windows", command=self.refresh_all_windows, style='info.TButton')
        self.set_btn = ttk.Button(button_frame, text="Set Window", command=self.set_target_window, style='primary.TButton')
        
        self.refresh_btn.pack(side='left', expand=True, padx=(10, 5))
        self.set_btn.pack(side='left', expand=True, padx=(5, 10))
        
        self.win_frame.pack_forget()

    def create_settings_tab(self):
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")
        
        # Window Settings frame
        win_settings_frame = ttk.LabelFrame(self.settings_tab, text="Window Settings", padding=10)
        win_settings_frame.pack(fill='x', padx=5, pady=5)
        
        # Label for window width
        ttk.Label(win_settings_frame, text="Desired Window Width:").pack(anchor='w', pady=(0, 5))
        
        # Width spinbox
        self.width_var = tk.StringVar()
        settings_info = self.window_settings_manager.get_window_settings()
        
        self.width_spinbox = ttk.Spinbox(
            win_settings_frame,
            from_=settings_info['min_width'],
            to=settings_info['max_width'],
            textvariable=self.width_var,
            width=15,
            validate='focusout',
            validatecommand=(self.root.register(self.validate_width_input), '%P')
        )
        self.width_spinbox.pack(fill='x', pady=(0, 10))
        
        # Buttons frame
        buttons_frame = ttk.Frame(win_settings_frame)
        buttons_frame.pack(fill='x')
        
        self.set_width_btn = ttk.Button(
            buttons_frame, 
            text="Set Width", 
            command=self.set_window_width,
            style='primary.TButton'
        )
        self.set_width_btn.pack(side='left', expand=True, padx=(0, 5))
        
        self.reset_width_btn = ttk.Button(
            buttons_frame, 
            text="Reset to Default", 
            command=self.reset_window_width,
            style='info.TButton'
        )
        self.reset_width_btn.pack(side='left', expand=True, padx=(5, 0))
        
        # Load current width
        self.load_current_width()
        
        # Configuration frame
        settings_frame = ttk.LabelFrame(self.settings_tab, text="Configuration", padding=10)
        settings_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        self.party_default = tk.BooleanVar(value=True)
        self.accept_bounty = tk.BooleanVar(value=True)
        self.mute_clients = tk.BooleanVar()
        
        ttk.Checkbutton(settings_frame, text="Party by default", variable=self.party_default).pack(anchor='w', pady=2)
        ttk.Checkbutton(settings_frame, text="Accept Bounty Invites", variable=self.accept_bounty).pack(anchor='w', pady=2)
        ttk.Checkbutton(settings_frame, text="Mute Clients", variable=self.mute_clients).pack(anchor='w', pady=2)
        
        ttk.Button(settings_frame, text="Save Settings", command=self.save_settings, style='success.TButton').pack(pady=10)

    def create_clients_tab(self):
        """Updated clients tab with reordered columns: Client | HWND | Position"""
        self.clients_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.clients_tab, text="Clients")
        
        self.client_list_frame = ttk.LabelFrame(self.clients_tab, text="Active Clients", padding=10)
        self.client_list_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(self.client_list_frame, columns=('Client', 'HWND', 'Position'), show='headings')
        self.tree.heading('Client', text='Client')
        self.tree.heading('HWND', text='HWND')
        self.tree.heading('Position', text='Screen Position')
        self.tree.column('Client', width=50)
        self.tree.column('HWND', width=50)
        self.tree.column('Position', width=130)
        
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
        self.notebook.add(self.coord_tab, text="Debug")

        coord_frame = ttk.LabelFrame(self.coord_tab, text="Mouse Position Finder", padding=10)
        coord_frame.pack(fill='both', expand=True, padx=5, pady=5)

        ttk.Label(coord_frame, text="Select Target Window:").pack(anchor='w', pady=(0, 2))
        self.selected_hwnd = tk.StringVar()
        self.window_combo = ttk.Combobox(coord_frame, textvariable=self.selected_hwnd, state='readonly')
        self.window_combo.pack(fill='x', pady=(0, 8))

        self.window_combo.bind('<<ComboboxSelected>>', self.on_coord_window_selected)

        ttk.Button(coord_frame, text="Refresh Window List", command=self.populate_coord_window_list, style='info.TButton').pack(pady=(0, 10))

        self.coord_label = ttk.Label(
            coord_frame, 
            text="Screen: X=0, Y=0\nClient-relative: X=0, Y=0\nColor: null\nClient size: Unknown", 
            font=('Consolas', 9),
            justify='left'
        )
        self.coord_label.pack(pady=10, fill='x')
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
        
        # Enable hotkey listener immediately
        self.toggle_hotkey_listener()

    def on_mode_changed(self, event=None):
        """Handle mode change - show/hide target window frame"""
        selected_mode = self.mode_var.get()
        mode_info = self.mode_manager.set_mode(selected_mode)
        
        if mode_info['needs_target_window']:
            self.win_frame.pack(fill='x', padx=5, pady=5)
            if not mode_info['has_target_window']:
                self.log_action("Realm Raid mode requires a target window to be set", 'system')
        else:
            self.win_frame.pack_forget()

    def init_target_window_display(self):
        """
        Initialize target window display after GUI is fully set up.
        
        Behavior:
        1. If target_window_manager has a saved target HWND:
        - Try to find that HWND in current window list
        - If found: Display it in dropdown (e.g., "Client #2 - Top Left...")
        - If not found: Auto-select Client #1 as new target
        2. If no saved target:
        - Auto-select Client #1 (already done by target_window_manager.__init__)
        
        The key is that we search by HWND, not by position!
        """
        try:
            # Get sorted window list
            window_list = self.window_fetcher.get_window_info_list()
            
            if not window_list:
                self.log_action("No windows available for target selection", 'error')
                return
            
            # Populate combobox with sorted list
            self.win_combo['values'] = window_list
            
            # Check if target window manager has a target set
            if self.target_window_manager.has_target_window():
                target_hwnd = self.target_window_manager.get_target_hwnd()
                
                # Get the display string for this HWND
                target_string = self.target_window_manager.get_target_window_string()
                
                if target_string and target_string in window_list:
                    # Target exists in current window list - display it
                    self.win_var.set(target_string)
                    
                    # Extract client number from string for logging
                    client_num = target_string.split()[1].rstrip(' -')
                    self.log_action(f"✓ Loaded saved target: {client_num} (HWND={target_hwnd})", 'success')
                else:
                    # Target no longer exists, auto-select Client #1 as new target
                    first_window = window_list[0]
                    self.win_var.set(first_window)
                    
                    # Automatically set and save Client #1 as the new target
                    success, message = self.target_window_manager.set_target_window(first_window)
                    if success:
                        new_hwnd = self.window_fetcher.parse_hwnd_from_selection(first_window)
                        self.log_action(f"Previous target (HWND={target_hwnd}) not found. Auto-selected Client #1 (HWND={new_hwnd})", 'system')
                    else:
                        self.log_action(f"⚠ Previous target (HWND={target_hwnd}) not found, but failed to set new target: {message}", 'error')
            else:
                # No target set (shouldn't happen due to auto_set_first_window in __init__)
                # But handle it just in case
                first_window = window_list[0]
                self.win_var.set(first_window)
                
                success, message = self.target_window_manager.set_target_window(first_window)
                if success:
                    new_hwnd = self.window_fetcher.parse_hwnd_from_selection(first_window)
                    self.log_action(f"Auto-selected Client #1 as initial target (HWND={new_hwnd})", 'system')
                else:
                    self.log_action(f"Failed to set initial target: {message}", 'error')
                    
        except Exception as e:
            self.log_action(f"Error initializing target window display: {e}", 'error')
            import traceback
            traceback.print_exc()

    def refresh_all_windows(self):
        """Refresh window lists in all tabs"""
        try:
            window_list = self.window_fetcher.get_window_info_list()
            
            # Update Control tab dropdown
            self.win_combo['values'] = window_list
            
            # NEW: Set current target window as selected (if exists)
            if window_list:
                current_target = self.target_window_manager.get_target_window_string()
                if current_target and current_target in window_list:
                    self.win_var.set(current_target)
                    self.log_action(f"Target window: {current_target}", 'success')
                elif self.win_combo.get() == "":
                    # Fallback: select first window if no target set
                    self.win_combo.current(0)
            
            # Update Coordinates tab dropdown
            self.window_combo['values'] = window_list
            if window_list and self.window_combo.get() == "":
                self.window_combo.current(0)
            
            # Refresh Clients tab
            self.refresh_client_list()
            
            if window_list:
                self.log_action(f"Refreshed all window lists: {len(window_list)} window(s)", 'system')
                
        except Exception as e:
            self.log_action(f"Error refreshing windows: {e}", 'error')

    def on_coord_window_selected(self, event=None):
        """Store the selected HWND when Coordinate tab dropdown changes"""
        selected = self.selected_hwnd.get()
        
        if selected:
            hwnd = self.coord_finder.parse_hwnd_from_selection(selected)
            
            if hwnd:
                self.current_coord_hwnd = hwnd
                self.log_action(f"Coordinate target set to HWND: {hwnd}", 'system')

    def refresh_client_list(self):
        """Refresh client list in Clients tab with reordered columns: Client | HWND | Position"""
        self.tree.delete(*self.tree.get_children())
        
        try:
            treeview_data = self.window_fetcher.get_window_treeview_data()
            # Reorder the tuple values to match: Client | HWND | Position
            for client_label, position, hwnd in treeview_data:
                self.tree.insert('', 'end', values=(client_label, hwnd, position))
        except Exception as e:
            self.log_action(f"Error refreshing client list: {str(e)}", 'error')

    def populate_coord_window_list(self):
        """Populate window list in Coordinates tab"""
        try:
            window_list = self.window_fetcher.get_window_info_list()
            self.window_combo['values'] = window_list
            
            if window_list and self.window_combo.get() == "":
                self.window_combo.current(0)
                self.log_action(f"Loaded {len(window_list)} client(s) into coordinate finder", 'system')
            else:
                self.log_action("No windows found matching instance name", 'error')
                
        except Exception as e:
            self.log_action(f"Error populating window list: {e}", 'error')

    def set_target_window(self):
        """Set the target window using the manager"""
        selected = self.win_var.get()
        
        if not selected:
            self.log_action("No window selected", 'error')
            return
        
        success, message = self.target_window_manager.set_target_window(selected)
        
        if success:
            self.log_action(message, 'success')
            # Show visual feedback in combobox
            self.win_combo.selection_clear()
        else:
            self.log_action(message, 'error')

    def toggle_hotkey_listener(self):
        """Toggle F8 hotkey listener using CoordinateFinder"""
        try:
            if self.hotkey_listening.get():
                self.coord_finder.toggle_hotkey_listener(self.capture_mouse_position)
                self.log_action("Hotkey listener enabled (Press F8 to capture position)", 'system')
            else:
                self.coord_finder.toggle_hotkey_listener(self.capture_mouse_position)
                self.log_action("Hotkey listener disabled", 'system')
        except Exception as e:
            self.log_action(f"Error toggling hotkey listener: {e}", 'error')

    def capture_mouse_position(self):
        """Capture mouse position using the stored HWND"""
        try:
            if hasattr(self, 'current_coord_hwnd') and self.current_coord_hwnd:
                hwnd = self.current_coord_hwnd
            else:
                selected = self.selected_hwnd.get()
                hwnd = self.coord_finder.parse_hwnd_from_selection(selected) if selected else None
                if hwnd:
                    self.current_coord_hwnd = hwnd
            
            if not hwnd:
                self.log_action("No window selected for coordinate capture", 'error')
                return
                
            data = self.coord_finder.capture_client_position_data(hwnd)
            display_text = self.coord_finder.format_position_string(data)
            self.coord_label.config(text=display_text)
            
            if data.get('client_x') is not None:
                log_msg = f"Captured Client: X={data['client_x']}, Y={data['client_y']}, Color: {data['hex_color']}"
            else:
                log_msg = f"Captured Screen: X={data['screen_x']}, Y={data['screen_y']}, Color: {data['hex_color']}"
            
            self.log_action(log_msg, "success")

        except Exception as e:
            self.coord_label.config(text="Error capturing coordinates")
            self.log_action(f"Coordinate capture error: {e}", "error")

    def toggle_tracking(self):
        """Toggle live coordinate tracking"""
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
            selected = self.selected_hwnd.get()
            hwnd = self.coord_finder.parse_hwnd_from_selection(selected) if selected else None
            
            data = self.coord_finder.get_live_update(hwnd)
            display_text = self.coord_finder.format_position_string(data)
            self.coord_label.config(text=display_text)
            
        except Exception as e:
            self.coord_label.config(text=f"Error: {e}")
        
        self.root.after(100, self.update_mouse_position)

    def make_label_copyable(self, label):
        """Allow right-click to copy label text to clipboard"""
        def copy_text(event=None):
            self.root.clipboard_clear()
            self.root.clipboard_append(label.cget("text"))
        label.bind("<Button-3>", copy_text)

    def update_status(self, text, color='gray'):
        """Update status label"""
        self.status_label.config(text=text, foreground=color)

    def check_automation_status(self):
        """Periodically check if automation is still running"""
        # Import here to avoid circular imports
        from cogs.mode_rr import _rr_running
        
        mode = self.mode_var.get()
        
        if mode == "Realm Raid":
            if _rr_running and self.automation_running:
                self.update_status("Running: Realm Raid", 'green')
            elif self.automation_running and not _rr_running:
                # Automation stopped (likely due to error or completion)
                self.automation_running = False
                self.start_btn['state'] = 'normal'
                self.stop_btn['state'] = 'disabled'
                self.resize_btn['state'] = 'normal'
                self.mode_combo['state'] = 'readonly'
                self.update_status("Stopped", 'red')
                self.log_action("Automation stopped (check logs for details)", 'system')
            else:
                self.update_status("Idle", 'gray')
        elif mode == "Solo":
            # Add Solo mode status checking if needed
            if self.automation_running:
                self.update_status("Running: Solo", 'green')
            else:
                self.update_status("Idle", 'gray')
        else:
            self.update_status("Idle", 'gray')
        
        # Schedule next check
        self.root.after(1000, self.check_automation_status)

    def start_clicker(self):
        """Start automation with proper target window handling"""
        mode = self.mode_var.get()
        
        # Check if mode can be started
        is_valid, message = self.mode_manager.validate_mode_setup(mode)
        if not is_valid:
            self.log_action(message, 'error')
            return
        
        self.log_action(f"Starting mode: {mode}", 'control')
        self.automation_running = True
        self.start_btn['state'] = 'disabled'
        self.stop_btn['state'] = 'normal'
        self.resize_btn['state'] = 'disabled'
        self.mode_combo['state'] = 'disabled'
        self.update_status(f"Starting: {mode}", 'yellow')

        if mode == "Solo":
            run_solo_mode(self.log_action, self.CONFIG_PATH, self.COORDS_PATH)
            self.update_status("Running: Solo", 'green')

        elif mode == "Realm Raid":
            # Get the target HWND from target_window_manager (stored in memory)
            target_hwnd = self.target_window_manager.get_target_hwnd()
            
            if not target_hwnd:
                self.log_action("Error: No target window set for Realm Raid", "error")
                self.automation_running = False
                self.start_btn['state'] = 'normal'
                self.stop_btn['state'] = 'disabled'
                self.resize_btn['state'] = 'normal'
                self.mode_combo['state'] = 'readonly'
                self.update_status("Error", 'red')
                return
            
            # Verify the target window still exists
            target_window = self.window_fetcher.get_window_by_hwnd(target_hwnd)
            if not target_window:
                self.log_action(f"Error: Target window (HWND={target_hwnd}) no longer exists", "error")
                self.log_action("Please refresh windows and select a new target", "error")
                self.automation_running = False
                self.start_btn['state'] = 'normal'
                self.stop_btn['state'] = 'disabled'
                self.resize_btn['state'] = 'normal'
                self.mode_combo['state'] = 'readonly'
                self.update_status("Error", 'red')
                return
            
            # Log which client is being used
            sorted_windows = self.window_fetcher.get_all_windows_sorted()
            for idx, win in enumerate(sorted_windows, 1):
                if win._hWnd == target_hwnd:
                    self.log_action(f"Using Client #{idx} as target: HWND={target_hwnd}", "system")
                    self.log_action(f"Window position: ({target_window.left}, {target_window.top})", "system")
                    break
            
            # Pass the specific target HWND to run_rr_mode (NOT a list!)
            run_rr_mode(self.log_action, self.CONFIG_PATH, self.COORDS_PATH, target_hwnd)
            self.update_status("Running: Realm Raid", 'green')

        else:
            self.log_action(f"Mode '{mode}' not implemented yet.", 'error')
            self.automation_running = False
            self.update_status("Error", 'red')

    def stop_clicker(self):
        mode = self.mode_var.get()
        self.log_action(f"Stop requested for mode: {mode}", 'control')
        self.update_status("Stopping...", 'yellow')

        stop_success = False
        if mode == "Solo":
            stop_success = stop_solo_mode()
        elif mode == "Realm Raid":
            stop_success = stop_rr_mode()
            if stop_success:
                self.log_action("Stop signal sent to Realm Raid automation", 'system')
            else:
                self.log_action("No active Realm Raid automation to stop", 'error')
        else:
            self.log_action(f"Mode '{mode}' not implemented yet.", 'error')

        self.automation_running = False
        self.start_btn['state'] = 'normal'
        self.resize_btn['state'] = 'normal'
        self.stop_btn['state'] = 'disabled'
        self.mode_combo['state'] = 'readonly'
        self.update_status("Stopped", 'gray')
    
    def validate_width_input(self, value):
        """GUI wrapper for width validation"""
        return self.window_settings_manager.validate_width_input(value)

    def load_current_width(self):
        """Load current width from config and set in spinbox"""
        current_width = self.window_settings_manager.get_current_width()
        self.width_var.set(str(current_width))

    def set_window_width(self):
        """Set the window width and resize windows"""
        try:
            width_str = self.width_var.get().strip()
            if not width_str:
                self.log_action("Please enter a width value", 'error')
                return
                
            if not width_str.isdigit():
                self.log_action("Width must be a number", 'error')
                return
                
            width = int(width_str)
            success, message = self.window_settings_manager.set_window_width(width)
            
            if success:
                self.log_action(message, 'success')
                self.resize_windows_after_width_change()
                self.set_size_btn['state'] = 'disabled'
                self.mode_combo['state'] = 'readonly'  # Enable mode dropdown when Set Size becomes inactive
                self.start_btn['state'] = 'normal'
                self.resize_btn['state'] = 'normal'
            else:
                self.log_action(message, 'error')
                
        except ValueError:
            self.log_action("Please enter a valid number for width", 'error')
        except Exception as e:
            self.log_action(f"Error setting window width: {e}", 'error')

    def reset_window_width(self):
        """Reset window width and resize windows"""
        success, message, default_width = self.window_settings_manager.reset_window_width()
        
        if success:
            self.width_var.set(str(default_width))
            self.log_action(message, 'success')
            self.resize_windows_after_width_change()
            self.set_size_btn['state'] = 'disabled'
            self.mode_combo['state'] = 'readonly'  # Enable mode dropdown when Set Size becomes inactive
            self.start_btn['state'] = 'normal'
            self.resize_btn['state'] = 'normal'
        else:
            self.log_action(message, 'error')

    def resize_windows(self, action_label="Resizing client windows", update_buttons=True):
        """Unified method to resize all windows"""
        try:
            success = resize_all_clients(self.log_action, action_label=action_label)
            
            if success and update_buttons:
                self.start_btn['state'] = 'normal'
                self.resize_btn['state'] = 'normal'
                if "Setting window size" in action_label:
                    self.set_size_btn['state'] = 'disabled'
                    self.mode_combo['state'] = 'readonly'  # Enable mode dropdown when Set Size becomes inactive
            
            return success
            
        except Exception as e:
            self.log_action(f"Error during resize operation: {e}", 'error')
            return False

    def resize_clients(self):
        """Manual resize clients"""
        self.resize_windows(action_label="Resizing client windows", update_buttons=True)

    def set_size(self):
        """Initial window size setup"""
        self.resize_windows(action_label="Setting window size for all clients", update_buttons=True)

    def resize_windows_after_width_change(self):
        """Resize after width change"""
        self.resize_windows(action_label="Auto-resizing windows to new width", update_buttons=False)

    def log_action(self, message, tag='system'):
        """Thread-safe logging"""
        def _log():
            self.log_text.config(state='normal')
            self.log_text.insert('end', f"[{tag.upper()}] {message}\n", tag)
            self.log_text.see('end')
            self.log_text.config(state='disabled')
        
        # Schedule on main thread if called from another thread
        self.root.after(0, _log)

    def clear_logs(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, 'end')
        self.log_text.config(state='disabled')
        self.log_action("Logs cleared", 'system')

    def load_settings(self):
        """Load settings from config"""
        try:
            cfg = configparser.ConfigParser()
            cfg.read(self.CONFIG_PATH, encoding='utf-8')
            
            if cfg.has_section('GLOBAL'):
                self.party_default.set(cfg.getboolean('GLOBAL', 'party', fallback=True))
                self.accept_bounty.set(cfg.getboolean('GLOBAL', 'bounty', fallback=True))
                self.mute_clients.set(cfg.getboolean('GLOBAL', 'mute', fallback=False))
            
            self.log_action("Loaded settings from config", 'system')
        except Exception as e:
            self.log_action(f"Error loading settings: {e}", 'error')

    def save_settings(self):
        """Save settings to config"""
        try:
            cfg = configparser.ConfigParser()
            cfg.read(self.CONFIG_PATH, encoding='utf-8')
            
            if not cfg.has_section('GLOBAL'):
                cfg.add_section('GLOBAL')
            
            cfg.set('GLOBAL', 'party', str(self.party_default.get()))
            cfg.set('GLOBAL', 'bounty', str(self.accept_bounty.get()))
            cfg.set('GLOBAL', 'mute', str(self.mute_clients.get()))
            
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                cfg.write(f)
            
            settings = {
                'party_default': self.party_default.get(),
                'accept_bounty': self.accept_bounty.get(),
                'mute_clients': self.mute_clients.get()
            }
            self.log_action(f"Settings saved: {settings}", 'success')
        except Exception as e:
            self.log_action(f"Error saving settings: {e}", 'error')