#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::OsStr;
use std::fs;
use std::mem::{size_of, zeroed};
use std::os::windows::ffi::OsStrExt;
use std::path::PathBuf;
use std::ptr::{null, null_mut};
use std::time::{Duration, Instant};
use windows_sys::core::BOOL;
use windows_sys::Win32::Foundation::{HINSTANCE, HWND, LPARAM, LRESULT, POINT, RECT, WPARAM};
use windows_sys::Win32::Graphics::Gdi::{
    BeginPaint, CreateFontW, CreateSolidBrush, DeleteObject, EndPaint, FillRect, GetMonitorInfoW,
    GetSysColor, MonitorFromPoint, MonitorFromWindow, SetBkColor, SetBkMode, SetTextColor,
    CLIP_DEFAULT_PRECIS, COLOR_BTNFACE, COLOR_BTNTEXT, COLOR_HIGHLIGHT, COLOR_HIGHLIGHTTEXT,
    COLOR_WINDOW, COLOR_WINDOWTEXT, DEFAULT_CHARSET, DEFAULT_PITCH, DEFAULT_QUALITY, FF_DONTCARE,
    FW_NORMAL, HBRUSH, HFONT, HMONITOR, MONITORINFO, MONITOR_DEFAULTTONEAREST,
    MONITOR_DEFAULTTONULL, OUT_DEFAULT_PRECIS, PAINTSTRUCT, TRANSPARENT,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;
use windows_sys::Win32::System::Registry::{
    RegCloseKey, RegDeleteValueW, RegOpenKeyExW, RegSetValueExW, HKEY, HKEY_CURRENT_USER,
    KEY_WRITE, REG_SZ,
};
use windows_sys::Win32::UI::Controls::{
    InitCommonControlsEx, BST_CHECKED, BST_UNCHECKED, ICC_BAR_CLASSES, INITCOMMONCONTROLSEX,
    TBM_SETPOS, TBM_SETRANGE, TBS_AUTOTICKS,
};
use windows_sys::Win32::UI::Input::KeyboardAndMouse::*;
use windows_sys::Win32::UI::Shell::{
    Shell_NotifyIconW, NIF_ICON, NIF_MESSAGE, NIF_TIP, NIM_ADD, NIM_DELETE, NIM_MODIFY,
    NOTIFYICONDATAW,
};
use windows_sys::Win32::UI::WindowsAndMessaging::*;

const APP_NAME: &str = "WindowManagerApp";
const APP_VERSION: &str = "v1.2.1";

const WINDOW_TITLE: &str = "Window Manager";
const CLIENT_WIDTH: i32 = 771;
const CLIENT_HEIGHT: i32 = 395;
const STATUS_HEIGHT: i32 = 20;
const STATIC_RIGHT: u32 = 0x0002;
const STATIC_SUNKEN: u32 = 0x1000;
const SHELL_DESKTOP_CLASS: &str = "Progman";
const SHELL_WORKER_CLASS: &str = "WorkerW";
const SHELL_PRIMARY_TASKBAR_CLASS: &str = "Shell_TrayWnd";
const SHELL_SECONDARY_TASKBAR_CLASS: &str = "Shell_SecondaryTrayWnd";
const APP_ICON_ID: usize = 1;
const WM_TRAYICON: u32 = WM_USER + 1;
const TRAY_ID: u32 = 1;
const TBM_GETPOS_LOCAL: u32 = 1024;

const ID_EDIT_RESIZE_80: i32 = 1001;
const ID_EDIT_FULLSCREEN: i32 = 1002;
const ID_EDIT_CENTER: i32 = 1003;
const ID_EDIT_RESIZE_60: i32 = 1004;
const ID_EDIT_EXPAND: i32 = 1005;
const ID_EDIT_SHRINK: i32 = 1006;
const ID_RECORD_RESIZE_80: i32 = 1101;
const ID_RECORD_FULLSCREEN: i32 = 1102;
const ID_RECORD_CENTER: i32 = 1103;
const ID_RECORD_RESIZE_60: i32 = 1104;
const ID_RECORD_EXPAND: i32 = 1105;
const ID_RECORD_SHRINK: i32 = 1106;
const ID_SAVE: i32 = 1201;
const ID_INCREMENT_EDIT: i32 = 1202;
const ID_INCREMENT_TRACK: i32 = 1203;
const ID_CUSTOM_LIST: i32 = 1301;
const ID_CUSTOM_PERCENT: i32 = 1302;
const ID_CUSTOM_HOTKEY: i32 = 1303;
const ID_CUSTOM_RECORD: i32 = 1304;
const ID_CUSTOM_ADD: i32 = 1305;
const ID_CUSTOM_REMOVE: i32 = 1306;
const ID_STARTUP: i32 = 1401;
const ID_MINIMIZE: i32 = 1402;
const ID_TRAY_RESTORE: i32 = 4001;
const ID_TRAY_RECOVER: i32 = 4002;
const ID_TRAY_EXIT: i32 = 4003;

const FIRST_HOTKEY_ID: i32 = 5000;

static mut APP_PTR: *mut App = null_mut();

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
struct CustomAction {
    percentage: String,
    hotkey: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct Settings {
    resize_80: String,
    fullscreen: String,
    center: String,
    resize_60: String,
    expand_window: String,
    shrink_window: String,
    startup: bool,
    resize_increment: i32,
    custom_actions: Vec<CustomAction>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            resize_80: "ctrl+shift+comma".to_string(),
            fullscreen: "ctrl+shift+slash".to_string(),
            center: "ctrl+shift+period".to_string(),
            resize_60: String::new(),
            expand_window: "ctrl+shift+up".to_string(),
            shrink_window: "ctrl+shift+down".to_string(),
            startup: false,
            resize_increment: 10,
            custom_actions: Vec::new(),
        }
    }
}

#[derive(Clone)]
enum HotkeyAction {
    Resize(f64),
    Center,
    Expand,
    Shrink,
    MinimizeStart,
    MinimizeComplete,
}

#[derive(Clone, Copy)]
enum BuiltInKey {
    Resize80,
    Fullscreen,
    Center,
    Resize60,
    Expand,
    Shrink,
}

#[derive(Clone, Copy)]
enum RecordingTarget {
    BuiltIn(BuiltInKey),
    CustomHotkey,
}

#[derive(Default)]
struct Controls {
    resize_80: HWND,
    fullscreen: HWND,
    center: HWND,
    resize_60: HWND,
    expand: HWND,
    shrink: HWND,
    increment_edit: HWND,
    increment_track: HWND,
    startup_check: HWND,
    custom_list: HWND,
    custom_percent: HWND,
    custom_hotkey: HWND,
    status: HWND,
}

struct App {
    hinstance: HINSTANCE,
    hwnd: HWND,
    controls: Controls,
    settings: Settings,
    hotkey_actions: HashMap<i32, HotkeyAction>,
    next_hotkey_id: i32,
    recording: Option<RecordingTarget>,
    minimize_started: Option<Instant>,
    tray_added: bool,
    bg_brush: HBRUSH,
    white_brush: HBRUSH,
    highlight_brush: HBRUSH,
    font_normal: HFONT,
    font_small: HFONT,
    font_bold: HFONT,
    font_mono: HFONT,
}

