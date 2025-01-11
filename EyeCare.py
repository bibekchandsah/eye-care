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

# Global variables
default_interval_minutes = 20
default_message = "Have a look far away from your current screen to protect your beautiful eyes"

interval_minutes = default_interval_minutes
selected_interval = "20 minutes"
is_paused = False
auto_start_enabled = False
reminder_message = default_message

def show_message():
    if is_paused:
        return
    
    msg_window = tk.Toplevel(root)
    msg_window.title("Reminder")
    msg_window.geometry("300x100")
    msg_window.configure(bg='black')
    msg_window.attributes('-fullscreen', True)

    label = tk.Label(msg_window, text=reminder_message,
                     font=("Helvetica", 24), fg="white", bg="black")
    label.pack(expand=True)

    countdown_label = tk.Label(msg_window, text="20", font=("Helvetica", 48), fg="white", bg="black")
    countdown_label.pack()

    scheduled = False

    def countdown(count):
        nonlocal scheduled
        countdown_label.config(text=str(count))
        if count > 0:
            if count < 10:
                transparency = (count / 10)
                msg_window.attributes('-alpha', transparency)
            msg_window.after(1000, countdown, count - 1)
        else:
            if msg_window.winfo_exists():
                msg_window.destroy()
            if not scheduled:
                root.after(interval_minutes * 60 * 1000, show_message)
                scheduled = True

    def on_close():
        nonlocal scheduled
        if not scheduled:
            root.after(interval_minutes * 60 * 1000, show_message)
            scheduled = True
        msg_window.destroy()

    context_menu = tk.Menu(msg_window, tearoff=0)
    context_menu.add_command(label="Close", command=on_close)

    def show_context_menu(event):
        context_menu.tk_popup(event.x_root, event.y_root)

    msg_window.bind("<Button-3>", show_context_menu)
    msg_window.protocol("WM_DELETE_WINDOW", on_close)

    countdown(20)

def set_interval(minutes, label):
    global interval_minutes, selected_interval
    interval_minutes = minutes
    selected_interval = label

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

def toggle_auto_start(icon, item):
    key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
    reg_key = winreg.OpenKey(reg, key, 0, winreg.KEY_SET_VALUE)
    
    if is_auto_start_enabled():
        # Remove from registry
        winreg.DeleteValue(reg_key, 'EyeCareReminder')
        print("Auto Start Disabled")
    else:
        # Add the .exe directly to registry for auto start
        exe_path = os.path.abspath(sys.argv[0])  # Get the absolute path of the .exe
        winreg.SetValueEx(reg_key, 'EyeCareReminder', 0, winreg.REG_SZ, exe_path)
        print("Auto Start Enabled")
    
    winreg.CloseKey(reg_key)
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

def set_custom_message():
    global reminder_message
    try:
        temp_root = tk.Tk()
        temp_root.withdraw()

        custom_message = simpledialog.askstring("Set Message", "Enter the reminder message:", parent=temp_root)
        temp_root.destroy()

        if custom_message:
            reminder_message = custom_message

    except Exception as e:
        print(f"An error occurred while setting the custom message: {e}")

def restore_defaults():
    global interval_minutes, selected_interval, reminder_message
    interval_minutes = default_interval_minutes
    selected_interval = "20 minutes"
    reminder_message = default_message

def setup_tray_icon():
    interval_menu = Menu(
        # MenuItem("1 minute", lambda: set_interval(1, "1 minute"), checked=lambda item: is_selected_interval("1 minute")),
        MenuItem("20 minutes", lambda: set_interval(20, "20 minutes"), checked=lambda item: is_selected_interval("20 minutes")),
        MenuItem("25 minutes", lambda: set_interval(25, "25 minutes"), checked=lambda item: is_selected_interval("25 minutes")),
        MenuItem("30 minutes", lambda: set_interval(30, "30 minutes"), checked=lambda item: is_selected_interval("30 minutes")),
        MenuItem("60 minutes", lambda: set_interval(60, "60 minutes"), checked=lambda item: is_selected_interval("60 minutes")),
        MenuItem("Custom...", set_custom_interval, checked=lambda item: selected_interval.startswith("Custom"))
    )

    icon = Icon("EyeCare", create_image(), menu=Menu(
        MenuItem("Start", start_timer, enabled=lambda item: is_paused),
        MenuItem("Pause", pause_timer, enabled=lambda item: not is_paused),
        MenuItem('Auto Start', toggle_auto_start, checked=lambda item: is_auto_start_enabled()),
        MenuItem("Message", set_custom_message),
        MenuItem("Reminder Interval", interval_menu),
        MenuItem("Restore Default", restore_defaults),
        Menu.SEPARATOR,
        MenuItem("Developer", open_developer_page),
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

def quit_app(icon, item):
    icon.stop()
    root.quit()

# Set up the main Tkinter window
root = tk.Tk()
root.withdraw()

# Start the tray icon
run_tray_icon()

# Start the timer
start_timer()

# Start the Tkinter main loop
root.mainloop()
