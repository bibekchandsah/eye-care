import tkinter as tk
from tkinter import simpledialog, messagebox
import time
from threading import Thread, Timer, Event
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import webbrowser
import os
import sys
import winreg
import json
import ctypes
import logging
from datetime import datetime
import urllib.request
import urllib.error
import subprocess
import queue

# ---------------------------------------------------------------------------
# When the frozen exe is spawned as a reminder subprocess it receives
# "--reminder <html_path>" and only shows the webview, then exits.
# ---------------------------------------------------------------------------
if len(sys.argv) >= 3 and sys.argv[1] == '--reminder':
    import webview
    _html_path = sys.argv[2]
    if os.path.exists(_html_path):
        class _Api:
            def close_window(self):
                try:
                    for w in webview.windows:
                        w.destroy()
                except Exception:
                    pass
        _window = webview.create_window(
            'Eye Care Reminder', _html_path,
            fullscreen=True, frameless=True, on_top=True, js_api=_Api()
        )
        def _bring_to_front():
            time.sleep(0.5)
            try:
                if webview.windows:
                    webview.windows[0].on_top = True
                    ctypes.windll.user32.keybd_event(0, 0, 0, 0)
                    time.sleep(0.1)
                    webview.windows[0].on_top = True
            except Exception:
                pass
        def _auto_close():
            time.sleep(20)
            try:
                for w in webview.windows:
                    w.destroy()
            except Exception:
                pass
        from threading import Thread as _Thread
        _Thread(target=_bring_to_front, daemon=True).start()
        _Thread(target=_auto_close, daemon=True).start()
        webview.start(gui='edgechromium')
    sys.exit(0)

# Version
CURRENT_VERSION = "v1.0.3"
GITHUB_RELEASES_URL = "https://github.com/bibekchandsah/eye-care/releases"
GITHUB_NEW_RELEASES_URL = "https://github.com/bibekchandsah/eye-care/releases/latest"
GITHUB_API_URL = "https://api.github.com/repos/bibekchandsah/eye-care/releases/latest"