impl App {
    fn new() -> Self {
        unsafe {
            let hinstance = GetModuleHandleW(null());
            Self {
                hinstance,
                hwnd: 0 as HWND,
                controls: Controls::default(),
                settings: Settings::default(),
                hotkey_actions: HashMap::new(),
                next_hotkey_id: FIRST_HOTKEY_ID,
                recording: None,
                minimize_started: None,
                tray_added: false,
                bg_brush: CreateSolidBrush(sys_color(COLOR_BTNFACE)),
                white_brush: CreateSolidBrush(sys_color(COLOR_WINDOW)),
                highlight_brush: CreateSolidBrush(sys_color(COLOR_HIGHLIGHT)),
                font_normal: create_font(11, FW_NORMAL as i32),
                font_small: create_font(10, FW_NORMAL as i32),
                font_bold: create_font(11, 700),
                font_mono: create_font_face(11, FW_NORMAL as i32, "Fixedsys"),
            }
        }
    }

    unsafe fn run(&mut self) {
        let mut common = INITCOMMONCONTROLSEX {
            dwSize: size_of::<INITCOMMONCONTROLSEX>() as u32,
            dwICC: ICC_BAR_CLASSES,
        };
        InitCommonControlsEx(&mut common);

        let class_name = wide("WindowManagerAppRust");
        let wc = WNDCLASSW {
            style: CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc: Some(window_proc),
            hInstance: self.hinstance,
            hCursor: LoadCursorW(0 as _, IDC_ARROW),
            hIcon: load_app_icon(self.hinstance),
            hbrBackground: self.bg_brush,
            lpszClassName: class_name.as_ptr(),
            ..zeroed()
        };
        RegisterClassW(&wc);

        let title = wide(WINDOW_TITLE);
        let style = WS_OVERLAPPEDWINDOW | WS_CLIPCHILDREN;
        let mut window_rect = RECT {
            left: 0,
            top: 0,
            right: CLIENT_WIDTH,
            bottom: CLIENT_HEIGHT,
        };
        AdjustWindowRectEx(&mut window_rect, style, 0, 0);
        CreateWindowExW(
            0,
            class_name.as_ptr(),
            title.as_ptr(),
            style,
            CW_USEDEFAULT,
            CW_USEDEFAULT,
            window_rect.right - window_rect.left,
            window_rect.bottom - window_rect.top,
            0 as HWND,
            0 as _,
            self.hinstance,
            null_mut(),
        );

        let mut msg: MSG = zeroed();
        while GetMessageW(&mut msg, 0 as HWND, 0, 0) > 0 {
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }

    unsafe fn on_create(&mut self, hwnd: HWND) {
        self.hwnd = hwnd;
        let icon = load_app_icon(self.hinstance);
        SendMessageW(self.hwnd, WM_SETICON, ICON_BIG as usize, icon as isize);
        SendMessageW(self.hwnd, WM_SETICON, ICON_SMALL as usize, icon as isize);
        self.create_controls();
        self.settings = read_settings();
        self.apply_settings_to_ui();
        self.register_hotkeys();
        self.add_tray_icon();
        self.set_status("Ready. Shortcuts are active while the app is running.");
    }

    unsafe fn create_controls(&mut self) {
        self.create_group("Shortcuts", 6, 6, 365, 318);
        self.create_label(
            "Choose the key combinations for each action.",
            18,
            26,
            340,
            14,
            self.font_small,
        );

        let rows = [
            (
                "Resize to 80%:",
                BuiltInKey::Resize80,
                ID_EDIT_RESIZE_80,
                ID_RECORD_RESIZE_80,
            ),
            (
                "Fullscreen:",
                BuiltInKey::Fullscreen,
                ID_EDIT_FULLSCREEN,
                ID_RECORD_FULLSCREEN,
            ),
            (
                "Center Window:",
                BuiltInKey::Center,
                ID_EDIT_CENTER,
                ID_RECORD_CENTER,
            ),
            (
                "Resize to 60%:",
                BuiltInKey::Resize60,
                ID_EDIT_RESIZE_60,
                ID_RECORD_RESIZE_60,
            ),
            (
                "Expand Window:",
                BuiltInKey::Expand,
                ID_EDIT_EXPAND,
                ID_RECORD_EXPAND,
            ),
            (
                "Shrink Window:",
                BuiltInKey::Shrink,
                ID_EDIT_SHRINK,
                ID_RECORD_SHRINK,
            ),
        ];

        for (index, (label, key, edit_id, record_id)) in rows.iter().enumerate() {
            let y = 48 + (index as i32 * 25);
            self.create_right_label(label, 18, y + 3, 110, 14, self.font_normal);
            let edit = self.create_edit("", *edit_id, 136, y, 158, 20);
            self.set_builtin_edit(*key, edit);
            self.create_button("Record", *record_id, 299, y - 1, 60, 23);
        }

        self.create_right_label("Resize Increment:", 18, 211, 110, 14, self.font_normal);
        self.controls.increment_edit = self.create_edit("", ID_INCREMENT_EDIT, 136, 208, 42, 20);
        self.controls.increment_track = self.create_child(
            "msctls_trackbar32",
            "",
            WS_TABSTOP | TBS_AUTOTICKS,
            0,
            ID_INCREMENT_TRACK,
            184,
            202,
            175,
            32,
        );
        SendMessageW(
            self.controls.increment_track,
            TBM_SETRANGE,
            1,
            make_lparam(5, 150),
        );
        SendMessageW(self.controls.increment_track, TBM_SETPOS, 1, 10);
        self.create_label(
            "Pixels moved per edge when expanding or shrinking.",
            18,
            239,
            335,
            14,
            self.font_small,
        );
        self.create_button("Save Hotkeys", ID_SAVE, 18, 270, 341, 23);

        self.create_group("Custom Resizes", 377, 6, 388, 236);
        self.create_label(
            "Create extra resize percentages and shortcuts.",
            389,
            26,
            364,
            14,
            self.font_small,
        );
        self.controls.custom_list = self.create_child(
            "LISTBOX",
            "",
            WS_BORDER | WS_VSCROLL | LBS_NOTIFY as u32,
            WS_EX_CLIENTEDGE,
            ID_CUSTOM_LIST,
            389,
            48,
            364,
            96,
        );
        self.send_font(self.controls.custom_list, self.font_mono);
        self.create_label("Percent:", 389, 158, 52, 14, self.font_normal);
        self.controls.custom_percent = self.create_edit("", ID_CUSTOM_PERCENT, 444, 154, 42, 20);
        self.create_label("Hotkey:", 494, 158, 48, 14, self.font_normal);
        self.controls.custom_hotkey = self.create_edit("", ID_CUSTOM_HOTKEY, 544, 154, 123, 20);
        self.create_button("Set", ID_CUSTOM_RECORD, 673, 153, 60, 23);
        self.create_button("Add", ID_CUSTOM_ADD, 389, 192, 75, 23);
        self.create_button("Remove", ID_CUSTOM_REMOVE, 470, 192, 75, 23);

        self.create_group("Options", 377, 248, 388, 86);
        self.create_label(
            "Control startup and background behavior.",
            389,
            268,
            364,
            14,
            self.font_small,
        );
        self.controls.startup_check = self.create_child(
            "BUTTON",
            "Start with Windows",
            BS_AUTOCHECKBOX as u32 | WS_TABSTOP,
            0,
            ID_STARTUP,
            389,
            292,
            155,
            20,
        );
        self.send_font(self.controls.startup_check, self.font_normal);
        self.create_button("Minimize to Tray", ID_MINIMIZE, 595, 288, 158, 23);

        self.controls.status = self.create_status(
            "",
            0,
            CLIENT_HEIGHT - STATUS_HEIGHT,
            CLIENT_WIDTH,
            STATUS_HEIGHT,
        );
    }

    unsafe fn on_paint(&self, hwnd: HWND) {
        let mut ps: PAINTSTRUCT = zeroed();
        let hdc = BeginPaint(hwnd, &mut ps);

        let mut client: RECT = zeroed();
        GetClientRect(hwnd, &mut client);

        FillRect(hdc, &client, self.bg_brush);

        EndPaint(hwnd, &ps);
    }

    unsafe fn create_child(
        &self,
        class: &str,
        text: &str,
        style: u32,
        ex_style: u32,
        id: i32,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
    ) -> HWND {
        let class = wide(class);
        let text = wide(text);
        CreateWindowExW(
            ex_style,
            class.as_ptr(),
            text.as_ptr(),
            WS_CHILD | WS_VISIBLE | style,
            x,
            y,
            width,
            height,
            self.hwnd,
            id as usize as _,
            self.hinstance,
            null_mut(),
        )
    }

    unsafe fn create_label(
        &self,
        text: &str,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
        font: HFONT,
    ) -> HWND {
        let hwnd = self.create_child("STATIC", text, 0, 0, 0, x, y, width, height);
        self.send_font(hwnd, font);
        hwnd
    }

    unsafe fn create_right_label(
        &self,
        text: &str,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
        font: HFONT,
    ) -> HWND {
        let hwnd = self.create_child("STATIC", text, STATIC_RIGHT, 0, 0, x, y, width, height);
        self.send_font(hwnd, font);
        hwnd
    }

    unsafe fn create_status(&self, text: &str, x: i32, y: i32, width: i32, height: i32) -> HWND {
        let hwnd = self.create_child("STATIC", text, STATIC_SUNKEN, 0, 0, x, y, width, height);
        self.send_font(hwnd, self.font_small);
        hwnd
    }

    unsafe fn create_group(&self, text: &str, x: i32, y: i32, width: i32, height: i32) -> HWND {
        let hwnd = self.create_child(
            "BUTTON",
            text,
            BS_GROUPBOX as u32,
            0,
            0,
            x,
            y,
            width,
            height,
        );
        self.send_font(hwnd, self.font_bold);
        hwnd
    }

    unsafe fn create_button(
        &self,
        text: &str,
        id: i32,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
    ) -> HWND {
        let hwnd = self.create_child(
            "BUTTON",
            text,
            BS_PUSHBUTTON as u32 | WS_TABSTOP,
            0,
            id,
            x,
            y,
            width,
            height,
        );
        self.send_font(hwnd, self.font_bold);
        hwnd
    }

    unsafe fn create_edit(
        &self,
        text: &str,
        id: i32,
        x: i32,
        y: i32,
        width: i32,
        height: i32,
    ) -> HWND {
        let hwnd = self.create_child(
            "EDIT",
            text,
            WS_TABSTOP | WS_BORDER | ES_AUTOHSCROLL as u32,
            WS_EX_CLIENTEDGE,
            id,
            x,
            y,
            width,
            height,
        );
        self.send_font(hwnd, self.font_normal);
        hwnd
    }

    unsafe fn send_font(&self, hwnd: HWND, font: HFONT) {
        SendMessageW(hwnd, WM_SETFONT, font as usize, 1);
    }

    fn set_builtin_edit(&mut self, key: BuiltInKey, hwnd: HWND) {
        match key {
            BuiltInKey::Resize80 => self.controls.resize_80 = hwnd,
            BuiltInKey::Fullscreen => self.controls.fullscreen = hwnd,
            BuiltInKey::Center => self.controls.center = hwnd,
            BuiltInKey::Resize60 => self.controls.resize_60 = hwnd,
            BuiltInKey::Expand => self.controls.expand = hwnd,
            BuiltInKey::Shrink => self.controls.shrink = hwnd,
        }
    }

    fn builtin_edit(&self, key: BuiltInKey) -> HWND {
        match key {
            BuiltInKey::Resize80 => self.controls.resize_80,
            BuiltInKey::Fullscreen => self.controls.fullscreen,
            BuiltInKey::Center => self.controls.center,
            BuiltInKey::Resize60 => self.controls.resize_60,
            BuiltInKey::Expand => self.controls.expand,
            BuiltInKey::Shrink => self.controls.shrink,
        }
    }

    unsafe fn apply_settings_to_ui(&mut self) {
        set_text(self.controls.resize_80, &self.settings.resize_80);
        set_text(self.controls.fullscreen, &self.settings.fullscreen);
        set_text(self.controls.center, &self.settings.center);
        set_text(self.controls.resize_60, &self.settings.resize_60);
        set_text(self.controls.expand, &self.settings.expand_window);
        set_text(self.controls.shrink, &self.settings.shrink_window);
        self.settings.resize_increment = self.settings.resize_increment.clamp(5, 150);
        set_text(
            self.controls.increment_edit,
            &self.settings.resize_increment.to_string(),
        );
        SendMessageW(
            self.controls.increment_track,
            TBM_SETPOS,
            1,
            self.settings.resize_increment as isize,
        );
        SendMessageW(
            self.controls.startup_check,
            BM_SETCHECK,
            if self.settings.startup {
                BST_CHECKED
            } else {
                BST_UNCHECKED
            } as usize,
            0,
        );
        self.refresh_custom_list();
    }

    unsafe fn refresh_custom_list(&self) {
        SendMessageW(self.controls.custom_list, LB_RESETCONTENT, 0, 0);
        for action in &self.settings.custom_actions {
            let row = format!("{:>3}%   {}", action.percentage, action.hotkey);
            let row = wide(&row);
            SendMessageW(
                self.controls.custom_list,
                LB_ADDSTRING,
                0,
                row.as_ptr() as isize,
            );
        }
    }

    unsafe fn save_from_ui(&mut self) {
        self.settings.resize_80 = get_text(self.controls.resize_80);
        self.settings.fullscreen = get_text(self.controls.fullscreen);
        self.settings.center = get_text(self.controls.center);
        self.settings.resize_60 = get_text(self.controls.resize_60);
        self.settings.expand_window = get_text(self.controls.expand);
        self.settings.shrink_window = get_text(self.controls.shrink);
        self.settings.resize_increment = self.read_increment();
        self.settings.startup =
            SendMessageW(self.controls.startup_check, BM_GETCHECK, 0, 0) == BST_CHECKED as isize;

        write_settings(&self.settings);
        self.set_startup(self.settings.startup);
        self.register_hotkeys();
        self.set_status("Settings saved and hotkeys registered.");
    }

    unsafe fn read_increment(&self) -> i32 {
        let value = get_text(self.controls.increment_edit)
            .trim()
            .parse::<i32>()
            .unwrap_or(self.settings.resize_increment)
            .clamp(5, 150);
        set_text(self.controls.increment_edit, &value.to_string());
        SendMessageW(self.controls.increment_track, TBM_SETPOS, 1, value as isize);
        value
    }

    unsafe fn set_status(&self, message: &str) {
        set_text(self.controls.status, message);
    }

    fn recording_control(&self) -> Option<HWND> {
        match self.recording {
            Some(RecordingTarget::BuiltIn(key)) => Some(self.builtin_edit(key)),
            Some(RecordingTarget::CustomHotkey) => Some(self.controls.custom_hotkey),
            None => None,
        }
    }

    unsafe fn layout_status(&self) {
        if self.controls.status.is_null() {
            return;
        }
        let mut client: RECT = zeroed();
        GetClientRect(self.hwnd, &mut client);
        MoveWindow(
            self.controls.status,
            0,
            client.bottom - STATUS_HEIGHT,
            client.right,
            STATUS_HEIGHT,
            1,
        );
    }

    unsafe fn handle_command(&mut self, id: i32) {
        match id {
            ID_RECORD_RESIZE_80 => {
                self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Resize80))
            }
            ID_RECORD_FULLSCREEN => {
                self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Fullscreen))
            }
            ID_RECORD_CENTER => self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Center)),
            ID_RECORD_RESIZE_60 => {
                self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Resize60))
            }
            ID_RECORD_EXPAND => self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Expand)),
            ID_RECORD_SHRINK => self.start_recording(RecordingTarget::BuiltIn(BuiltInKey::Shrink)),
            ID_CUSTOM_RECORD => self.start_recording(RecordingTarget::CustomHotkey),
            ID_SAVE => self.save_from_ui(),
            ID_CUSTOM_ADD => self.add_custom_action(),
            ID_CUSTOM_REMOVE => self.remove_custom_action(),
            ID_STARTUP => self.save_from_ui(),
            ID_MINIMIZE => self.minimize_to_tray(),
            ID_TRAY_RESTORE => self.restore_from_tray(),
            ID_TRAY_RECOVER => {
                self.register_hotkeys();
                self.set_status("Hotkeys recovered.");
            }
            ID_TRAY_EXIT => {
                DestroyWindow(self.hwnd);
            }
            _ => {}
        }
    }

    unsafe fn start_recording(&mut self, target: RecordingTarget) {
        self.recording = Some(target);
        match target {
            RecordingTarget::BuiltIn(key) => set_text(self.builtin_edit(key), "Press shortcut..."),
            RecordingTarget::CustomHotkey => {
                set_text(self.controls.custom_hotkey, "Press shortcut...")
            }
        }
        self.unregister_hotkeys();
        SetFocus(self.hwnd);
        self.set_status(
            "Recording shortcut. Press the final key with any modifiers, or Esc to cancel.",
        );
    }

    unsafe fn handle_recording_key(&mut self, vk: u32) -> bool {
        let Some(target) = self.recording else {
            return false;
        };

        if vk == VK_ESCAPE as u32 {
            self.recording = None;
            self.apply_settings_to_ui();
            self.register_hotkeys();
            self.set_status("Shortcut recording cancelled.");
            return true;
        }

        if is_modifier_vk(vk) {
            return true;
        }

        let Some(hotkey) = format_recorded_hotkey(vk) else {
            return true;
        };

        match target {
            RecordingTarget::BuiltIn(key) => set_text(self.builtin_edit(key), &hotkey),
            RecordingTarget::CustomHotkey => set_text(self.controls.custom_hotkey, &hotkey),
        }
        self.recording = None;
        self.save_from_ui();
        true
    }

    unsafe fn add_custom_action(&mut self) {
        let percentage = get_text(self.controls.custom_percent).trim().to_string();
        let hotkey = get_text(self.controls.custom_hotkey).trim().to_string();
        let valid_percentage = percentage
            .parse::<u32>()
            .map(|value| (1..=100).contains(&value))
            .unwrap_or(false);
        if !valid_percentage || parse_hotkey(&hotkey).is_none() {
            message_box(
                self.hwnd,
                "Enter a resize percentage from 1 to 100 and a valid hotkey.",
            );
            return;
        }

        self.settings
            .custom_actions
            .push(CustomAction { percentage, hotkey });
        set_text(self.controls.custom_percent, "");
        set_text(self.controls.custom_hotkey, "");
        self.refresh_custom_list();
        write_settings(&self.settings);
        self.register_hotkeys();
        self.set_status("Custom resize action added.");
    }

    unsafe fn remove_custom_action(&mut self) {
        let selected = SendMessageW(self.controls.custom_list, LB_GETCURSEL, 0, 0);
        if selected < 0 {
            self.set_status("Select a custom action before removing it.");
            return;
        }
        let index = selected as usize;
        if index < self.settings.custom_actions.len() {
            self.settings.custom_actions.remove(index);
            self.refresh_custom_list();
            write_settings(&self.settings);
            self.register_hotkeys();
            self.set_status("Custom resize action removed.");
        }
    }

    unsafe fn register_hotkeys(&mut self) {
        self.unregister_hotkeys();
        self.next_hotkey_id = FIRST_HOTKEY_ID;

        let builtins = [
            (self.settings.resize_80.clone(), HotkeyAction::Resize(0.8)),
            (self.settings.fullscreen.clone(), HotkeyAction::Resize(1.0)),
            (self.settings.center.clone(), HotkeyAction::Center),
            (self.settings.resize_60.clone(), HotkeyAction::Resize(0.6)),
            (self.settings.expand_window.clone(), HotkeyAction::Expand),
            (self.settings.shrink_window.clone(), HotkeyAction::Shrink),
            ("ctrl+shift+h".to_string(), HotkeyAction::MinimizeStart),
            ("ctrl+shift+m".to_string(), HotkeyAction::MinimizeComplete),
        ];
        for (hotkey, action) in builtins {
            self.register_one_hotkey(&hotkey, action);
        }

        for action in self.settings.custom_actions.clone() {
            if let Ok(percent) = action.percentage.parse::<f64>() {
                self.register_one_hotkey(&action.hotkey, HotkeyAction::Resize(percent / 100.0));
            }
        }

        self.update_tray_tip();
    }

    unsafe fn register_one_hotkey(&mut self, hotkey: &str, action: HotkeyAction) {
        let Some(binding) = parse_hotkey(hotkey) else {
            return;
        };
        let id = self.next_hotkey_id;
        self.next_hotkey_id += 1;
        if RegisterHotKey(self.hwnd, id, binding.modifiers, binding.vk) != 0 {
            self.hotkey_actions.insert(id, action);
        }
    }

    unsafe fn unregister_hotkeys(&mut self) {
        for id in self.hotkey_actions.keys().copied().collect::<Vec<_>>() {
            UnregisterHotKey(self.hwnd, id);
        }
        self.hotkey_actions.clear();
    }

    unsafe fn handle_hotkey(&mut self, id: i32) {
        let Some(action) = self.hotkey_actions.get(&id).cloned() else {
            return;
        };
        match action {
            HotkeyAction::Resize(scale) => {
                self.with_foreground_window(|app, hwnd| app.resize_window(hwnd, scale))
            }
            HotkeyAction::Center => {
                self.with_foreground_window(|app, hwnd| app.center_window(hwnd))
            }
            HotkeyAction::Expand => self.with_foreground_window(|app, hwnd| {
                app.adjust_window(hwnd, app.settings.resize_increment)
            }),
            HotkeyAction::Shrink => self.with_foreground_window(|app, hwnd| {
                app.adjust_window(hwnd, -app.settings.resize_increment)
            }),
            HotkeyAction::MinimizeStart => {
                self.minimize_started = Some(Instant::now());
                self.set_status("Minimize-all sequence started.");
            }
            HotkeyAction::MinimizeComplete => {
                if self
                    .minimize_started
                    .map(|started| started.elapsed() <= Duration::from_secs(2))
                    .unwrap_or(false)
                {
                    match self.minimize_windows_on_current_monitor() {
                        Some(count) => {
                            self.set_status(&format!(
                                "Minimized {} windows on the current monitor.",
                                count
                            ));
                        }
                        None => self.set_status("Could not determine the current monitor."),
                    }
                } else {
                    self.set_status("Minimize-all sequence expired.");
                }
                self.minimize_started = None;
            }
        }
    }

    unsafe fn with_foreground_window<F>(&mut self, action: F)
    where
        F: FnOnce(&mut Self, HWND),
    {
        let hwnd = GetForegroundWindow();
        if hwnd == 0 as HWND || hwnd == self.hwnd {
            return;
        }
        action(self, hwnd);
    }

    unsafe fn resize_window(&self, hwnd: HWND, scale: f64) {
        let Some(work) = monitor_work_area(hwnd) else {
            return;
        };
        let monitor_width = work.right - work.left;
        let monitor_height = work.bottom - work.top;
        let width = (monitor_width as f64 * scale).round() as i32;
        let height = (monitor_height as f64 * scale).round() as i32;
        let left = work.left + (monitor_width - width) / 2;
        let top = work.top + (monitor_height - height) / 2;
        SetWindowPos(hwnd, 0 as HWND, left, top, width, height, SWP_NOZORDER);
    }

    unsafe fn center_window(&self, hwnd: HWND) {
        let mut rect: RECT = zeroed();
        if GetWindowRect(hwnd, &mut rect) == 0 {
            return;
        }
        let Some(work) = monitor_work_area(hwnd) else {
            return;
        };
        let width = rect.right - rect.left;
        let height = rect.bottom - rect.top;
        let left = work.left + ((work.right - work.left) - width) / 2;
        let top = work.top + ((work.bottom - work.top) - height) / 2;
        SetWindowPos(hwnd, 0 as HWND, left, top, width, height, SWP_NOZORDER);
    }

    unsafe fn adjust_window(&mut self, hwnd: HWND, increment: i32) {
        self.settings.resize_increment = self.read_increment();
        let mut rect: RECT = zeroed();
        if GetWindowRect(hwnd, &mut rect) == 0 {
            return;
        }
        let Some(work) = monitor_work_area(hwnd) else {
            return;
        };

        let current_width = rect.right - rect.left;
        let current_height = rect.bottom - rect.top;
        let work_width = work.right - work.left;
        let work_height = work.bottom - work.top;
        let mut width = (current_width + (2 * increment)).clamp(100, work_width);
        let mut height = (current_height + (2 * increment)).clamp(100, work_height);
        if width > work_width {
            width = work_width;
        }
        if height > work_height {
            height = work_height;
        }

        let mut left = rect.left - increment;
        let mut top = rect.top - increment;
        if left < work.left {
            left = work.left;
        }
        if top < work.top {
            top = work.top;
        }
        if left + width > work.right {
            left = work.right - width;
        }
        if top + height > work.bottom {
            top = work.bottom - height;
        }
        SetWindowPos(hwnd, 0 as HWND, left, top, width, height, SWP_NOZORDER);
    }

    unsafe fn minimize_windows_on_current_monitor(&self) -> Option<usize> {
        let mut point: POINT = zeroed();
        if GetCursorPos(&mut point) == 0 {
            return None;
        }
        let monitor = MonitorFromPoint(point, MONITOR_DEFAULTTONULL);
        if monitor.is_null() {
            return None;
        }
        Some(self.minimize_windows_on_monitor(monitor))
    }

    unsafe fn minimize_windows_on_monitor(&self, monitor: HMONITOR) -> usize {
        let mut context = EnumContext {
            monitor,
            self_hwnd: self.hwnd,
            minimized: 0,
        };
        EnumWindows(
            Some(enum_minimize_proc),
            &mut context as *mut EnumContext as isize,
        );
        context.minimized
    }

    unsafe fn add_tray_icon(&mut self) {
        if self.tray_added {
            return;
        }
        let mut data = self.tray_data();
        if Shell_NotifyIconW(NIM_ADD, &mut data) != 0 {
            self.tray_added = true;
        }
    }

    unsafe fn update_tray_tip(&self) {
        if !self.tray_added {
            return;
        }
        let mut data = self.tray_data();
        Shell_NotifyIconW(NIM_MODIFY, &mut data);
    }

    unsafe fn remove_tray_icon(&mut self) {
        if self.tray_added {
            let mut data = self.tray_data();
            Shell_NotifyIconW(NIM_DELETE, &mut data);
            self.tray_added = false;
        }
    }

    unsafe fn tray_data(&self) -> NOTIFYICONDATAW {
        let mut data: NOTIFYICONDATAW = zeroed();
        data.cbSize = size_of::<NOTIFYICONDATAW>() as u32;
        data.hWnd = self.hwnd;
        data.uID = TRAY_ID;
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP;
        data.uCallbackMessage = WM_TRAYICON;
        data.hIcon = load_app_icon(self.hinstance);
        let tip = format!(
            "Window Manager App {} - {} hotkeys active",
            APP_VERSION,
            self.hotkey_actions.len()
        );
        copy_wide_fixed(&mut data.szTip, &tip);
        data
    }

    unsafe fn minimize_to_tray(&mut self) {
        self.add_tray_icon();
        ShowWindow(self.hwnd, SW_HIDE);
    }

    unsafe fn restore_from_tray(&mut self) {
        self.add_tray_icon();
        ShowWindow(self.hwnd, SW_SHOW);
        ShowWindow(self.hwnd, SW_RESTORE);
        SetForegroundWindow(self.hwnd);
    }

    unsafe fn show_tray_menu(&mut self) {
        let menu = CreatePopupMenu();
        append_menu(menu, ID_TRAY_RESTORE, "Restore");
        let hotkeys = format!("Hotkeys: {} active", self.hotkey_actions.len());
        let hotkeys_w = wide(&hotkeys);
        AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, hotkeys_w.as_ptr());
        AppendMenuW(menu, MF_SEPARATOR, 0, null());
        append_menu(menu, ID_TRAY_RECOVER, "Recover Hotkeys");
        append_menu(menu, ID_TRAY_EXIT, "Exit");

        let mut point: POINT = zeroed();
        GetCursorPos(&mut point);
        SetForegroundWindow(self.hwnd);
        TrackPopupMenu(
            menu,
            TPM_RIGHTBUTTON,
            point.x,
            point.y,
            0,
            self.hwnd,
            null(),
        );
        DestroyMenu(menu);
    }

    unsafe fn handle_tray(&mut self, event: u32) {
        match event {
            WM_LBUTTONDBLCLK => self.restore_from_tray(),
            WM_RBUTTONUP | WM_CONTEXTMENU => self.show_tray_menu(),
            _ => {}
        }
    }

    unsafe fn set_startup(&self, enable: bool) {
        let path = wide("Software\\Microsoft\\Windows\\CurrentVersion\\Run");
        let name = wide(APP_NAME);
        let mut key: HKEY = 0 as _;
        if RegOpenKeyExW(HKEY_CURRENT_USER, path.as_ptr(), 0, KEY_WRITE, &mut key) != 0 {
            return;
        }

        if enable {
            if let Ok(exe) = std::env::current_exe() {
                let command = format!("\"{}\"", exe.display());
                let command = wide(&command);
                RegSetValueExW(
                    key,
                    name.as_ptr(),
                    0,
                    REG_SZ,
                    command.as_ptr() as *const u8,
                    (command.len() * 2) as u32,
                );
            }
        } else {
            RegDeleteValueW(key, name.as_ptr());
        }
        RegCloseKey(key);
    }

    unsafe fn cleanup(&mut self) {
        self.unregister_hotkeys();
        self.remove_tray_icon();
        DeleteObject(self.bg_brush as _);
        DeleteObject(self.white_brush as _);
        DeleteObject(self.highlight_brush as _);
        DeleteObject(self.font_normal as _);
        DeleteObject(self.font_small as _);
        DeleteObject(self.font_bold as _);
        DeleteObject(self.font_mono as _);
    }
}

