
# Windows Manager App
The Windows Manager App is a Python application for managing and manipulating windows' sizes and positions in Windows. This is done using configured keyboard shortcuts.

I was inspired to make this app thanks to the many apps of this type for macOS, which I also use and have used myself. It makes windows management a lot simpler and faster and for people who are pedantic about that, it gives them the ability to precisely center a window or set a specific size. So I decided to make something like this for Windows, adding the shortcuts I use most often.

The application is lightweight and runs in the background, residing in the system tray.

## Features

-   **Resize windows**: Quickly resize the active window to predefined percentages (e.g., 80%, 60%) or custom sizes.
-   **Center windows**: Center the active window on the screen without changing its size.
-   **Fullscreen**: Maximize the active window to fill the entire screen.
-   **Custom hotkeys**: Assign your preferred keyboard shortcuts to different actions.
-   **Custom resize actions**: Add custom resize percentages with associated hotkeys.
-   **Minimize all windows**: Minimize all windows on the current desktop with a specific hotkey sequence.
-   **System tray integration**: Minimize the app to the system tray to keep it running without cluttering the taskbar.
-   **Start with Windows**: Option to launch the app automatically when Windows starts.
-   **Start minimized**: The app starts minimized to the system tray by default.

## Installation

### Prerequisites

-   **Windows OS**: This application is designed for Windows operating systems.
-   **Python 3.7 or higher**: Ensure you have Python installed. You can download it from the [official website](https://www.python.org/downloads/).

## Usage

### Install Dependencies

Open a command prompt and navigate to the project directory. Install the required Python packages using `pip`:

```bash
pip install -r requirements.txt
```

### Running the Application

To start the application, run the following command in the project directory:

`python main.py` 

The application will start minimized to the system tray.

### Accessing the Main Window

To open the main window of the application:

1.  Locate the app icon in the system tray (it displays "WM").
2.  Right-click the icon and select **Restore**.

### Configuring Hotkeys and Actions

1.  **Keyboard Shortcuts**: In the main window, you can set hotkeys for predefined actions:
    
    -   **Resize to 80%**
    -   **Fullscreen**
    -   **Center Window**
    -   **Resize to 60%**
    
    Enter your desired hotkeys in the corresponding fields.
    
2.  **Custom Resize Actions**:
    
    -   Click the **Add** button to create a new custom action.
    -   Enter the resize percentage (e.g., 75) and assign a hotkey.
    -   Click **OK** to save the custom action.
3.  **Save Hotkeys**:
    
    -   After configuring your hotkeys, click the **Save Hotkeys** button to apply the changes.

### Minimizing to System Tray

-   To minimize the application to the system tray, click the **Minimize to Tray** button in the main window.
-   The application will continue running in the background, listening for hotkeys.

### Starting with Windows

-   To launch the application automatically when Windows starts, check the **Start with Windows** option in the main window.
-   Uncheck the option to disable automatic startup.

### Minimizing All Windows on Current Desktop

-   Press `Ctrl + Shift + H` to initiate the minimize sequence.
-   Within 2 seconds, press `Ctrl + Shift + M` to minimize all windows on the current desktop.

## Configuration

The application saves settings to a `settings.json` file located in the project directory. This file stores your hotkey configurations and startup preferences.

### Editing `settings.json` Manually

You can also edit `settings.json` manually if needed. Ensure the JSON structure is maintained to prevent errors.
