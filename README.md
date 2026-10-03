# Window Manager App

A lightweight native Windows tray utility written in Rust. It lets you resize,
center, and manage application windows with global hotkeys.

## Features

- Resize the active window to 80%, 60%, fullscreen work area, or a custom percentage
- Center the active window without resizing it
- Expand or shrink the active window by a configurable pixel increment
- Assign and record global hotkeys for every built-in action
- Add custom resize percentages with their own hotkeys
- Minimize all visible windows on the current monitor with `Ctrl + Shift + H`,
  then `Ctrl + Shift + M` within 2 seconds
- Dim the monitor under the cursor with `Ctrl + Shift + D`, then
  `Ctrl + Shift + M` within 2 seconds; click that monitor to remove the dimming
- Optionally show a clock in any corner of the dimmed monitor, with a
  configurable font color
- Minimize to the system tray, restore from the tray menu, and recover hotkeys
- Optional Start with Windows registry integration
- Compatible with the previous `settings.json` format

## Build

```powershell
cargo build --release
```

The compiled executable is written to:

```text
target\release\windowmanagerapp.exe
```

## Usage

Run `windowmanagerapp.exe`. The app starts in the system tray. Right-click the
tray icon and choose **Restore** to open the configuration window.

Settings are saved to `settings.json`. The app first looks next to the
executable, then falls back to the current directory for compatibility with the
old Python version.
