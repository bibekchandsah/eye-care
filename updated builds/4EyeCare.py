# added start | pause | developer | auto start option in system tray

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
interval_minutes = 1
selected_interval = "1 minute"
is_paused = False
auto_start_enabled = False

def show_message():
    if is_paused:
        return
    
    msg_window = tk.Toplevel(root)
    msg_window.title("Reminder")
    msg_window.geometry("300x100")
    msg_window.configure(bg='black')
    msg_window.attributes('-fullscreen', True)

    label = tk.Label(msg_window, text="Have a look far away from your current screen to protect your beautiful eyes",
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

def manage_auto_start(enable):
    global auto_start_enabled
    auto_start_enabled = enable
    file_path = os.path.realpath(sys.argv[0])
    key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "EyeCareReminder"

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as reg_key:
        if enable:
            winreg.SetValueEx(reg_key, app_name, 0, winreg.REG_SZ, file_path)
        else:
            try:
                winreg.DeleteValue(reg_key, app_name)
            except FileNotFoundError:
                pass

def setup_tray_icon():
    interval_menu = Menu(
        MenuItem("1 minute", lambda: set_interval(1, "1 minute"), checked=lambda item: is_selected_interval("1 minute")),
        MenuItem("20 minutes", lambda: set_interval(20, "20 minutes"), checked=lambda item: is_selected_interval("20 minutes")),
        MenuItem("25 minutes", lambda: set_interval(25, "25 minutes"), checked=lambda item: is_selected_interval("25 minutes")),
        MenuItem("30 minutes", lambda: set_interval(30, "30 minutes"), checked=lambda item: is_selected_interval("30 minutes")),
        MenuItem("Custom...", set_custom_interval, checked=lambda item: selected_interval.startswith("Custom"))
    )

    icon = Icon("EyeCare", create_image(), menu=Menu(
        MenuItem("Start", start_timer, enabled=lambda item: is_paused),
        MenuItem("Pause", pause_timer, enabled=lambda item: not is_paused),
        MenuItem("Developer", open_developer_page),
        MenuItem("Auto Start", lambda icon, item: manage_auto_start(item.checked), checked=lambda item: auto_start_enabled),
        MenuItem("Reminder Interval", interval_menu),
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
