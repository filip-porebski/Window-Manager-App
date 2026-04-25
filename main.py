import sys
import os
import json
import threading
import logging
import time
import tkinter as tk
import winreg
from tkinter import ttk, messagebox
from typing import Callable, Dict, Optional, Tuple, NamedTuple, TypedDict, Any

import keyboard
import win32gui
import win32con
import win32api
from PIL import Image, ImageDraw, ImageTk
import pystray

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('window_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RECT(NamedTuple):
    """A named tuple representing a rectangle with left, top, right, and bottom coordinates.

    Attributes:
        left (int): The x-coordinate of the left edge
        top (int): The y-coordinate of the top edge
        right (int): The x-coordinate of the right edge
        bottom (int): The y-coordinate of the bottom edge
    """
    left: int
    top: int
    right: int
    bottom: int

def rects_intersect(a: RECT, b: RECT) -> bool:
    """Check if two rectangles intersect."""
    return not (a.left >= b.right or a.right <= b.left or a.top >= b.bottom or a.bottom <= b.top)

def get_current_monitor() -> int:
    """Get the handle to the monitor where the cursor is currently located."""
    cursor = win32gui.GetCursorPos()
    return win32api.MonitorFromPoint(cursor, win32con.MONITOR_DEFAULTTONEAREST)

class MonitorInfo(TypedDict):
    Monitor: Tuple[int, int, int, int]
    Work: Tuple[int, int, int, int]
    Flags: int

class WindowManagerApp(tk.Tk):
    """Main application class for the Window Manager App."""

    def __init__(self):
        super().__init__()
        self._initialize_window()
        self._initialize_state_variables()
        self._setup_ui()
        self._configure_window_behavior()
        self._start_minimized()

    def _initialize_window(self):
        """Configure initial window properties."""
        self.title("Window Manager")
        # Set initial size but allow dynamic resizing
        self.geometry("840x650")
        self.minsize(760, 580)  # Set minimum size
        # Set app icon for all windows (main + dialogs)
        self._app_icon = ImageTk.PhotoImage(self._create_tray_icon_image())
        self.iconphoto(True, self._app_icon)
        self.hwnd = self.winfo_id()

    def _initialize_state_variables(self):
        """Initialize instance variables and state tracking."""
        self.icon: Optional[Any] = None
        self.hotkeys: Dict[str, Callable] = {}
        self.startup_var = tk.BooleanVar()
        self.minimize_sequence_started = False
        self.minimize_sequence_start_time = 0
        self.resize_increment = 10  # Default resize increment in pixels
        self.hotkey_monitor_thread = None
        self.hotkey_monitor_running = False
        self.last_hotkey_test_time = 0
        self.hotkey_failure_count = 0

    def _setup_ui(self):
        """Set up UI components and load settings."""
        self._setup_styles()
        self._create_widgets()
        self._load_settings()
        self._register_hotkeys()
        self._start_hotkey_monitor()

    def _configure_window_behavior(self):
        """Configure window-level event handlers."""
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        # Bind window state change events to handle minimize to tray
        self.bind('<Unmap>', self.on_window_minimize)

    def _start_minimized(self):
        """Start application minimized to system tray."""
        self.withdraw()
        self.minimize_to_tray()

    def _setup_styles(self):
        """Configure a polished ttk theme for the application."""
        self.palette = {
            "bg": "#eef3f8",
            "surface": "#ffffff",
            "surface_alt": "#f8fafc",
            "border": "#d9e2ec",
            "text": "#102033",
            "muted": "#64748b",
            "primary": "#2563eb",
            "primary_hover": "#1d4ed8",
            "primary_pressed": "#1e40af",
            "accent": "#0f766e",
            "danger": "#b91c1c",
            "selection": "#dbeafe",
        }

        self.configure(bg=self.palette["bg"])
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            logger.warning("Failed to apply clam theme; using default ttk theme.")

        self.option_add("*Font", ("Segoe UI", 10))
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

        self.style.configure(".", font=("Segoe UI", 10), background=self.palette["bg"], foreground=self.palette["text"])
        self.style.configure("App.TFrame", background=self.palette["bg"])
        self.style.configure("Card.TFrame", background=self.palette["surface"], borderwidth=1, relief="solid")
        self.style.configure("CardInner.TFrame", background=self.palette["surface"])
        self.style.configure("Toolbar.TFrame", background=self.palette["surface"])
        self.style.configure("Title.TLabel", background=self.palette["bg"], foreground=self.palette["text"], font=("Segoe UI Semibold", 22))
        self.style.configure("Subtitle.TLabel", background=self.palette["bg"], foreground=self.palette["muted"], font=("Segoe UI", 10))
        self.style.configure("SectionTitle.TLabel", background=self.palette["surface"], foreground=self.palette["text"], font=("Segoe UI Semibold", 12))
        self.style.configure("SectionHint.TLabel", background=self.palette["surface"], foreground=self.palette["muted"], font=("Segoe UI", 9))
        self.style.configure("Field.TLabel", background=self.palette["surface"], foreground=self.palette["text"], font=("Segoe UI", 10))
        self.style.configure("Hint.TLabel", background=self.palette["surface"], foreground=self.palette["muted"], font=("Segoe UI", 9))
        self.style.configure("Pill.TLabel", background="#e0f2fe", foreground="#075985", font=("Segoe UI Semibold", 9), padding=(10, 5))

        self.style.configure(
            "TEntry",
            fieldbackground=self.palette["surface_alt"],
            foreground=self.palette["text"],
            bordercolor=self.palette["border"],
            lightcolor=self.palette["border"],
            darkcolor=self.palette["border"],
            padding=6,
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=self.palette["surface_alt"],
            foreground=self.palette["text"],
            bordercolor=self.palette["border"],
            lightcolor=self.palette["border"],
            darkcolor=self.palette["border"],
            arrowsize=14,
            padding=5,
        )
        self.style.configure("TCheckbutton", background=self.palette["surface"], foreground=self.palette["text"], font=("Segoe UI", 10))
        self.style.map("TCheckbutton", background=[("active", self.palette["surface"])])

        self.style.configure(
            "Primary.TButton",
            background=self.palette["primary"],
            foreground="#ffffff",
            bordercolor=self.palette["primary"],
            focusthickness=1,
            focuscolor=self.palette["primary"],
            font=("Segoe UI Semibold", 10),
            padding=(14, 8),
        )
        self.style.map(
            "Primary.TButton",
            background=[("pressed", self.palette["primary_pressed"]), ("active", self.palette["primary_hover"])],
            bordercolor=[("pressed", self.palette["primary_pressed"]), ("active", self.palette["primary_hover"])],
            foreground=[("disabled", "#e5e7eb"), ("!disabled", "#ffffff")],
        )
        self.style.configure(
            "Secondary.TButton",
            background=self.palette["surface_alt"],
            foreground=self.palette["text"],
            bordercolor=self.palette["border"],
            font=("Segoe UI Semibold", 10),
            padding=(12, 8),
        )
        self.style.map(
            "Secondary.TButton",
            background=[("pressed", "#e2e8f0"), ("active", "#edf2f7")],
            bordercolor=[("pressed", "#cbd5e1"), ("active", "#cbd5e1")],
        )
        self.style.configure(
            "Compact.TButton",
            background=self.palette["surface_alt"],
            foreground=self.palette["text"],
            bordercolor=self.palette["border"],
            font=("Segoe UI Semibold", 9),
            padding=(8, 6),
        )
        self.style.map(
            "Compact.TButton",
            background=[("pressed", "#e2e8f0"), ("active", "#edf2f7")],
            bordercolor=[("pressed", "#cbd5e1"), ("active", "#cbd5e1")],
        )
        self.style.configure(
            "Danger.TButton",
            background="#fff1f2",
            foreground=self.palette["danger"],
            bordercolor="#fecdd3",
            font=("Segoe UI Semibold", 10),
            padding=(12, 8),
        )
        self.style.map(
            "Danger.TButton",
            background=[("pressed", "#ffe4e6"), ("active", "#ffe4e6")],
            bordercolor=[("pressed", "#fda4af"), ("active", "#fda4af")],
        )

        self.style.configure(
            "Treeview",
            background=self.palette["surface"],
            fieldbackground=self.palette["surface"],
            foreground=self.palette["text"],
            bordercolor=self.palette["border"],
            rowheight=30,
            font=("Segoe UI", 10),
        )
        self.style.configure(
            "Treeview.Heading",
            background=self.palette["surface_alt"],
            foreground=self.palette["muted"],
            bordercolor=self.palette["border"],
            font=("Segoe UI Semibold", 9),
            padding=(8, 6),
        )
        self.style.map("Treeview", background=[("selected", self.palette["selection"])], foreground=[("selected", self.palette["text"])])
        self.style.configure("Horizontal.TScale", background=self.palette["surface"], troughcolor=self.palette["border"])

    def _create_widgets(self):
        """Create GUI widgets."""
        outer_frame = ttk.Frame(self, style="App.TFrame", padding=(24, 22, 24, 18))
        outer_frame.pack(fill="both", expand=True)
        outer_frame.columnconfigure(0, weight=1)
        outer_frame.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(outer_frame, style="App.TFrame")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 18))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Window Manager", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(header_frame, text="Global hotkeys for resizing, centering, and managing active windows.", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Label(header_frame, text="Tray utility", style="Pill.TLabel").grid(row=0, column=1, rowspan=2, sticky="ne", padx=(12, 0))

        content_frame = ttk.Frame(outer_frame, style="App.TFrame")
        content_frame.grid(row=1, column=0, sticky="nsew")
        content_frame.columnconfigure(0, weight=1, minsize=390)
        content_frame.columnconfigure(1, weight=1, minsize=320)
        content_frame.rowconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=0)

        # Keyboard Shortcuts Section
        shortcut_frame = ttk.Frame(content_frame, style="Card.TFrame", padding=(20, 16, 20, 18))
        shortcut_frame.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 16))
        shortcut_frame.columnconfigure(1, weight=1)
        shortcut_frame.columnconfigure(2, weight=0)

        ttk.Label(shortcut_frame, text="Keyboard Shortcuts", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(
            shortcut_frame,
            text="Assign hotkey combinations for the built-in window actions.",
            style="SectionHint.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 14))

        self.shortcuts_entries = {}
        shortcuts = [("Resize to 80%", "resize_80"), ("Fullscreen", "fullscreen"),
                     ("Center Window", "center"), ("Resize to 60%", "resize_60"),
                     ("Expand Window", "expand_window"), ("Shrink Window", "shrink_window")]

        for idx, (label_text, key) in enumerate(shortcuts):
            row = idx + 2
            ttk.Label(shortcut_frame, text=f"{label_text}:", style="Field.TLabel").grid(row=row, column=0, sticky="w", pady=5, padx=(0, 18))
            entry = ttk.Entry(shortcut_frame, width=28)
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            record_button = ttk.Button(
                shortcut_frame,
                text="Record",
                style="Compact.TButton",
                command=lambda shortcut_entry=entry, action_name=label_text: self.record_shortcut(shortcut_entry, action_name),
            )
            record_button.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=5)
            self.shortcuts_entries[key] = entry

        # Resize Increment Configuration
        increment_row = len(shortcuts) + 2
        ttk.Label(shortcut_frame, text="Resize Increment (px):", style="Field.TLabel").grid(row=increment_row, column=0, sticky="w", pady=(10, 5), padx=(0, 18))
        self.increment_var = tk.IntVar(value=10)
        increment_input_frame = ttk.Frame(shortcut_frame, style="CardInner.TFrame")
        increment_input_frame.grid(row=increment_row, column=1, columnspan=2, sticky="ew", pady=(10, 5))
        increment_input_frame.columnconfigure(1, weight=1)
        self.increment_spinbox = ttk.Spinbox(increment_input_frame, from_=5, to=150, textvariable=self.increment_var, width=8, command=self._on_increment_spinbox_changed)
        self.increment_spinbox.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self._increment_scale_var = tk.DoubleVar(value=10)
        self.increment_scale = ttk.Scale(
            increment_input_frame,
            from_=5,
            to=150,
            orient="horizontal",
            variable=self._increment_scale_var,
            command=self._on_increment_scale_changed,
            style="Horizontal.TScale",
        )
        self.increment_scale.grid(row=0, column=1, sticky="ew")
        ttk.Label(
            shortcut_frame,
            text="Controls how far Expand Window and Shrink Window move each edge.",
            style="Hint.TLabel",
        ).grid(row=increment_row + 1, column=1, columnspan=2, sticky="w", pady=(0, 10))

        # Save Button
        self.save_button = ttk.Button(shortcut_frame, text="Save Hotkeys", command=self.save_settings)
        self.save_button.configure(style="Primary.TButton")
        self.save_button.grid(row=increment_row + 2, column=0, columnspan=3, sticky="ew", pady=(4, 0))

        # Custom Resize Actions Section
        custom_frame = ttk.Frame(content_frame, style="Card.TFrame", padding=(20, 16, 20, 18))
        custom_frame.grid(row=0, column=1, sticky="nsew", pady=(0, 16))
        custom_frame.columnconfigure(0, weight=1)
        custom_frame.rowconfigure(2, weight=1)

        custom_header = ttk.Frame(custom_frame, style="Toolbar.TFrame")
        custom_header.grid(row=0, column=0, sticky="ew")
        custom_header.columnconfigure(0, weight=1)
        ttk.Label(custom_header, text="Custom Resize Actions", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            custom_frame,
            text="Create additional resize percentages with dedicated hotkeys.",
            style="SectionHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 12))

        # Treeview to display custom actions
        table_frame = ttk.Frame(custom_frame, style="CardInner.TFrame")
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ('Percentage', 'Hotkey')
        self.tree = ttk.Treeview(table_frame, columns=columns, show='headings', selectmode='browse', height=6)
        self.tree.heading('Percentage', text='Percentage')
        self.tree.heading('Hotkey', text='Hotkey')
        self.tree.column('Percentage', width=90, minwidth=80, anchor='center', stretch=False)
        self.tree.column('Hotkey', width=200, minwidth=120, anchor='w', stretch=True)
        self.tree.grid(row=0, column=0, sticky='nsew')

        tree_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        tree_scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        # Buttons to add and remove custom actions
        btn_frame = ttk.Frame(custom_frame, style="Toolbar.TFrame")
        btn_frame.grid(row=3, column=0, sticky='ew', pady=(12, 0))
        btn_frame.columnconfigure(2, weight=1)

        self.add_button = ttk.Button(btn_frame, text="Add", command=self.add_custom_action)
        self.add_button.configure(style="Secondary.TButton")
        self.add_button.grid(row=0, column=0, sticky='w')

        self.remove_button = ttk.Button(btn_frame, text="Remove", command=self.remove_custom_action)
        self.remove_button.configure(style="Danger.TButton")
        self.remove_button.grid(row=0, column=1, sticky='w', padx=(10, 0))

        # System controls
        system_frame = ttk.Frame(content_frame, style="Card.TFrame", padding=(20, 16, 20, 16))
        system_frame.grid(row=1, column=1, sticky="ew")
        system_frame.columnconfigure(0, weight=1)

        ttk.Label(system_frame, text="System", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(system_frame, text="Control background behavior and startup integration.", style="SectionHint.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        # Start with Windows Checkbox
        self.startup_check = ttk.Checkbutton(system_frame, text="Start with Windows", variable=self.startup_var,
                                             command=self.on_startup_checkbox)
        self.startup_check.grid(row=2, column=0, sticky="w", pady=(0, 2))

        # Minimize to Tray Button
        self.minimize_button = ttk.Button(system_frame, text="Minimize to Tray", command=self.minimize_to_tray)
        self.minimize_button.configure(style="Secondary.TButton")
        self.minimize_button.grid(row=2, column=1, sticky="e", padx=(14, 0))
        
        # Auto-adjust window size after all widgets are created
        self.after_idle(self._auto_adjust_window_size)

    def record_shortcut(self, entry: ttk.Entry, action_name: str, save_after_record: bool = True):
        """Record a hotkey and write it into the provided entry field."""
        self._unregister_all_hotkeys()
        dialog = ShortcutRecorderDialog(self, action_name)
        self.wait_window(dialog)
        if dialog.result:
            entry.delete(0, tk.END)
            entry.insert(0, dialog.result)
            if save_after_record:
                self.save_settings()
                return
        self._register_hotkeys()

    def _on_increment_scale_changed(self, value: str):
        """Keep the resize increment slider on whole-pixel values."""
        try:
            rounded_value = int(round(float(value)))
        except (TypeError, ValueError):
            return
        self.increment_var.set(rounded_value)

    def _on_increment_spinbox_changed(self):
        """Clamp manual resize increment edits to the supported range."""
        try:
            value = int(round(float(self.increment_var.get())))
        except (tk.TclError, ValueError):
            value = self.resize_increment
        clamped = min(150, max(5, value))
        self.increment_var.set(clamped)
        self._increment_scale_var.set(clamped)

    def _auto_adjust_window_size(self):
        """Automatically adjust window size to fit all widgets."""
        # Update the window to ensure all widgets are properly sized
        self.update_idletasks()
        
        # Get the required height for all widgets
        required_height = self.winfo_reqheight()
        
        # Add some padding for better appearance
        padding = 28
        new_height = required_height + padding
        
        # Ensure minimum height
        min_height = 580
        new_height = max(new_height, min_height)
        max_height = max(min_height, min(760, self.winfo_screenheight() - 96))
        new_height = min(new_height, max_height)
        
        # Get current width
        current_width = self.winfo_width()
        if current_width < 840:  # Ensure minimum width
            current_width = 840
        
        # Update window geometry
        self.geometry(f"{current_width}x{new_height}")
        
        logger.info(f"Auto-adjusted window size to {current_width}x{new_height}")

    def add_custom_action(self):
        """Add a new custom resize action."""
        dialog = CustomActionDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            percentage, hotkey = dialog.result
            self.tree.insert('', 'end', values=(percentage, hotkey))
            self._register_custom_hotkey(percentage, hotkey)
            self.save_settings()
            # Adjust window size after adding new action
            self.after_idle(self._auto_adjust_window_size)

    def remove_custom_action(self):
        """Remove the selected custom resize action."""
        selected_item = self.tree.selection()
        if selected_item:
            item = selected_item[0]
            values = self.tree.item(item, 'values')
            percentage, hotkey = values
            self._unregister_hotkey(hotkey)
            self.tree.delete(item)
            self.save_settings()
            # Adjust window size after removing action
            self.after_idle(self._auto_adjust_window_size)

    def _register_hotkeys(self):
        """Register all hotkeys."""
        self._unregister_all_hotkeys()

        # Register predefined hotkeys
        actions = {
            'resize_80': self.resize_to_80,
            'fullscreen': self.fullscreen,
            'center': self.center_window,
            'resize_60': self.resize_to_60,
            'expand_window': self.expand_window,
            'shrink_window': self.shrink_window
        }

        for key, action in actions.items():
            hotkey = self.shortcuts_entries[key].get()
            self._register_hotkey(hotkey, action)

        # Register custom hotkeys
        for item in self.tree.get_children():
            percentage, hotkey = self.tree.item(item, 'values')
            resize_action = self._create_resize_function(float(percentage))
            self._register_hotkey(hotkey, resize_action)

        # Register minimize sequence hotkeys
        self._register_hotkey('ctrl+shift+h', self._start_minimize_sequence)
        self._register_hotkey('ctrl+shift+m', self._complete_minimize_sequence)

    def _register_hotkey(self, hotkey: str, action: Callable):
        """Register a single hotkey with enhanced error handling."""
        if not hotkey.strip():
            logger.warning("Empty hotkey provided; skipping registration.")
            return
        
        # Unregister existing hotkey if it exists
        self._unregister_hotkey(hotkey)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                keyboard.add_hotkey(hotkey, action, suppress=False, timeout=1)
                self.hotkeys[hotkey] = action
                logger.info(f"Registered hotkey: {hotkey} (attempt {attempt + 1})")
                return
            except ValueError as e:
                logger.error(f"Failed to register hotkey '{hotkey}' (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.1)  # Brief delay before retry
                else:
                    logger.error(f"Failed to register hotkey '{hotkey}' after {max_retries} attempts")
            except Exception as e:
                logger.error(f"Unexpected error registering hotkey '{hotkey}': {e}")
                break

    def _register_custom_hotkey(self, percentage: str, hotkey: str):
        """Register a custom resize action hotkey."""
        resize_action = self._create_resize_function(float(percentage))
        self._register_hotkey(hotkey, resize_action)

    def _unregister_hotkey(self, hotkey: str):
        """Unregister a single hotkey with enhanced error handling."""
        if not hotkey.strip():
            return
        try:
            keyboard.remove_hotkey(hotkey)
            self.hotkeys.pop(hotkey, None)
            logger.info(f"Unregistered hotkey: {hotkey}")
        except (KeyError, ValueError):
            # Hotkey wasn't registered or already removed
            self.hotkeys.pop(hotkey, None)
        except Exception as e:
            logger.error(f"Error unregistering hotkey '{hotkey}': {e}")
            self.hotkeys.pop(hotkey, None)

    def _unregister_all_hotkeys(self):
        """Unregister all hotkeys."""
        for hotkey in list(self.hotkeys.keys()):
            self._unregister_hotkey(hotkey)

    def _start_hotkey_monitor(self):
        """Start the hotkey monitoring thread."""
        self.hotkey_monitor_running = True
        self.hotkey_monitor_thread = threading.Thread(target=self._hotkey_monitor_loop, daemon=True)
        self.hotkey_monitor_thread.start()
        logger.info("Hotkey monitor started.")

    def _stop_hotkey_monitor(self):
        """Stop the hotkey monitoring thread."""
        self.hotkey_monitor_running = False
        if self.hotkey_monitor_thread and self.hotkey_monitor_thread.is_alive():
            self.hotkey_monitor_thread.join(timeout=1)
        logger.info("Hotkey monitor stopped.")

    def _hotkey_monitor_loop(self):
        """Monitor hotkeys and re-register them if they stop working."""
        while self.hotkey_monitor_running:
            try:
                time.sleep(5)  # Check every 5 seconds
                if not self.hotkey_monitor_running:
                    break
                
                # Test if hotkeys are still working by checking keyboard state
                current_time = time.time()
                if current_time - self.last_hotkey_test_time > 30:  # Test every 30 seconds
                    self._test_hotkey_system()
                    self.last_hotkey_test_time = current_time
                
            except Exception as e:
                logger.error(f"Error in hotkey monitor loop: {e}")
                time.sleep(10)  # Wait longer on error

    def _test_hotkey_system(self):
        """Test if the hotkey system is still working."""
        try:
            # Check if keyboard module is still responsive
            if not hasattr(keyboard, '_listener') or not keyboard._listener:
                logger.warning("Keyboard listener appears to be inactive. Re-registering hotkeys.")
                self._recover_hotkeys()
                return
            
            # Check if we have registered hotkeys
            if not self.hotkeys:
                logger.warning("No hotkeys registered. Re-registering hotkeys.")
                self._recover_hotkeys()
                return
                
            # Try to get current pressed keys (this will fail if keyboard hook is broken)
            keyboard.is_pressed('ctrl')
            
            logger.debug("Hotkey system test passed.")
            self.hotkey_failure_count = 0
            
        except Exception as e:
            self.hotkey_failure_count += 1
            logger.warning(f"Hotkey system test failed (count: {self.hotkey_failure_count}): {e}")
            
            if self.hotkey_failure_count >= 3:
                logger.error("Multiple hotkey system failures detected. Attempting recovery.")
                self._recover_hotkeys()
                self.hotkey_failure_count = 0

    def _recover_hotkeys(self):
        """Recover hotkeys after system failure."""
        try:
            logger.info("Attempting to recover hotkey system...")
            
            # Clear all existing hotkeys
            try:
                keyboard.unhook_all()
            except:
                pass
            
            # Wait a moment for cleanup
            time.sleep(1)
            
            # Re-register all hotkeys
            self._register_hotkeys()
            
            logger.info("Hotkey system recovery completed.")
            
        except Exception as e:
            logger.error(f"Failed to recover hotkey system: {e}")
            # Try again in a few seconds
            threading.Timer(5.0, self._recover_hotkeys).start()

    def _create_resize_function(self, percentage: float) -> Callable:
        """Create a resize function for a given percentage."""
        def resize_function():
            hwnd = self._get_foreground_window()
            if hwnd:
                self._resize_window(hwnd, percentage / 100.0)
        return resize_function

    def _get_foreground_window(self) -> Optional[int]:
        """Get the handle of the foreground window."""
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            logger.warning("No foreground window found.")
            return None
        return hwnd

    def _get_monitor_info(self, hwnd: int) -> MonitorInfo:
        """Get the monitor information for the given window handle."""
        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        return win32api.GetMonitorInfo(monitor)

    def _resize_window(self, hwnd: int, scale: float):
        """Resize and reposition the window based on the scale."""
        monitor_info = self._get_monitor_info(hwnd)
        work_area = monitor_info['Work']
        width = int((work_area[2] - work_area[0]) * scale)
        height = int((work_area[3] - work_area[1]) * scale)
        left = work_area[0] + ((work_area[2] - work_area[0]) - width) // 2
        top = work_area[1] + ((work_area[3] - work_area[1]) - height) // 2

        win32gui.SetWindowPos(hwnd, None, left, top, width, height, win32con.SWP_NOZORDER)
        logger.info(f"Resized window {hwnd} to {width}x{height} at ({left}, {top})")

    def resize_to_80(self):
        """Resize the foreground window to 80% of the screen."""
        hwnd = self._get_foreground_window()
        if hwnd:
            self._resize_window(hwnd, 0.8)

    def resize_to_60(self):
        """Resize the foreground window to 60% of the screen."""
        hwnd = self._get_foreground_window()
        if hwnd:
            self._resize_window(hwnd, 0.6)

    def fullscreen(self):
        """Maximize the foreground window to full screen."""
        hwnd = self._get_foreground_window()
        if hwnd:
            self._resize_window(hwnd, 1.0)

    def center_window(self):
        """Center the foreground window without resizing."""
        hwnd = self._get_foreground_window()
        if hwnd:
            rect = win32gui.GetWindowRect(hwnd)
            window_width = rect[2] - rect[0]
            window_height = rect[3] - rect[1]
            monitor_info = self._get_monitor_info(hwnd)
            work_area = monitor_info['Work']
            left = work_area[0] + ((work_area[2] - work_area[0]) - window_width) // 2
            top = work_area[1] + ((work_area[3] - work_area[1]) - window_height) // 2
            win32gui.SetWindowPos(hwnd, None, left, top, window_width, window_height, win32con.SWP_NOZORDER)
            logger.info(f"Centered window {hwnd} at ({left}, {top})")

    def expand_window(self):
        """Expand the foreground window by the configured increment on all sides."""
        hwnd = self._get_foreground_window()
        if hwnd:
            self._adjust_window_size(hwnd, self.resize_increment)

    def shrink_window(self):
        """Shrink the foreground window by the configured increment on all sides."""
        hwnd = self._get_foreground_window()
        if hwnd:
            self._adjust_window_size(hwnd, -self.resize_increment)

    def _adjust_window_size(self, hwnd: int, increment: int):
        """Adjust the window size by the given increment on all sides."""
        rect = win32gui.GetWindowRect(hwnd)
        current_left, current_top, current_right, current_bottom = rect
        
        # Calculate new dimensions (expand/shrink by increment on all sides)
        new_left = current_left - increment
        new_top = current_top - increment
        new_width = (current_right - current_left) + (2 * increment)
        new_height = (current_bottom - current_top) + (2 * increment)
        
        # Get monitor info to ensure window stays within bounds
        monitor_info = self._get_monitor_info(hwnd)
        work_area = monitor_info['Work']
        
        # Ensure minimum window size (prevent windows from becoming too small)
        min_width, min_height = 100, 100
        if new_width < min_width:
            new_width = min_width
            new_left = current_left - (new_width - (current_right - current_left)) // 2
        if new_height < min_height:
            new_height = min_height
            new_top = current_top - (new_height - (current_bottom - current_top)) // 2
        
        # Ensure window doesn't go outside work area
        if new_left < work_area[0]:
            new_left = work_area[0]
        if new_top < work_area[1]:
            new_top = work_area[1]
        if new_left + new_width > work_area[2]:
            new_left = work_area[2] - new_width
        if new_top + new_height > work_area[3]:
            new_top = work_area[3] - new_height
        
        # Apply the new position and size
        win32gui.SetWindowPos(hwnd, None, new_left, new_top, new_width, new_height, win32con.SWP_NOZORDER)
        action = "Expanded" if increment > 0 else "Shrunk"
        logger.info(f"{action} window {hwnd} by {abs(increment)}px to {new_width}x{new_height} at ({new_left}, {new_top})")

    def minimize_to_tray(self):
        """Minimize the application window to the system tray."""
        self.withdraw()
        image = self._create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem('Restore', self.restore_window),
            pystray.MenuItem(lambda item: f'Hotkeys: {len(self.hotkeys)} active', None, enabled=False),
            pystray.MenuItem('Recover Hotkeys', self._recover_hotkeys),
            pystray.MenuItem('Exit', self.exit_app)
        )
        icon = pystray.Icon("WindowManagerApp", image, "Window Manager App", menu)
        self.icon = icon
        threading.Thread(target=icon.run, daemon=True).start()
        logger.info("Application minimized to tray.")

    def restore_window(self):
        """Restore the application window from the system tray."""
        if self.icon:
            self.icon.stop()
        self.deiconify()
        logger.info("Application window restored.")

    def exit_app(self):
        """Exit the application from the system tray."""
        if self.icon:
            self.icon.stop()
        self.on_exit()
        logger.info("Application exited from tray.")

    def _create_tray_icon_image(self) -> Image.Image:
        """Create an image for the system tray icon."""
        image = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(37, 99, 235, 255))
        draw.rounded_rectangle((14, 17, 50, 44), radius=4, outline=(255, 255, 255, 235), width=3)
        draw.line((14, 26, 50, 26), fill=(255, 255, 255, 200), width=2)
        draw.line((29, 26, 29, 44), fill=(255, 255, 255, 180), width=2)
        return image

    def on_window_minimize(self, event):
        """Handle window minimize event - automatically minimize to tray."""
        if event.widget == self:
            # Check if the window is being minimized (iconified)
            if self.state() == 'iconic':
                # Delay the tray minimization slightly to ensure the window state change completes
                self.after(100, self.minimize_to_tray)

    def on_exit(self):
        """Handle application exit."""
        self._stop_hotkey_monitor()
        self._unregister_all_hotkeys()
        try:
            keyboard.unhook_all()
        except:
            pass
        self.destroy()
        logger.info("Application exited.")

    def set_startup(self, enable: bool):
        """Set or unset the application to start with Windows."""
        registry_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "WindowManagerApp"
        if getattr(sys, 'frozen', False):
            exe_path = f'"{sys.executable}"'
        else:
            exe_path = f'"{os.path.abspath(__file__)}"'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path, 0, winreg.KEY_WRITE) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                logger.info("Set application to start with Windows.")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info("Removed application from Windows startup.")
                except FileNotFoundError:
                    pass

    def on_startup_checkbox(self):
        """Callback for the startup checkbox."""
        self.set_startup(self.startup_var.get())

    def save_settings(self):
        """Save the current settings to a JSON file."""
        self._on_increment_spinbox_changed()
        settings = {
            key: entry.get() for key, entry in self.shortcuts_entries.items()
        }
        settings['startup'] = self.startup_var.get()
        settings['resize_increment'] = int(round(self.increment_var.get()))
        settings['custom_actions'] = [
            {'percentage': percentage, 'hotkey': hotkey}
            for percentage, hotkey in (self.tree.item(item, 'values') for item in self.tree.get_children())
        ]

        # Update the resize increment value
        self.resize_increment = int(round(self.increment_var.get()))

        with open('settings.json', 'w') as f:
            json.dump(settings, f)
        logger.info("Settings saved to settings.json.")
        self._register_hotkeys()

    # Load settings from the settings.json file
    def _load_settings(self):
        """Load settings from a JSON file."""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
            logger.info("Settings loaded from settings.json.")
        except FileNotFoundError:
            settings = {}
            logger.warning("Settings file not found. Using default settings.")

        # Update hotkey names for special keys
        hotkey_replacements = {
            ',': 'comma',
            '.': 'period',
            '/': 'slash',
            '\\': 'backslash',
            ';': 'semicolon',
            "'": 'apostrophe',
            '-': 'minus',
            '=': 'equal',
            '`': 'grave',
            '[': 'left bracket',
            ']': 'right bracket',
            ' ': 'space'
        }

        for key, entry in self.shortcuts_entries.items():
            hotkey = settings.get(key, '')
            # Replace special symbols with their key names
            for symbol, name in hotkey_replacements.items():
                hotkey = hotkey.replace(symbol, name)
            entry.delete(0, tk.END)
            entry.insert(0, hotkey)

        self.startup_var.set(settings.get('startup', False))
        
        # Load resize increment setting
        resize_increment = int(round(float(settings.get('resize_increment', 10))))
        self.increment_var.set(resize_increment)
        self._increment_scale_var.set(resize_increment)
        self.resize_increment = resize_increment

        # Load custom actions
        for action in settings.get('custom_actions', []):
            percentage = action['percentage']
            hotkey = action['hotkey']
            # Replace special symbols with their key names
            for symbol, name in hotkey_replacements.items():
                hotkey = hotkey.replace(symbol, name)
            self.tree.insert('', 'end', values=(percentage, hotkey))

    def _start_minimize_sequence(self):
        """Start the minimize sequence when Ctrl+Shift+H is pressed."""
        self.minimize_sequence_started = True
        self.minimize_sequence_start_time = time.time()
        logger.info("Minimize sequence started.")

    def _complete_minimize_sequence(self):
        """Complete the minimize sequence when Ctrl+Shift+M is pressed."""
        if self.minimize_sequence_started:
            elapsed_time = time.time() - self.minimize_sequence_start_time
            if elapsed_time <= 2:
                self._minimize_all_windows_on_current_desktop()
                logger.info("Minimize sequence completed.")
            else:
                logger.info("Minimize sequence timed out.")
        else:
            logger.info("Minimize sequence not started.")
        self.minimize_sequence_started = False

    def _minimize_all_windows_on_current_desktop(self):
        """Minimize all windows on the current desktop."""
        monitor = get_current_monitor()
        monitor_info = win32api.GetMonitorInfo(monitor)
        monitor_rect = RECT(*monitor_info['Monitor'])

        def enum_handler(hwnd: int, _):
            if not win32gui.IsWindowVisible(hwnd) or hwnd == self.hwnd:
                return
            rect = win32gui.GetWindowRect(hwnd)
            window_rect = RECT(*rect)
            if rects_intersect(window_rect, monitor_rect):
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

        win32gui.EnumWindows(enum_handler, None)
        logger.info("Minimized all windows on current desktop.")

class ShortcutRecorderDialog(tk.Toplevel):
    """Dialog that records the next keyboard shortcut entered by the user."""

    MODIFIER_KEYSYMS = {
        "Shift_L",
        "Shift_R",
        "Control_L",
        "Control_R",
        "Alt_L",
        "Alt_R",
        "Meta_L",
        "Meta_R",
        "Win_L",
        "Win_R",
    }
    KEY_NAME_MAP = {
        "Control_L": "ctrl",
        "Control_R": "ctrl",
        "Shift_L": "shift",
        "Shift_R": "shift",
        "Alt_L": "alt",
        "Alt_R": "alt",
        "Meta_L": "windows",
        "Meta_R": "windows",
        "Win_L": "windows",
        "Win_R": "windows",
        "Return": "enter",
        "Escape": "esc",
        "BackSpace": "backspace",
        "Tab": "tab",
        "space": "space",
        "Delete": "delete",
        "Insert": "insert",
        "Home": "home",
        "End": "end",
        "Prior": "page up",
        "Next": "page down",
        "Up": "up",
        "Down": "down",
        "Left": "left",
        "Right": "right",
        "minus": "minus",
        "equal": "equal",
        "comma": "comma",
        "period": "period",
        "slash": "slash",
        "backslash": "backslash",
        "semicolon": "semicolon",
        "apostrophe": "apostrophe",
        "grave": "grave",
        "bracketleft": "left bracket",
        "bracketright": "right bracket",
    }

    def __init__(self, parent: WindowManagerApp, action_name: str):
        super().__init__(parent)
        self.parent = parent
        self.result: Optional[str] = None
        self.title("Record Shortcut")
        self.configure(bg=parent.palette["bg"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self._create_widgets(action_name)
        self.bind("<KeyPress>", self._on_key_press)
        self.after_idle(lambda: self._center_on_parent(parent))
        self.after(100, self.focus_force)

    def _create_widgets(self, action_name: str):
        """Create recorder dialog controls."""
        container = ttk.Frame(self, style="Card.TFrame", padding=(22, 20, 22, 18))
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.columnconfigure(0, weight=1)

        ttk.Label(container, text=f"Record {action_name}", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text="Press the shortcut now. Use Esc to cancel.",
            style="SectionHint.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        self.preview_label = ttk.Label(container, text="Waiting for keys...", style="Pill.TLabel")
        self.preview_label.grid(row=2, column=0, sticky="ew", pady=(0, 18))

        cancel_button = ttk.Button(container, text="Cancel", command=self.on_cancel, style="Secondary.TButton")
        cancel_button.grid(row=3, column=0, sticky="e")

    def _on_key_press(self, event: tk.Event):
        """Convert the pressed combination into keyboard module syntax."""
        if event.keysym == "Escape":
            self.on_cancel()
            return "break"

        hotkey = self._format_event_hotkey(event)
        if hotkey:
            self.result = hotkey
            self.preview_label.configure(text=hotkey)
            self.after(120, self.destroy)
        return "break"

    def _format_event_hotkey(self, event: tk.Event) -> str:
        """Format a Tk key event as a keyboard-library hotkey string."""
        key = self._normalize_key_name(event.keysym)
        if not key:
            return ""

        modifiers = []
        if event.state & 0x0004:
            modifiers.append("ctrl")
        if event.state & 0x0001:
            modifiers.append("shift")
        if event.state & 0x20000:
            modifiers.append("alt")

        if key in {"ctrl", "shift", "alt", "windows"}:
            return ""
        return "+".join([*modifiers, key])

    def _normalize_key_name(self, keysym: str) -> str:
        """Normalize Tk key names to names accepted by the keyboard package."""
        if keysym in self.KEY_NAME_MAP:
            return self.KEY_NAME_MAP[keysym]
        if len(keysym) == 1:
            return keysym.lower()
        if keysym.startswith("F") and keysym[1:].isdigit():
            return keysym.lower()
        if keysym in self.MODIFIER_KEYSYMS:
            return ""
        return keysym.replace("_", " ").lower()

    def _center_on_parent(self, parent: tk.Tk):
        """Center the dialog over the parent window."""
        self.update_idletasks()
        parent.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def on_cancel(self):
        """Cancel shortcut recording."""
        self.result = None
        self.destroy()

class CustomActionDialog(tk.Toplevel):
    """Dialog for adding custom resize actions."""

    def __init__(self, parent: WindowManagerApp):
        super().__init__(parent)
        self.parent = parent
        self.title("Add Custom Action")
        self.configure(bg=parent.palette["bg"])
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str]] = None
        self._create_widgets()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.after_idle(lambda: self._center_on_parent(parent))

    def _create_widgets(self):
        """Create widgets for the dialog."""
        container = ttk.Frame(self, style="Card.TFrame", padding=(22, 20, 22, 18))
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text="Add Custom Action", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(container, text="Define a resize percentage and the hotkey that triggers it.", style="SectionHint.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 16))

        ttk.Label(container, text="Resize Percentage (e.g., 75):", style="Field.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=6)
        self.percentage_entry = ttk.Entry(container, width=24)
        self.percentage_entry.grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(container, text="Hotkey (e.g., ctrl+alt+5):", style="Field.TLabel").grid(row=3, column=0, sticky="w", padx=(0, 16), pady=6)
        self.hotkey_entry = ttk.Entry(container, width=24)
        self.hotkey_entry.grid(row=3, column=1, sticky="ew", pady=6)
        record_button = ttk.Button(
            container,
            text="Record",
            style="Compact.TButton",
            command=lambda: self.parent.record_shortcut(self.hotkey_entry, "Custom Action", save_after_record=False),
        )
        record_button.grid(row=3, column=2, sticky="e", padx=(8, 0), pady=6)

        btn_frame = ttk.Frame(container, style="Toolbar.TFrame")
        btn_frame.grid(row=4, column=0, columnspan=3, sticky="e", pady=(18, 0))

        ok_button = ttk.Button(btn_frame, text="OK", command=self.on_ok)
        ok_button.configure(style="Primary.TButton")
        ok_button.pack(side='left', padx=(0, 8))

        cancel_button = ttk.Button(btn_frame, text="Cancel", command=self.on_cancel)
        cancel_button.configure(style="Secondary.TButton")
        cancel_button.pack(side='left')

        self.percentage_entry.focus_set()

    def _center_on_parent(self, parent: tk.Tk):
        """Center the dialog over the main window."""
        self.update_idletasks()
        parent.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - width) // 2
        y = parent_y + (parent_height - height) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def on_ok(self):
        """Handle the OK button press."""
        percentage = self.percentage_entry.get()
        hotkey = self.hotkey_entry.get()
        if not percentage.isdigit() or not hotkey.strip():
            messagebox.showerror("Error", "Please enter a valid percentage and hotkey.")
            return
        self.result = (percentage, hotkey)
        self.destroy()
        logger.info(f"Added custom action: {percentage}% with hotkey {hotkey}")

    def on_cancel(self):
        """Handle the Cancel button press."""
        self.result = None
        self.destroy()
        logger.info("Custom action dialog canceled.")

if __name__ == "__main__":
    app = WindowManagerApp()
    app.mainloop()