#[derive(Clone, Copy)]
struct HotkeyBinding {
    modifiers: u32,
    vk: u32,
}

fn parse_hotkey(input: &str) -> Option<HotkeyBinding> {
    let mut modifiers = MOD_NOREPEAT;
    let mut key = None;
    for raw in input.split('+') {
        let token = raw.trim().to_ascii_lowercase();
        if token.is_empty() {
            continue;
        }
        match token.as_str() {
            "ctrl" | "control" => modifiers |= MOD_CONTROL,
            "shift" => modifiers |= MOD_SHIFT,
            "alt" => modifiers |= MOD_ALT,
            "windows" | "win" | "meta" | "super" => modifiers |= MOD_WIN,
            _ => key = key_to_vk(&token),
        }
    }
    key.map(|vk| HotkeyBinding { modifiers, vk })
}

fn key_to_vk(key: &str) -> Option<u32> {
    if key.len() == 1 {
        let ch = key.chars().next().unwrap();
        if ch.is_ascii_alphabetic() {
            return Some(ch.to_ascii_uppercase() as u32);
        }
        if ch.is_ascii_digit() {
            return Some(ch as u32);
        }
    }

    if let Some(number) = key
        .strip_prefix('f')
        .and_then(|value| value.parse::<u32>().ok())
    {
        if (1..=24).contains(&number) {
            return Some(VK_F1 as u32 + number - 1);
        }
    }

    Some(match key {
        "space" => VK_SPACE as u32,
        "enter" | "return" => VK_RETURN as u32,
        "tab" => VK_TAB as u32,
        "esc" | "escape" => VK_ESCAPE as u32,
        "backspace" => VK_BACK as u32,
        "delete" | "del" => VK_DELETE as u32,
        "insert" | "ins" => VK_INSERT as u32,
        "home" => VK_HOME as u32,
        "end" => VK_END as u32,
        "page up" | "pageup" => VK_PRIOR as u32,
        "page down" | "pagedown" => VK_NEXT as u32,
        "up" => VK_UP as u32,
        "down" => VK_DOWN as u32,
        "left" => VK_LEFT as u32,
        "right" => VK_RIGHT as u32,
        "comma" | "," => VK_OEM_COMMA as u32,
        "period" | "." => VK_OEM_PERIOD as u32,
        "slash" | "/" => VK_OEM_2 as u32,
        "backslash" | "\\" => VK_OEM_5 as u32,
        "semicolon" | ";" => VK_OEM_1 as u32,
        "apostrophe" | "'" => VK_OEM_7 as u32,
        "minus" | "-" => VK_OEM_MINUS as u32,
        "equal" | "=" => VK_OEM_PLUS as u32,
        "grave" | "`" => VK_OEM_3 as u32,
        "left bracket" | "leftbracket" | "[" => VK_OEM_4 as u32,
        "right bracket" | "rightbracket" | "]" => VK_OEM_6 as u32,
        _ => return None,
    })
}

