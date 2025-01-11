# works well with all required featrues just adding context menu in system tray is left
import tkinter as tk

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
                root.after(60 * 1000, show_message)  # Schedule the next message
                scheduled = True

    # Schedule the next message if closed manually
    def on_close():
        nonlocal scheduled
        if not scheduled:
            root.after(60 * 1000, show_message)  # Schedule the next message
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

def start_timer():
    # Start the first reminder after 1 minute
    root.after(60 * 1000, show_message)

# Set up the main Tkinter window
root = tk.Tk()
root.withdraw()  # Hide the main window

# Start the timer
start_timer()

# Start the Tkinter main loop
root.mainloop()
