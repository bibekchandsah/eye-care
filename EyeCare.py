import tkinter as tk
from tkinter import simpledialog
import time
from threading import Thread
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import webbrowser
import os
import sys
import winreg
import json
import webview
import ctypes
import logging
from datetime import datetime

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

# Settings file path
settings_file = os.path.join(get_app_path(), "settings.json")
logger.info(f"Settings file: {settings_file}")

def load_settings():
    global interval_minutes, selected_interval, reminder_message
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
            'auto_start': is_auto_start_enabled()
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

def show_message():
    logger.info("show_message() called")
    if is_paused:
        logger.info("Timer is paused, skipping reminder")
        return
    
    def show_html_window():
        logger.info("show_html_window() starting")
        # Create a temporary HTML file with the custom message and countdown
        html_path = os.path.join(get_resource_path(), "index.html")
        logger.info(f"HTML path: {html_path}")
        
        # Read the original HTML file
        try:
            if not os.path.exists(html_path):
                logger.error(f"index.html not found at: {html_path}")
                root.after(interval_minutes * 60 * 1000, show_message)
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
            
            # JavaScript API for closing the window
            class Api:
                def close_window(self):
                    logger.info("close_window API called")
                    try:
                        for window in webview.windows:
                            window.destroy()
                    except Exception as e:
                        logger.error(f"Error in close_window: {e}")
            
            api = Api()
            
            # Create and show webview window in fullscreen
            logger.info("Creating webview window...")
            window = webview.create_window(
                'Eye Care Reminder',
                temp_html_path,
                fullscreen=True,
                frameless=True,
                on_top=True,
                js_api=api
            )
            logger.info("Webview window created")
            
            # Function to bring window to front using Windows API
            def bring_to_front():
                time.sleep(0.5)
                try:
                    if webview.windows:
                        webview.windows[0].on_top = True
                        # Use Windows API to force foreground
                        user32 = ctypes.windll.user32
                        hwnd = user32.GetForegroundWindow()
                        # Get all windows and find ours
                        user32.keybd_event(0, 0, 0, 0)  # Simulate key press to allow SetForegroundWindow
                        time.sleep(0.1)
                        webview.windows[0].on_top = True
                        logger.info("Window brought to front")
                except Exception as e:
                    logger.error(f"Error bringing window to front: {e}")
            
            # Auto-close after 20 seconds
            def auto_close():
                logger.info("Auto-close timer started (20 seconds)")
                time.sleep(20)
                try:
                    for w in webview.windows:
                        w.destroy()
                    logger.info("Window auto-closed")
                except Exception as e:
                    logger.error(f"Error in auto-close: {e}")
            
            # Start threads
            focus_thread = Thread(target=bring_to_front, daemon=True)
            focus_thread.start()
            
            close_thread = Thread(target=auto_close, daemon=True)
            close_thread.start()
            
            logger.info("Starting webview...")
            webview.start()
            logger.info("Webview closed")
            
            # Clean up temp file
            try:
                if os.path.exists(temp_html_path):
                    os.remove(temp_html_path)
                    logger.info("Temp file cleaned up")
            except Exception as e:
                logger.warning(f"Could not remove temp file: {e}")
            
            # Schedule next reminder after webview closes
            logger.info(f"Scheduling next reminder in {interval_minutes} minutes")
            root.after(interval_minutes * 60 * 1000, show_message)
                
        except Exception as e:
            logger.error(f"Error showing HTML reminder: {e}", exc_info=True)
            print(f"Error showing HTML reminder: {e}")
            # Fallback to schedule next reminder
            root.after(interval_minutes * 60 * 1000, show_message)
    
    # Schedule to run on main thread
    root.after(100, show_html_window)

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
    root.after(interval_minutes * 60 * 1000, show_message)

def pause_timer():
    global is_paused
    is_paused = True

def open_developer_page():
    webbrowser.open("https://bibekchandsah.com.np/developer.html")

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

def test_reminder():
    """Test function to show reminder immediately without waiting"""
    show_message()

def restore_defaults():
    global interval_minutes, selected_interval, reminder_message
    interval_minutes = default_interval_minutes
    selected_interval = "20 minutes"
    reminder_message = default_message
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
        MenuItem("Restore Default", restore_defaults),
        Menu.SEPARATOR,
        MenuItem("Test Reminder", test_reminder),
        MenuItem("Developer", open_developer_page),
        MenuItem("Restart", lambda icon, item: restart_app(icon, item)),
        MenuItem("Quit", lambda icon, item: quit_app(icon, item))
    ))

    icon.run()

def run_tray_icon():
    Thread(target=setup_tray_icon).start()

def create_image():
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill=(0, 0, 0))
    draw.ellipse((width // 4, height // 4, 3 * width // 4, 3 * height // 4), fill=(255, 255, 255))
    return image

def restart_app(icon, item):
    icon.stop()
    root.quit()
    # Restart the application
    os.execv(sys.executable, [sys.executable] + sys.argv)

def quit_app(icon, item):
    logger.info("Application shutting down...")
    try:
        icon.stop()
    except:
        pass
    try:
        root.quit()
    except:
        pass

# Set up the main Tkinter window
root = tk.Tk()
root.withdraw()

# Load saved settings
load_settings()

# Start the tray icon
run_tray_icon()

# Start the timer
start_timer()

# Start the Tkinter main loop with exception handling
try:
    root.mainloop()
except KeyboardInterrupt:
    logger.info("Application interrupted by user (Ctrl+C)")
    print("\nShutting down gracefully...")
except Exception as e:
    logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
finally:
    logger.info("Application closed")
    try:
        root.destroy()
    except:
        pass
