"""
Separate process for showing the reminder window.
This runs independently so the main EyeCare app stays responsive.
"""
import webview
import sys
import os
import time
import ctypes
from threading import Thread

def main():
    if len(sys.argv) < 2:
        print("Usage: reminder_window.py <html_file_path>")
        sys.exit(1)
    
    html_path = sys.argv[1]
    
    if not os.path.exists(html_path):
        print(f"HTML file not found: {html_path}")
        sys.exit(1)
    
    # JavaScript API for closing the window
    class Api:
        def close_window(self):
            try:
                for window in webview.windows:
                    window.destroy()
            except Exception as e:
                print(f"Error in close_window: {e}")
    
    api = Api()
    
    # Create webview window
    window = webview.create_window(
        'Eye Care Reminder',
        html_path,
        fullscreen=True,
        frameless=True,
        on_top=True,
        js_api=api
    )
    
    # Function to bring window to front using Windows API
    def bring_to_front():
        time.sleep(0.5)
        try:
            if webview.windows:
                webview.windows[0].on_top = True
                user32 = ctypes.windll.user32
                user32.keybd_event(0, 0, 0, 0)
                time.sleep(0.1)
                webview.windows[0].on_top = True
        except Exception as e:
            print(f"Error bringing window to front: {e}")
    
    # Auto-close after 20 seconds
    def auto_close():
        time.sleep(20)
        try:
            for w in webview.windows:
                w.destroy()
        except Exception as e:
            print(f"Error in auto-close: {e}")
    
    # Start helper threads
    Thread(target=bring_to_front, daemon=True).start()
    Thread(target=auto_close, daemon=True).start()
    
    # Start webview (blocks until closed)
    webview.start(gui='edgechromium')

if __name__ == '__main__':
    main()
