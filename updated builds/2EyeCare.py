# added custom and more time interval for remainder message

import tkinter as tk
from tkinter import simpledialog
import time
from threading import Thread
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw

# Global variable to keep track of the time interval
interval_minutes = 1

# To keep track of the selected menu item
selected_interval = "1 minute"

def show_message():
    # Create a new window for the message
    msg_window = tk.Toplevel(root)
    msg_window.title("Reminder")
    msg_window.geometry("300x100")
    msg_window.configure(bg='black')
    msg_window.attributes('-fullscreen', True)  # Make the window full screen

    # Display the message in white text
    label = tk.Label(msg_window, text="Have a look far away from your current screen to protect your beautiful eyes",
                     font=("Helvetica", 24), fg="white", bg="black")
    label.pack(expand=True)

    # Label to display the countdown
    countdown_label = tk.Label(msg_window, text="20", font=("Helvetica", 48), fg="white", bg="black")
    countdown_label.pack()

    # Variable to track if the next message is already scheduled
    scheduled = False

    # Countdown function
    def countdown(count):
        nonlocal scheduled
        # Update the countdown label
        countdown_label.config(text=str(count))
        if count > 0:
            # Adjust transparency if less than 10 seconds
            if count < 10:
                transparency = (count / 10)  # Calculate transparency from 0.9 to 0.1 (90% to 10% opaque)
                msg_window.attributes('-alpha', transparency)
            # Call the countdown function again after 1 second
            msg_window.after(1000, countdown, count - 1)
        else:
            if msg_window.winfo_exists():  # Check if the window is still open
                msg_window.destroy()
            if not scheduled:
                root.after(interval_minutes * 60 * 1000, show_message)  # Schedule the next message
                scheduled = True

    # Schedule the next message if closed manually
    def on_close():
        nonlocal scheduled
        if not scheduled:
            root.after(interval_minutes * 60 * 1000, show_message)  # Schedule the next message
            scheduled = True
        msg_window.destroy()

    # Create a context menu with a "Close" option
    context_menu = tk.Menu(msg_window, tearoff=0)
    context_menu.add_command(label="Close", command=on_close)

    # Function to show the context menu on right-click
    def show_context_menu(event):
        context_menu.tk_popup(event.x_root, event.y_root)

    # Bind right-click event to the context menu
    msg_window.bind("<Button-3>", show_context_menu)

    # Bind the manual close event to on_close
    msg_window.protocol("WM_DELETE_WINDOW", on_close)

    # Start the countdown from 20 seconds
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
    # Use root.after to call prompt_custom_interval in the Tkinter main thread
    root.after(0, prompt_custom_interval)

def is_selected_interval(label):
    return selected_interval == label

def start_timer():
    # Start the first reminder after the chosen interval
    root.after(interval_minutes * 60 * 1000, show_message)

def create_image():
    # Generate an image for the system tray icon
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

def setup_tray_icon():
    # Create a submenu for the reminder intervals with checkmarks
    interval_menu = Menu(
        MenuItem("1 minute", lambda: set_interval(1, "1 minute"), checked=lambda item: is_selected_interval("1 minute")),
        MenuItem("20 minutes", lambda: set_interval(20, "20 minutes"), checked=lambda item: is_selected_interval("20 minutes")),
        MenuItem("25 minutes", lambda: set_interval(25, "25 minutes"), checked=lambda item: is_selected_interval("25 minutes")),
        MenuItem("30 minutes", lambda: set_interval(30, "30 minutes"), checked=lambda item: is_selected_interval("30 minutes")),
        MenuItem("Custom...", set_custom_interval, checked=lambda item: selected_interval.startswith("Custom"))
    )

    # Create the system tray icon with the main menu
    icon = Icon("EyeCare", create_image(), menu=Menu(
        MenuItem("Reminder Interval", interval_menu),  # Dropdown for interval selection
        MenuItem("Quit", lambda icon, item: quit_app(icon, item))
    ))

    icon.run()

def run_tray_icon():
    # Run the system tray icon in a separate thread
    Thread(target=setup_tray_icon).start()

# Set up the main Tkinter window
root = tk.Tk()
root.withdraw()  # Hide the main window

# Start the tray icon
run_tray_icon()

# Start the timer
start_timer()

# Start the Tkinter main loop
root.mainloop()

