# Window Manager App

A lightweight tray utility for Windows that lets you resize, center, and manage application windows using global hotkeys.

## Features

- **Smart Resizing** - Snap windows to 80%, 60%, or any custom percentage of the screen
- **Center Window** - Center any window on screen without changing its size
- **Fullscreen** - Expand any window to fill the entire work area
- **Expand / Shrink** - Grow or shrink windows by a configurable pixel increment on all sides
- **Custom Hotkeys** - Assign your own keyboard shortcuts to every action
- **Custom Resize Actions** - Define additional resize percentages with their own hotkeys
- **Minimize All** - Minimize every window on the current desktop using a two-key sequence
- **System Tray** - Runs silently in the background; restore from the tray at any time
- **Start with Windows** - Optional auto-launch on login
- **Hotkey Recovery** - Automatically detects and recovers broken hotkey registrations

## Screenshots

![Main window](https://i.imgur.com/KYUOG7d.png)

![Hotkey recording](https://i.imgur.com/BehTtAP.png)

![Custom actions](https://i.imgur.com/JvAenjx.png)

![System tray](https://i.imgur.com/PGxBUZt.png)

## Getting Started

**Requirements**

- Windows
- Python 3.7+ (if running from source)

**Run from source**

```bash
pip install -r requirements.txt
python main.py
```

**Run the executable**

Download the `.exe` from the Releases page and run it directly, no Python required.

## Usage

### Opening the app

Find the icon in the system tray, right-click it, and select **Restore** to open the main window.

### Built-in actions

| Action | Description |
|---|---|
| Resize to 80% | Resize the active window to 80% of the work area |
| Resize to 60% | Resize the active window to 60% of the work area |
| Fullscreen | Expand the active window to fill the work area |
| Center Window | Center the active window without resizing it |
| Expand Window | Grow the active window by the resize increment on all sides |
| Shrink Window | Shrink the active window by the resize increment on all sides |

### Resize increment

The **Resize Increment** setting (5-150 px) controls how many pixels each Expand / Shrink action adds or removes per edge. Adjust it with the spinbox or slider in the Keyboard Shortcuts panel.

### Custom resize actions

Click **Add** to define a resize percentage (e.g. 73) and assign a hotkey to it. The action appears in the Custom Resize Actions table and is registered immediately. Select a row and click **Remove** to delete it.

### Minimize all windows

Press `Ctrl + Shift + H` followed by `Ctrl + Shift + M` within 2 seconds to minimize every window on the current desktop.

### Recording hotkeys

Click **Record** next to any action, then press the desired key combination. The shortcut is saved automatically. Click **Save Hotkeys** to apply any manual edits made directly in the text fields.

## Settings

All settings are persisted to `settings.json` in the application directory. The file stores hotkey bindings, custom resize actions, the resize increment, and the startup preference. It can be edited manually if needed.

## Troubleshooting

**Hotkeys not responding**
- Right-click the tray icon and select **Recover Hotkeys**
- The app monitors hotkey health in the background and will attempt automatic recovery
- The tray tooltip shows how many hotkeys are currently active

**App fails to start**
- Ensure all Python dependencies are installed: `pip install -r requirements.txt`
- Check `window_manager.log` for error details
- Try running as administrator if hotkey registration fails

**Window does not resize**
- Some applications (fullscreen games, UWP apps) block external window management
- Test on a standard desktop window to verify the hotkeys are working

## Built With

- [Python](https://www.python.org/)
- [tkinter](https://docs.python.org/3/library/tkinter.html) - GUI
- [keyboard](https://github.com/boppreh/keyboard) - Global hotkeys
- [pywin32](https://github.com/mhammond/pywin32) - Windows API access
- [pystray](https://github.com/moses-palmer/pystray) - System tray integration
- [Pillow](https://python-pillow.org/) - Tray icon rendering