fn vk_to_key(vk: u32) -> Option<String> {
    if (b'A' as u32..=b'Z' as u32).contains(&vk) {
        return Some((vk as u8 as char).to_ascii_lowercase().to_string());
    }
    if (b'0' as u32..=b'9' as u32).contains(&vk) {
        return Some((vk as u8 as char).to_string());
    }
    if (VK_F1 as u32..=VK_F24 as u32).contains(&vk) {
        return Some(format!("f{}", vk - VK_F1 as u32 + 1));
    }

    Some(
        match vk {
            value if value == VK_SPACE as u32 => "space",
            value if value == VK_RETURN as u32 => "enter",
            value if value == VK_TAB as u32 => "tab",
            value if value == VK_ESCAPE as u32 => "esc",
            value if value == VK_BACK as u32 => "backspace",
            value if value == VK_DELETE as u32 => "delete",
            value if value == VK_INSERT as u32 => "insert",
            value if value == VK_HOME as u32 => "home",
            value if value == VK_END as u32 => "end",
            value if value == VK_PRIOR as u32 => "page up",
            value if value == VK_NEXT as u32 => "page down",
            value if value == VK_UP as u32 => "up",
            value if value == VK_DOWN as u32 => "down",
            value if value == VK_LEFT as u32 => "left",
            value if value == VK_RIGHT as u32 => "right",
            value if value == VK_OEM_COMMA as u32 => "comma",
            value if value == VK_OEM_PERIOD as u32 => "period",
            value if value == VK_OEM_2 as u32 => "slash",
            value if value == VK_OEM_5 as u32 => "backslash",
            value if value == VK_OEM_1 as u32 => "semicolon",
            value if value == VK_OEM_7 as u32 => "apostrophe",
            value if value == VK_OEM_MINUS as u32 => "minus",
            value if value == VK_OEM_PLUS as u32 => "equal",
            value if value == VK_OEM_3 as u32 => "grave",
            value if value == VK_OEM_4 as u32 => "left bracket",
            value if value == VK_OEM_6 as u32 => "right bracket",
            _ => return None,
        }
        .to_string(),
    )
}