# Setup paths
def get_app_path():
    """Get the application directory (where exe is located), for settings/logs"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path():
    """Get the resource path for bundled files (index.html, eyecare.ico)"""
    if getattr(sys, 'frozen', False):
        # When frozen, resources are in temp dir _MEIPASS
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# Custom logging handler that writes recent logs at the top
class PrependFileHandler(logging.FileHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            
            # Read existing content
            existing_content = ""
            if os.path.exists(self.baseFilename):
                try:
                    with open(self.baseFilename, 'r', encoding='utf-8') as f:
                        existing_content = f.read()
                except:
                    pass
            
            # Write new log at the top
            with open(self.baseFilename, 'w', encoding='utf-8') as f:
                f.write(msg + '\n')
                if existing_content:
                    f.write(existing_content)
        except Exception:
            self.handleError(record)

def trim_log_file(log_file_path):
    """Trim log file to keep only most recent session (between first two separator lines)"""
    try:
        if not os.path.exists(log_file_path):
            return
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the second occurrence of the separator
        separator = "="*50
        separator_count = 0
        trim_index = -1
        
        for i, line in enumerate(lines):
            if separator in line:
                separator_count += 1
                if separator_count == 3:  # second occurrence
                    trim_index = i
                    break
        
        # If second separator found, keep only lines before it
        if trim_index > 0:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines[:trim_index])
    except Exception as e:
        print(f"Error trimming log file: {e}")

# Setup logging
log_file = os.path.join(get_app_path(), "eyecare.log")

# Trim log file to keep only recent session
trim_log_file(log_file)

logger = logging.getLogger('EyeCare')
logger.setLevel(logging.DEBUG)

# Create handler and formatter
handler = PrependFileHandler(log_file, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Log startup
logger.info("="*50)
logger.info(f"EyeCare Application Starting")
logger.info(f"App Path: {get_app_path()}")
logger.info(f"Resource Path: {get_resource_path()}")
logger.info(f"Python: {sys.version}")
logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

# Global variables
# default_interval_minutes = 20
default_interval_minutes = 1
default_message = "Have a look far away from your current screen to protect your beautiful eyes"

interval_minutes = default_interval_minutes
# selected_interval = "20 minutes"
selected_interval = "1 minute"
is_paused = False
auto_start_enabled = False
reminder_message = default_message
current_timer = None  # Track the scheduled Timer object
app_running = True  # Flag to control main loop

# Schedule settings
schedule_enabled = False
schedule_start = "09:00"   # HH:MM 24-hour
schedule_end = "18:00"
# update_notification_shown = False  # Track if update notification was already shown this session

# Queue for cross-thread communication - functions to run on main thread
main_thread_queue = queue.Queue()

# Settings file path
settings_file = os.path.join(get_app_path(), "settings.json")
logger.info(f"Settings file: {settings_file}")

def load_settings():
    global interval_minutes, selected_interval, reminder_message
    global schedule_enabled, schedule_start, schedule_end
    logger.info("Loading settings...")
    try:
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                interval_minutes = settings.get('interval_minutes', default_interval_minutes)
                selected_interval = settings.get('selected_interval', '20 minutes')
                reminder_message = settings.get('reminder_message', default_message)
                # If reminder message is empty, use default
                if not reminder_message or reminder_message.strip() == '':
                    reminder_message = default_message
                # Schedule settings
                schedule_enabled = settings.get('schedule_enabled', False)
                schedule_start = settings.get('schedule_start', '09:00')
                schedule_end = settings.get('schedule_end', '18:00')
                # Apply auto start setting from JSON
                auto_start_saved = settings.get('auto_start', False)
                if auto_start_saved and not is_auto_start_enabled():
                    enable_auto_start()
                elif not auto_start_saved and is_auto_start_enabled():
                    disable_auto_start()
            logger.info(f"Settings loaded: interval={interval_minutes}, selected={selected_interval}")
        else:
            logger.warning(f"Settings file not found: {settings_file}")
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        print(f"Error loading settings: {e}")

def save_settings():
    logger.info("Saving settings...")
    try:
        settings = {
            'interval_minutes': interval_minutes,
            'selected_interval': selected_interval,
            'reminder_message': reminder_message,
            'auto_start': is_auto_start_enabled(),
            'schedule_enabled': schedule_enabled,
            'schedule_start': schedule_start,
            'schedule_end': schedule_end
        }
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info("Settings saved successfully")
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        print(f"Error saving settings: {e}")

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    window.geometry(f"{width}x{height}+{x}+{y}")

def is_within_schedule():
    """Return True if reminders should fire right now based on the schedule."""
    if not schedule_enabled:
        return True
    now = datetime.now().strftime("%H:%M")
    if schedule_start <= schedule_end:
        # Same-day range e.g. 09:00 – 18:00
        return schedule_start <= now <= schedule_end
    else:
        # Overnight range e.g. 22:00 – 06:00
        return now >= schedule_start or now <= schedule_end

def show_message():
    logger.info("show_message() called")
    if is_paused:
        logger.info("Timer is paused, skipping reminder")
        schedule_next_reminder()
        return

    if not is_within_schedule():
        logger.info(f"Outside schedule ({schedule_start}–{schedule_end}), skipping reminder")
        schedule_next_reminder()
        return

    # Queue the webview to run on main thread
    main_thread_queue.put(("show_reminder", None))
    logger.info("Reminder queued for main thread")

def show_webview_reminder():
    """Show the webview reminder in a separate process to avoid blocking"""
    logger.info("show_webview_reminder() launching subprocess")
    html_path = os.path.join(get_resource_path(), "index.html")
    logger.info(f"HTML path: {html_path}")
    
    try:
        if not os.path.exists(html_path):
            logger.error(f"index.html not found at: {html_path}")
            schedule_next_reminder()
            return
            
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        logger.info("HTML file read successfully")
        
        # Replace the message placeholder with the custom message
        html_content = html_content.replace(
            '{{REMINDER_MESSAGE}}',
            reminder_message
        )
        
        # Create a temporary file with modified content
        temp_html_path = os.path.join(get_app_path(), "temp_reminder.html")
        with open(temp_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"Temp HTML created: {temp_html_path}")
        
        if getattr(sys, 'frozen', False):
            # Frozen exe: re-launch ourselves with --reminder flag.
            # No separate script needed – the exe handles it via the early-exit
            # block at the top of this file.
            subprocess.Popen(
                [sys.executable, '--reminder', temp_html_path],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            logger.info("Reminder subprocess launched (frozen self)")
        else:
            # Development: run reminder_window.py with the current Python
            reminder_script = os.path.join(get_resource_path(), "reminder_window.py")
            subprocess.Popen(
                [sys.executable, reminder_script, temp_html_path],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            logger.info("Reminder subprocess launched (dev)")
        
        # Schedule next reminder immediately (subprocess runs independently)
        schedule_next_reminder()
            
    except Exception as e:
        logger.error(f"Error showing reminder: {e}", exc_info=True)
        print(f"Error showing reminder: {e}")
        schedule_next_reminder()

def schedule_next_reminder():
    """Schedule the next reminder using threading.Timer"""
    global current_timer
    
    # Cancel any existing timer
    if current_timer:
        current_timer.cancel()
        current_timer = None
    
    if not is_paused:
        delay_seconds = interval_minutes * 60
        logger.info(f"Scheduling next reminder in {interval_minutes} minutes ({delay_seconds} seconds)")
        current_timer = Timer(delay_seconds, show_message)
        current_timer.daemon = True
        current_timer.start()

def set_interval(minutes, label):
    global interval_minutes, selected_interval
    interval_minutes = minutes
    selected_interval = label
    save_settings()

def prompt_custom_interval():
    custom_minutes = simpledialog.askinteger("Custom Interval", "Enter the interval in minutes:")
    if custom_minutes:
        set_interval(custom_minutes, f"Custom ({custom_minutes} min)")

def set_custom_interval():
    root.after(0, prompt_custom_interval)

def is_selected_interval(label):
    return selected_interval == label or (selected_interval.startswith("Custom") and label.startswith("Custom"))

def start_timer():
    global is_paused
    is_paused = False
    schedule_next_reminder()

def pause_timer():
    global is_paused, current_timer
    is_paused = True
    # Cancel the current timer
    if current_timer:
        current_timer.cancel()
        current_timer = None
        logger.info("Timer paused and cancelled")

def open_developer_page():
    webbrowser.open("https://bibekchandsah.com.np/developer.html")

def check_for_updates(show_no_update=False):
    """Check GitHub for latest release version"""
    logger.info("Checking for updates...")
    try:
        req = urllib.request.Request(GITHUB_API_URL)
        req.add_header('User-Agent', 'EyeCare-App')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            latest_version = data.get('tag_name', '')
            
            logger.info(f"Current version: {CURRENT_VERSION}, Latest version: {latest_version}")
            
            if latest_version and latest_version != CURRENT_VERSION:
                # New version available
                logger.info("New update available!")
                show_update_notification(latest_version)
            else:
                logger.info("App is up to date")
                if show_no_update:
                    show_no_update_notification()
    except urllib.error.URLError as e:
        logger.warning(f"Could not check for updates (network error): {e}")
        if show_no_update:
            show_network_error()
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        if show_no_update:
            show_network_error()

def show_update_notification(latest_version):
    """Show notification dialog about available update"""
    # global update_notification_shown
    
    # Only show once per session
    # if update_notification_shown:
    #     logger.info("Update notification already shown this session, skipping")
    #     return
    
    # update_notification_shown = True
    
    def show_dialog():
        try:
            dialog = tk.Toplevel(root)
            dialog.title("Update Available")
            dialog.transient(root)
            dialog.grab_set()
            
            # Center the dialog
            center_window(dialog, 400, 200)
            
            # Set icon
            icon_path = os.path.join(get_resource_path(), "eyecare.ico")
            if os.path.exists(icon_path):
                dialog.iconbitmap(icon_path)
            
            dialog.attributes('-topmost', True)
            
            # Message
            message = f"A new version ({latest_version}) is available!\n\nYou are currently using {CURRENT_VERSION}.\n\nWould you like to download the update?"
            label = tk.Label(dialog, text=message, font=("Arial", 10), justify=tk.LEFT, wraplength=350)
            label.pack(pady=20, padx=20)
            
            # Buttons
            button_frame = tk.Frame(dialog)
            button_frame.pack(pady=10)
            
            def download_update():
                webbrowser.open(GITHUB_NEW_RELEASES_URL)
                dialog.destroy()
            
            download_btn = tk.Button(button_frame, text="Download", command=download_update, width=12)
            download_btn.pack(side=tk.LEFT, padx=5)
            
            later_btn = tk.Button(button_frame, text="Later", command=dialog.destroy, width=12)
            later_btn.pack(side=tk.LEFT, padx=5)
            
        except Exception as e:
            logger.error(f"Error showing update notification: {e}")
    
    root.after(0, show_dialog)

def show_no_update_notification():
    """Show message that app is up to date"""
    def show_dialog():
        try:
            messagebox.showinfo(
                "No Updates",
                f"You are using the latest version ({CURRENT_VERSION})."
            )
        except Exception as e:
            logger.error(f"Error showing no update dialog: {e}")
    
    root.after(0, show_dialog)

def show_network_error():
    """Show error message when update check fails"""
    def show_dialog():
        try:
            messagebox.showerror(
                "Update Check Failed",
                "Could not check for updates.\nPlease check your internet connection."
            )
        except Exception as e:
            logger.error(f"Error showing network error dialog: {e}")
    
    root.after(0, show_dialog)

def check_updates_manually():
    """Manually trigger update check (shows result regardless)"""
    Thread(target=lambda: check_for_updates(show_no_update=True), daemon=True).start()

def check_updates_on_startup():
    """Check for updates on startup (silent if no update)"""
    Thread(target=lambda: check_for_updates(show_no_update=False), daemon=True).start()

def enable_auto_start():
    try:
        key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        reg_key = winreg.OpenKey(reg, key, 0, winreg.KEY_SET_VALUE)
        exe_path = os.path.abspath(sys.argv[0])
        winreg.SetValueEx(reg_key, 'EyeCareReminder', 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(reg_key)
        print("Auto Start Enabled")
    except Exception as e:
        print(f"Error enabling auto start: {e}")

def disable_auto_start():
    try:
        key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
        reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        reg_key = winreg.OpenKey(reg, key, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(reg_key, 'EyeCareReminder')
        winreg.CloseKey(reg_key)
        print("Auto Start Disabled")
    except Exception as e:
        print(f"Error disabling auto start: {e}")

def toggle_auto_start(icon, item):
    if is_auto_start_enabled():
        disable_auto_start()
    else:
        enable_auto_start()
    
    save_settings()
    # Redraw the icon to reflect the updated state
    icon.update_menu()

def is_auto_start_enabled():
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    try:
        reg_key = winreg.OpenKey(reg, key, 0, winreg.KEY_READ)
        value, regtype = winreg.QueryValueEx(reg_key, 'EyeCareReminder')
        winreg.CloseKey(reg_key)
        if value == os.path.abspath(sys.argv[0]):
            return True
        return False
    except FileNotFoundError:
        return False

def show_custom_message_dialog():
    global reminder_message
    try:
        dialog = tk.Toplevel(root)
        dialog.title("Set Message")
        dialog.transient(root)
        dialog.grab_set()
        
        # Center the dialog on screen
        center_window(dialog, 400, 150)
        
        # Set the icon for the dialog
        icon_path = os.path.join(get_resource_path(), "eyecare.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)
        
        # Make it topmost
        dialog.attributes('-topmost', True)
        dialog.lift()
        dialog.focus_force()
        
        # Label
        label = tk.Label(dialog, text="Enter the reminder message:", font=("Arial", 10))
        label.pack(pady=10)
        
        # Entry widget with explicit colors
        entry = tk.Entry(dialog, width=50, font=("Arial", 10), fg="black", bg="white", insertbackground="black")
        entry.pack(pady=10)
        entry.insert(0, reminder_message)
        dialog.after(100, lambda: entry.focus_force())
        
        def on_ok():
            global reminder_message
            new_message = entry.get().strip()
            # Use default message if empty
            reminder_message = new_message if new_message else default_message
            save_settings()
            dialog.destroy()
        
        def on_cancel():
            dialog.destroy()
        
        # Buttons frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ok_button = tk.Button(button_frame, text="OK", command=on_ok, width=10)
        ok_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = tk.Button(button_frame, text="Cancel", command=on_cancel, width=10)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to OK
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

    except Exception as e:
        print(f"An error occurred while setting the custom message: {e}")

def set_custom_message():
    root.after(0, show_custom_message_dialog)

def show_schedule_dialog():
    global schedule_enabled, schedule_start, schedule_end
    try:
        dialog = tk.Toplevel(root)
        dialog.title("Set Schedule")
        dialog.transient(root)
        dialog.grab_set()
        center_window(dialog, 320, 240)

        icon_path = os.path.join(get_resource_path(), "eyecare.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)

        dialog.attributes('-topmost', True)
        dialog.lift()
        dialog.focus_force()

        # Enable / disable checkbox
        enabled_var = tk.BooleanVar(value=schedule_enabled)
        tk.Checkbutton(dialog, text="Enable schedule", variable=enabled_var,
                       font=("Arial", 10)).pack(pady=(15, 5))

        # Parse saved times
        try:
            start_h, start_m = schedule_start.split(":")
            end_h, end_m = schedule_end.split(":")
        except Exception:
            start_h, start_m = "09", "00"
            end_h, end_m = "18", "00"

        def make_time_row(parent, label_text, h_val, m_val):
            frame = tk.Frame(parent)
            frame.pack(pady=4)
            tk.Label(frame, text=label_text, font=("Arial", 10),
                     width=10, anchor='e').pack(side=tk.LEFT)
            h_spin = tk.Spinbox(frame, from_=0, to=23, width=3, format="%02.0f",
                                font=("Arial", 10), fg="black", bg="white")
            h_spin.delete(0, tk.END)
            h_spin.insert(0, h_val)
            h_spin.pack(side=tk.LEFT, padx=(5, 0))
            tk.Label(frame, text=":", font=("Arial", 10)).pack(side=tk.LEFT)
            m_spin = tk.Spinbox(frame, from_=0, to=59, width=3, format="%02.0f",
                                font=("Arial", 10), fg="black", bg="white")
            m_spin.delete(0, tk.END)
            m_spin.insert(0, m_val)
            m_spin.pack(side=tk.LEFT)
            return h_spin, m_spin

        sh_spin, sm_spin = make_time_row(dialog, "Start time:", start_h, start_m)
        eh_spin, em_spin = make_time_row(dialog, "End time:", end_h, end_m)

        tk.Label(dialog, text="(24-hour format. Reminders only fire\nduring this window.)",
                 font=("Arial", 8), fg="gray").pack(pady=(4, 0))

        def on_ok():
            global schedule_enabled, schedule_start, schedule_end
            try:
                sh = int(sh_spin.get()) % 24
                sm = int(sm_spin.get()) % 60
                eh = int(eh_spin.get()) % 24
                em = int(em_spin.get()) % 60
                schedule_start = f"{sh:02d}:{sm:02d}"
                schedule_end = f"{eh:02d}:{em:02d}"
                schedule_enabled = enabled_var.get()
                save_settings()
                logger.info(f"Schedule saved: enabled={schedule_enabled}, {schedule_start}–{schedule_end}")
            except Exception as e:
                logger.error(f"Error saving schedule: {e}")
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="OK", command=on_ok, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)

        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())

    except Exception as e:
        logger.error(f"Error showing schedule dialog: {e}")

def set_schedule():
    root.after(0, show_schedule_dialog)

def test_reminder():
    """Test function to show reminder immediately without waiting"""
    global current_timer
    
    # Cancel the current scheduled timer to prevent double triggers
    if current_timer:
        current_timer.cancel()
        current_timer = None
        logger.info("Cancelled existing timer for test reminder")
    
    # Queue reminder to run on main thread
    main_thread_queue.put(("show_reminder", None))
    logger.info("Test reminder queued for main thread")

def restore_defaults():
    global interval_minutes, selected_interval, reminder_message
    global schedule_enabled, schedule_start, schedule_end
    interval_minutes = default_interval_minutes
    selected_interval = "20 minutes"
    reminder_message = default_message
    schedule_enabled = False
    schedule_start = "09:00"
    schedule_end = "21:00"
    save_settings()

def setup_tray_icon():
    logger.info("Setting up tray icon...")
    interval_menu = Menu(
        MenuItem("1 minute", lambda: set_interval(1, "1 minute"), checked=lambda item: is_selected_interval("1 minute")),
        MenuItem("20 minutes", lambda: set_interval(20, "20 minutes"), checked=lambda item: is_selected_interval("20 minutes")),
        MenuItem("25 minutes", lambda: set_interval(25, "25 minutes"), checked=lambda item: is_selected_interval("25 minutes")),
        MenuItem("30 minutes", lambda: set_interval(30, "30 minutes"), checked=lambda item: is_selected_interval("30 minutes")),
        MenuItem("60 minutes", lambda: set_interval(60, "60 minutes"), checked=lambda item: is_selected_interval("60 minutes")),
        MenuItem("Custom...", set_custom_interval, checked=lambda item: selected_interval.startswith("Custom"))
    )

    # Load the icon from the ico file
    icon_path = os.path.join(get_resource_path(), "eyecare.ico")
    logger.info(f"Icon path: {icon_path}")
    if os.path.exists(icon_path):
        icon_image = Image.open(icon_path)
        logger.info("Icon loaded from file")
    else:
        icon_image = create_image()
        logger.warning("Icon file not found, using generated image")
    
    icon = Icon("EyeCare", icon_image, menu=Menu(
        MenuItem("Start", start_timer, enabled=lambda item: is_paused),
        MenuItem("Pause", pause_timer, enabled=lambda item: not is_paused),
        MenuItem('Auto Start', toggle_auto_start, checked=lambda item: is_auto_start_enabled()),
        MenuItem("Message", set_custom_message),
        MenuItem("Reminder Interval", interval_menu),
        MenuItem("Schedule", set_schedule, checked=lambda item: schedule_enabled),
        MenuItem("Restore Default", restore_defaults),
        Menu.SEPARATOR,
        MenuItem("Test Reminder", test_reminder),
        MenuItem("Check for Update", check_updates_manually),
        MenuItem("Developer", open_developer_page),
        MenuItem("Restart", lambda icon, item: restart_app(icon, item)),
        MenuItem("Quit", lambda icon, item: quit_app(icon, item))
    ))

    icon.run()

def run_tray_icon():
    Thread(target=setup_tray_icon, daemon=True).start()

def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
    draw.ellipse((width // 4, height // 4, 3 * width // 4, 3 * height // 4), fill=(255, 255, 255))
    return image

def restart_app(icon, item):
    global app_running
    app_running = False
    icon.stop()
    # Restart the application
    os.execv(sys.executable, [sys.executable] + sys.argv)

def quit_app(icon, item):
    global app_running
    logger.info("Application shutting down...")
    app_running = False
    try:
        icon.stop()
    except:
        pass
    try:
        root.quit()
    except:
        pass

# Set up the main Tkinter window (hidden, only for dialogs)
root = tk.Tk()
root.withdraw()

# Load saved settings
load_settings()

# Check for updates on startup
logger.info(f"Current version: {CURRENT_VERSION}")
check_updates_on_startup()

# Start the tray icon
run_tray_icon()

# Start the timer
start_timer()

# Process queued commands on the main thread using tkinter's event loop
def process_queue():
    try:
        command = main_thread_queue.get_nowait()
        if command[0] == "show_reminder":
            show_webview_reminder()
    except queue.Empty:
        pass
    except Exception as e:
        logger.error(f"Error processing queue: {e}", exc_info=True)
    finally:
        if app_running:
            root.after(100, process_queue)

logger.info("Application main loop starting...")
try:
    process_queue()
    root.mainloop()
except KeyboardInterrupt:
    logger.info("Application interrupted by user (Ctrl+C)")
    print("\nShutting down gracefully...")
except Exception as e:
    logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
finally:
    logger.info("Application closed")
    # Cancel any pending timer
    if current_timer:
        current_timer.cancel()
    try:
        root.destroy()
    except:
        pass
