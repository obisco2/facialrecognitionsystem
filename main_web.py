import os
import sys
import socket
import threading
import time
import logging
import base64
import uvicorn
import webview

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from core.backend import app, streamer

class Api:
    """Exposed to JavaScript via window.pywebview.api."""

    def save_file(self, filename, content_b64, mime):
        """Show native Save As dialog and write file."""
        try:
            ext = os.path.splitext(filename)[1]
            if ext == '.xlsx':
                file_types = (('Excel Workbook', '*.xlsx'), ('All Files', '*.*'))
            else:
                file_types = (('CSV File', '*.csv'), ('All Files', '*.*'))

            result = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=filename,
                file_types=file_types,
            )
            if result:
                path = result if isinstance(result, str) else result[0]
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(content_b64))
                logging.info(f"File saved: {path}")
                return True
            return False
        except Exception as e:
            logging.error(f"save_file error: {e}")
            return False

def find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_backend(port: int):
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

def on_closing():
    # Gracefully release camera stream before window shuts down
    streamer.stop()

if __name__ == "__main__":
    port = find_free_port()
    
    # Start uvicorn server in a daemon thread
    server_thread = threading.Thread(target=start_backend, args=(port,), daemon=True)
    server_thread.start()
    
    # Give the server a small moment to bind to the port
    time.sleep(0.5)

    # Initialize pywebview window with API exposed to JS
    api = Api()
    window = webview.create_window(
        title="AttendIQ — Facial Recognition Attendance System",
        url=f"http://127.0.0.1:{port}",
        width=1400,
        height=850,
        min_size=(1200, 700),
        background_color="#0f0f1a",
        js_api=api,
    )
    
    # Bind window close event handler
    window.events.closing += on_closing
    
    # Start webview loop with debug enabled
    webview.start(debug=True)