unsafe fn format_recorded_hotkey(vk: u32) -> Option<String> {
    let key = vk_to_key(vk)?;
    let mut parts = Vec::new();
    if is_key_down(VK_CONTROL as i32) {
        parts.push("ctrl".to_string());
    }
    if is_key_down(VK_SHIFT as i32) {
        parts.push("shift".to_string());
    }
    if is_key_down(VK_MENU as i32) {
        parts.push("alt".to_string());
    }
    if is_key_down(VK_LWIN as i32) || is_key_down(VK_RWIN as i32) {
        parts.push("windows".to_string());
    }
    parts.push(key);
    Some(parts.join("+"))
}

unsafe fn is_key_down(vk: i32) -> bool {
    (GetKeyState(vk) as u16 & 0x8000) != 0
}

fn is_modifier_vk(vk: u32) -> bool {
    matches!(
        vk,
        value if value == VK_CONTROL as u32
            || value == VK_LCONTROL as u32
            || value == VK_RCONTROL as u32
            || value == VK_SHIFT as u32
            || value == VK_LSHIFT as u32
            || value == VK_RSHIFT as u32
            || value == VK_MENU as u32
            || value == VK_LMENU as u32
            || value == VK_RMENU as u32
            || value == VK_LWIN as u32
            || value == VK_RWIN as u32
    )
}

