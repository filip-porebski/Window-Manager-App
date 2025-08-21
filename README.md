
# 🪟 Windows Manager App

*Because I want to manage windows in Windows the way I like.*

This lightweight app lives quietly in your system tray, waiting to make your windows behave exactly how you want them to.

## ✨ What does it do

-   **🎯 Smart Resizing**: Snap windows to 80%, 60% or any custom percentage
-   **📍 Perfect Centering**: Center any window without changing its size
-   **🖥️ Instant Fullscreen**: Make any window take over your entire screen
-   **⚡ Expand/Shrink**: Grow or shrink windows pixel by pixel with configurable increments
-   **🎮 Custom Hotkeys**: Set up your own keyboard shortcuts
-   **🔧 Custom Actions**: Add as many resize percentages as you want
-   **💥 Nuclear Option**: Minimize ALL windows on your current desktop (for when you need a clean slate)
-   **🥷 Stealth Mode**: Runs silently in the system tray
-   **🚀 Auto-Start**: Launches with Windows so it's always ready
-   **🛡️ Self-Healing**: Automatically recovers if hotkeys stop working

## 📸 Screenshots

![alt text](https://i.imgur.com/KYUOG7d.png)

![alt text](https://i.imgur.com/BehTtAP.png)

![alt text](https://i.imgur.com/JvAenjx.png)

![alt text](https://i.imgur.com/PGxBUZt.png)

## 🚀 Getting Started

### What You Need

-   **Windows**
-   **Python 3.7+** if you're running from source ([grab it here](https://www.python.org/downloads/))
-   Or just use the `.exe` from Releases

### Quick Setup

**Option 1: The Python way**
```bash
# Clone or download this repo
# Navigate to the folder
pip install -r requirements.txt
python main.py
```

**Option 2**
- Grab the `.exe` from releases
- Double-click it
- Profit! 💰


## 🎮 How to use

### Finding the App

Look for the "WM" icon in your system tray. Right-click it and hit **Restore** to bring up the main window.

### Setting up your hotkeys

The main window has everything you need:

**Built-in Actions:**
- **Resize to 80%**
- **Resize to 60%**
- **Fullscreen**
- **Center Window**
- **Expand Window**
- **Shrink Window**

**Pro Tips:**
- Set your **Resize Increment** (5-150px) to control how much expand/shrink moves change your windows
- Use the spinbox to dial in the perfect increment for your workflow

**Custom Actions:**
- Hit **Add** to create your own resize percentages
- Want 73% window size? You got it!
- Assign any hotkey combo you want

**The Nuclear Option:**
- `Ctrl + Shift + H` followed by `Ctrl + Shift + M` (within 2 seconds)
- Minimizes ALL windows on your current desktop

### Going Stealth

- Click **Minimize to Tray** to hide the window
- Check **Start with Windows** if you want it to launch automatically
- The app keeps working in the background

## 🔧 Seetings

All your settings get saved to `settings.json` in the app directory. It's got your hotkeys, custom actions, resize increment and startup preferences.

**What's in there:**
- Your hotkey bindings
- Custom resize actions and their hotkeys
- Resize increment setting (how many pixels expand/shrink moves)
- Whether to start with Windows

You can edit `settings.json` manually if you want.

## 🛠️ Troubleshooting

**Hotkeys stopped working?**
- Right-click the tray icon and hit "Recover Hotkeys"
- The app has self-healing powers and usually fixes itself
- Check the tray icon - it shows how many hotkeys are active

**App won't start?**
- Make sure you have all the Python dependencies installed
- Check `window_manager.log` for any error messages
- Try running as administrator if you're having permission issues

**Window won't resize properly?**
- Some apps (like fullscreen games) don't play nice with window management
- Try it on a regular window first to make sure everything's working



This thing is built with:
- **Python**
- **tkinter** for the GUI
- **keyboard** library for global hotkeys
- **pywin32** for Windows API
- **pystray** for system tray integration
- **Pillow** for the tray icon

---
