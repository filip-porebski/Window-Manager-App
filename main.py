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
from PIL import Image, ImageDraw
import pystray

logging.basicConfig(level=logging.INFO)
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
        self.title("Window Manager App")
        self.geometry("400x550")
        self.hwnd = self.winfo_id()

    def _initialize_state_variables(self):
        """Initialize instance variables and state tracking."""
        self.icon: Optional[Any] = None
        self.hotkeys: Dict[str, Callable] = {}
        self.startup_var = tk.BooleanVar()
        self.minimize_sequence_started = False
        self.minimize_sequence_start_time = 0

    def _setup_ui(self):
        """Set up UI components and load settings."""
        self._create_widgets()
        self._load_settings()
        self._register_hotkeys()

    def _configure_window_behavior(self):
        """Configure window-level event handlers."""
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _start_minimized(self):
        """Start application minimized to system tray."""
        self.withdraw()
        self.minimize_to_tray()

    def _create_widgets(self):
        """Create GUI widgets."""
        # Keyboard Shortcuts Section
        shortcut_frame = ttk.LabelFrame(self, text="Keyboard Shortcuts")
        shortcut_frame.pack(padx=10, pady=10, fill="x")

        self.shortcuts_entries = {}
        shortcuts = [("Resize to 80%", "resize_80"), ("Fullscreen", "fullscreen"),
                     ("Center Window", "center"), ("Resize to 60%", "resize_60")]

        for idx, (label_text, key) in enumerate(shortcuts):
            ttk.Label(shortcut_frame, text=f"{label_text}:").grid(row=idx, column=0, sticky="w")
            entry = ttk.Entry(shortcut_frame)
            entry.grid(row=idx, column=1)
            self.shortcuts_entries[key] = entry

        # Save Button
        self.save_button = ttk.Button(shortcut_frame, text="Save Hotkeys", command=self.save_settings)
        self.save_button.grid(row=len(shortcuts), column=0, columnspan=2, pady=5)

        # Custom Resize Actions Section
        custom_frame = ttk.LabelFrame(self, text="Custom Resize Actions")
        custom_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Treeview to display custom actions
        columns = ('Percentage', 'Hotkey')
        self.tree = ttk.Treeview(custom_frame, columns=columns, show='headings')
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill='both', expand=True)

        # Buttons to add and remove custom actions
        btn_frame = ttk.Frame(custom_frame)
        btn_frame.pack(fill='x')

        self.add_button = ttk.Button(btn_frame, text="Add", command=self.add_custom_action)
        self.add_button.pack(side='left', padx=5, pady=5)

        self.remove_button = ttk.Button(btn_frame, text="Remove", command=self.remove_custom_action)
        self.remove_button.pack(side='left', padx=5, pady=5)

        # Start with Windows Checkbox
        self.startup_check = ttk.Checkbutton(self, text="Start with Windows", variable=self.startup_var,
                                             command=self.on_startup_checkbox)
        self.startup_check.pack(pady=5)

        # Minimize to Tray Button
        self.minimize_button = ttk.Button(self, text="Minimize to Tray", command=self.minimize_to_tray)
        self.minimize_button.pack(pady=5)

    def add_custom_action(self):
        """Add a new custom resize action."""
        dialog = CustomActionDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            percentage, hotkey = dialog.result
            self.tree.insert('', 'end', values=(percentage, hotkey))
            self._register_custom_hotkey(percentage, hotkey)
            self.save_settings()

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

    def _register_hotkeys(self):
        """Register all hotkeys."""
        self._unregister_all_hotkeys()

        # Register predefined hotkeys
        actions = {
            'resize_80': self.resize_to_80,
            'fullscreen': self.fullscreen,
            'center': self.center_window,
            'resize_60': self.resize_to_60
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
        """Register a single hotkey."""
        if not hotkey.strip():
            logger.warning("Empty hotkey provided; skipping registration.")
            return
        try:
            keyboard.add_hotkey(hotkey, action)
            self.hotkeys[hotkey] = action
            logger.info(f"Registered hotkey: {hotkey}")
        except ValueError as e:
            messagebox.showerror("Error", f"Failed to register hotkey '{hotkey}': {e}")
            logger.error(f"Failed to register hotkey '{hotkey}': {e}")

    def _register_custom_hotkey(self, percentage: str, hotkey: str):
        """Register a custom resize action hotkey."""
        resize_action = self._create_resize_function(float(percentage))
        self._register_hotkey(hotkey, resize_action)

    def _unregister_hotkey(self, hotkey: str):
        """Unregister a single hotkey."""
        try:
            keyboard.remove_hotkey(hotkey)
            self.hotkeys.pop(hotkey, None)
            logger.info(f"Unregistered hotkey: {hotkey}")
        except KeyError:
            pass

    def _unregister_all_hotkeys(self):
        """Unregister all hotkeys."""
        for hotkey in list(self.hotkeys.keys()):
            self._unregister_hotkey(hotkey)

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

    def minimize_to_tray(self):
        """Minimize the application window to the system tray."""
        self.withdraw()
        image = self._create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem('Restore', self.restore_window),
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
        image = Image.new('RGB', (64, 64), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 64, 64), fill=(255, 255, 255))
        draw.text((10, 20), 'WM', fill=(0, 0, 0))
        return image

    def on_exit(self):
        """Handle application exit."""
        self._unregister_all_hotkeys()
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
        settings = {
            key: entry.get() for key, entry in self.shortcuts_entries.items()
        }
        settings['startup'] = self.startup_var.get()
        settings['custom_actions'] = [
            {'percentage': percentage, 'hotkey': hotkey}
            for percentage, hotkey in (self.tree.item(item, 'values') for item in self.tree.get_children())
        ]

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

class CustomActionDialog(tk.Toplevel):
    """Dialog for adding custom resize actions."""

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.title("Add Custom Action")
        self.result: Optional[Tuple[str, str]] = None
        self._create_widgets()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

    def _create_widgets(self):
        """Create widgets for the dialog."""
        ttk.Label(self, text="Resize Percentage (e.g., 75):").grid(row=0, column=0, padx=10, pady=10)
        self.percentage_entry = ttk.Entry(self)
        self.percentage_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(self, text="Hotkey (e.g., ctrl+alt+5):").grid(row=1, column=0, padx=10, pady=10)
        self.hotkey_entry = ttk.Entry(self)
        self.hotkey_entry.grid(row=1, column=1, padx=10, pady=10)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2)

        ok_button = ttk.Button(btn_frame, text="OK", command=self.on_ok)
        ok_button.pack(side='left', padx=5, pady=5)

        cancel_button = ttk.Button(btn_frame, text="Cancel", command=self.on_cancel)
        cancel_button.pack(side='left', padx=5, pady=5)

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