unsafe fn monitor_work_area(hwnd: HWND) -> Option<RECT> {
    let monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
    let mut info = MONITORINFO {
        cbSize: size_of::<MONITORINFO>() as u32,
        ..zeroed()
    };
    if GetMonitorInfoW(monitor, &mut info) == 0 {
        return None;
    }
    Some(info.rcWork)
}

struct EnumContext {
    monitor: HMONITOR,
    self_hwnd: HWND,
    minimized: usize,
}

unsafe extern "system" fn enum_minimize_proc(hwnd: HWND, lparam: LPARAM) -> BOOL {
    let context = &mut *(lparam as *mut EnumContext);
    if hwnd == context.self_hwnd || IsWindowVisible(hwnd) == 0 || IsIconic(hwnd) != 0 {
        return 1;
    }

    if MonitorFromWindow(hwnd, MONITOR_DEFAULTTONULL) != context.monitor {
        return 1;
    }

    let class_name = window_class_name(hwnd);
    let snapshot = WindowSnapshot {
        is_self: hwnd == context.self_hwnd,
        is_visible: true,
        is_minimized: false,
        is_on_target_monitor: true,
        is_shell_surface: class_name
            .as_deref()
            .map(is_shell_surface_class)
            .unwrap_or(false),
        extended_style: GetWindowLongPtrW(hwnd, GWL_EXSTYLE) as u32,
        has_owner: !GetWindow(hwnd, GW_OWNER).is_null(),
    };

    if window_can_be_minimized(snapshot) {
        ShowWindow(hwnd, SW_MINIMIZE);
        context.minimized += 1;
    }
    1
}

fn window_class_name(hwnd: HWND) -> Option<String> {
    let mut buffer = [0u16; 256];
    let length = unsafe { GetClassNameW(hwnd, buffer.as_mut_ptr(), buffer.len() as i32) };
    if length <= 0 {
        return None;
    }
    Some(String::from_utf16_lossy(&buffer[..length as usize]))
}

fn is_shell_surface_class(class_name: &str) -> bool {
    matches!(
        class_name,
        SHELL_DESKTOP_CLASS
            | SHELL_WORKER_CLASS
            | SHELL_PRIMARY_TASKBAR_CLASS
            | SHELL_SECONDARY_TASKBAR_CLASS
    )
}

#[derive(Clone, Copy)]
struct WindowSnapshot {
    is_self: bool,
    is_visible: bool,
    is_minimized: bool,
    is_on_target_monitor: bool,
    is_shell_surface: bool,
    extended_style: u32,
    has_owner: bool,
}

fn window_can_be_minimized(window: WindowSnapshot) -> bool {
    if window.is_self
        || !window.is_visible
        || window.is_minimized
        || !window.is_on_target_monitor
        || window.is_shell_surface
    {
        return false;
    }

    let is_app_window = window.extended_style & WS_EX_APPWINDOW != 0;
    let is_tool_window = window.extended_style & WS_EX_TOOLWINDOW != 0;
    let has_non_app_owner = window.has_owner && !is_app_window;

    (!is_tool_window && !has_non_app_owner) || is_app_window
}

fn read_settings() -> Settings {
    let path = settings_path();
    let Ok(raw) = fs::read_to_string(path) else {
        return Settings::default();
    };
    serde_json::from_str(&raw).unwrap_or_default()
}

fn write_settings(settings: &Settings) {
    if let Ok(json) = serde_json::to_string_pretty(settings) {
        let _ = fs::write(settings_path(), json);
    }
}

fn settings_path() -> PathBuf {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let exe_settings = parent.join("settings.json");
            if exe_settings.exists() {
                return exe_settings;
            }
        }
    }
    let local = PathBuf::from("settings.json");
    if local.exists() {
        return local;
    }
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|parent| parent.join("settings.json")))
        .unwrap_or(local)
}

unsafe fn set_text(hwnd: HWND, text: &str) {
    let text = wide(text);
    SetWindowTextW(hwnd, text.as_ptr());
}

unsafe fn get_text(hwnd: HWND) -> String {
    let len = GetWindowTextLengthW(hwnd);
    if len <= 0 {
        return String::new();
    }
    let mut buffer = vec![0u16; len as usize + 1];
    let read = GetWindowTextW(hwnd, buffer.as_mut_ptr(), buffer.len() as i32);
    String::from_utf16_lossy(&buffer[..read as usize])
}

unsafe fn message_box(hwnd: HWND, message: &str) {
    let message = wide(message);
    let title = wide(WINDOW_TITLE);
    MessageBoxW(
        hwnd,
        message.as_ptr(),
        title.as_ptr(),
        MB_OK | MB_ICONWARNING,
    );
}

unsafe fn append_menu(menu: HMENU, id: i32, label: &str) {
    let label = wide(label);
    AppendMenuW(menu, MF_STRING, id as usize, label.as_ptr());
}

fn copy_wide_fixed<const N: usize>(target: &mut [u16; N], text: &str) {
    let wide = wide(text);
    let max = target
        .len()
        .saturating_sub(1)
        .min(wide.len().saturating_sub(1));
    target[..max].copy_from_slice(&wide[..max]);
    target[max] = 0;
}

fn make_lparam(low: i32, high: i32) -> isize {
    ((low as u16 as u32) | ((high as u16 as u32) << 16)) as isize
}

fn sys_color(index: i32) -> u32 {
    unsafe { GetSysColor(index) }
}

fn wide(text: &str) -> Vec<u16> {
    OsStr::new(text).encode_wide().chain(Some(0)).collect()
}

unsafe fn create_font(height: i32, weight: i32) -> HFONT {
    create_font_face(height, weight, "MS Sans Serif")
}

unsafe fn create_font_face(height: i32, weight: i32, face: &str) -> HFONT {
    let face = wide(face);
    CreateFontW(
        -height,
        0,
        0,
        0,
        weight,
        0,
        0,
        0,
        DEFAULT_CHARSET as u32,
        OUT_DEFAULT_PRECIS as u32,
        CLIP_DEFAULT_PRECIS as u32,
        DEFAULT_QUALITY as u32,
        (DEFAULT_PITCH | FF_DONTCARE) as u32,
        face.as_ptr(),
    )
}

unsafe fn load_app_icon(hinstance: HINSTANCE) -> HICON {
    let icon = LoadIconW(hinstance, APP_ICON_ID as *const u16);
    if icon.is_null() {
        LoadIconW(0 as _, IDI_APPLICATION)
    } else {
        icon
    }
}

unsafe extern "system" fn window_proc(
    hwnd: HWND,
    msg: u32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    let app = if APP_PTR.is_null() {
        None
    } else {
        Some(&mut *APP_PTR)
    };

    match msg {
        WM_CREATE => {
            if let Some(app) = app {
                app.on_create(hwnd);
            }
            0
        }
        WM_COMMAND => {
            if let Some(app) = app {
                app.handle_command((wparam & 0xffff) as i32);
            }
            0
        }
        WM_HSCROLL => {
            if let Some(app) = app {
                if lparam == app.controls.increment_track as isize {
                    let pos =
                        SendMessageW(app.controls.increment_track, TBM_GETPOS_LOCAL, 0, 0) as i32;
                    set_text(app.controls.increment_edit, &pos.to_string());
                }
            }
            0
        }
        WM_KEYDOWN => {
            if let Some(app) = app {
                if app.handle_recording_key(wparam as u32) {
                    return 0;
                }
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_HOTKEY => {
            if let Some(app) = app {
                app.handle_hotkey(wparam as i32);
            }
            0
        }
        WM_SIZE => {
            if wparam == SIZE_MINIMIZED as usize {
                if let Some(app) = app {
                    app.minimize_to_tray();
                }
                return 0;
            }
            if let Some(app) = app {
                app.layout_status();
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_TRAYICON => {
            if let Some(app) = app {
                app.handle_tray(lparam as u32);
            }
            0
        }
        WM_PAINT => {
            if let Some(app) = app {
                app.on_paint(hwnd);
            } else {
                let mut ps: PAINTSTRUCT = zeroed();
                BeginPaint(hwnd, &mut ps);
                EndPaint(hwnd, &ps);
            }
            0
        }
        WM_CTLCOLORSTATIC => {
            if let Some(app) = app {
                SetBkMode(wparam as _, TRANSPARENT as i32);
                SetTextColor(wparam as _, sys_color(COLOR_BTNTEXT));
                return app.bg_brush as isize;
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_CTLCOLOREDIT => {
            if let Some(app) = app {
                let is_recording = app.recording_control() == Some(lparam as HWND);
                if is_recording {
                    SetBkColor(wparam as _, sys_color(COLOR_HIGHLIGHT));
                    SetTextColor(wparam as _, sys_color(COLOR_HIGHLIGHTTEXT));
                    return app.highlight_brush as isize;
                }
                SetBkColor(wparam as _, sys_color(COLOR_WINDOW));
                SetTextColor(wparam as _, sys_color(COLOR_WINDOWTEXT));
                return app.white_brush as isize;
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_CTLCOLORLISTBOX => {
            if let Some(app) = app {
                SetBkColor(wparam as _, sys_color(COLOR_WINDOW));
                SetTextColor(wparam as _, sys_color(COLOR_WINDOWTEXT));
                return app.white_brush as isize;
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_CTLCOLORBTN => {
            if let Some(app) = app {
                SetBkMode(wparam as _, TRANSPARENT as i32);
                SetTextColor(wparam as _, sys_color(COLOR_BTNTEXT));
                return app.bg_brush as isize;
            }
            DefWindowProcW(hwnd, msg, wparam, lparam)
        }
        WM_DESTROY => {
            if let Some(app) = app {
                app.cleanup();
            }
            PostQuitMessage(0);
            0
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

fn main() {
    unsafe {
        let mut app = Box::new(App::new());
        APP_PTR = &mut *app;
        app.run();
        APP_PTR = null_mut();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_default_oem_hotkeys() {
        let comma = parse_hotkey("ctrl+shift+comma").unwrap();
        assert_eq!(comma.vk, VK_OEM_COMMA as u32);
        assert_ne!(comma.modifiers & MOD_CONTROL, 0);
        assert_ne!(comma.modifiers & MOD_SHIFT, 0);

        let slash = parse_hotkey("ctrl+shift+slash").unwrap();
        assert_eq!(slash.vk, VK_OEM_2 as u32);
    }

    #[test]
    fn parses_named_and_function_keys() {
        assert_eq!(parse_hotkey("ctrl+alt+up").unwrap().vk, VK_UP as u32);
        assert_eq!(parse_hotkey("shift+f12").unwrap().vk, VK_F12 as u32);
        assert!(parse_hotkey("").is_none());
    }

    fn app_window() -> WindowSnapshot {
        WindowSnapshot {
            is_self: false,
            is_visible: true,
            is_minimized: false,
            is_on_target_monitor: true,
            is_shell_surface: false,
            extended_style: 0,
            has_owner: false,
        }
    }

    #[test]
    fn minimizes_only_visible_windows_on_the_target_monitor() {
        assert!(window_can_be_minimized(app_window()));

        let mut other_monitor = app_window();
        other_monitor.is_on_target_monitor = false;
        assert!(!window_can_be_minimized(other_monitor));

        let mut hidden = app_window();
        hidden.is_visible = false;
        assert!(!window_can_be_minimized(hidden));

        let mut minimized = app_window();
        minimized.is_minimized = true;
        assert!(!window_can_be_minimized(minimized));
    }

    #[test]
    fn never_minimizes_shell_surfaces_or_this_app() {
        for class_name in [
            SHELL_DESKTOP_CLASS,
            SHELL_WORKER_CLASS,
            SHELL_PRIMARY_TASKBAR_CLASS,
            SHELL_SECONDARY_TASKBAR_CLASS,
        ] {
            assert!(is_shell_surface_class(class_name));
            let mut shell = app_window();
            shell.is_shell_surface = true;
            assert!(!window_can_be_minimized(shell));
        }

        let mut this_app = app_window();
        this_app.is_self = true;
        assert!(!window_can_be_minimized(this_app));
    }

    #[test]
    fn excludes_tool_windows_and_owned_popups_unless_app_window_style_is_set() {
        let mut tool = app_window();
        tool.extended_style = WS_EX_TOOLWINDOW;
        assert!(!window_can_be_minimized(tool));

        let mut owned = app_window();
        owned.has_owner = true;
        assert!(!window_can_be_minimized(owned));

        let mut explicit_app = owned;
        explicit_app.extended_style = WS_EX_APPWINDOW;
        assert!(window_can_be_minimized(explicit_app));
    }
}
