import sys
import os
import logging
import argparse
import time
from app import output_actions
from core.config import ConfigManager
from core.ipc import send_signal
from core.audio import AudioRecorder

import socket

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Vocalis")

def ensure_single_instance():
    # Use abstract namespace socket (Linux) or file-based (macOS)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    
    if sys.platform == "linux":
        # Abstract namespace (no file cleanup needed)
        socket_path = '\0vocalis_instance_lock'
    else:
        # File based (macOS/BSD)
        socket_path = os.path.join(os.path.expanduser("~/.vocalis_lock"))
        # Clean up stale socket if it exists but connection fails
        if os.path.exists(socket_path):
            try:
                 # Try connecting to see if it's active
                check_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                check_sock.connect(socket_path)
                check_sock.close()
                # If connected, it's alive
                logger.error("Another instance is already running.")
                print("Vocalis is already running.")
                sys.exit(1)
            except ConnectionRefusedError:
                # Stale socket, remove it
                logger.info("Removing stale lock file.")
                os.unlink(socket_path)

    try:
        sock.bind(socket_path)
        logger.info(f"Single instance lock acquired: {socket_path}")
        return sock  # Keep socket open
    except socket.error as e:
        logger.error(f"Another instance is already running: {e}")
        print("Vocalis is already running.")
        sys.exit(1)

def main():


    parser = argparse.ArgumentParser(description="Vocalis - Voice to Text Assistant")
    parser.add_argument("--listen", action="store_true", help="Trigger one-shot listening immediately")
    parser.add_argument("--mode", type=str, help="Switch running instance to specific mode ID")
    parser.add_argument("--record-test", action="store_true", help="Test audio recording only")
    parser.add_argument("--gui", action="store_true", help="Start the GUI/Tray")
    
    args = parser.parse_args()
    
    config_manager = ConfigManager()
    config = config_manager.get()

    if args.record_test:
        logger.info("Testing audio recording (5 seconds)...")
        rec = AudioRecorder(device_index=config.input_device)
        path = rec.record_once(max_duration=5)
        logger.info(f"Recorded to {path}")
        return

    if args.mode:
        logger.info(f"Switching mode to '{args.mode}'...")
        if send_signal(f"SET_MODE:{args.mode}"):
            logger.info("Signal sent successfully.")
        else:
            logger.error("Could not connect to Vocalis. Is the GUI application running?")
        return

    if args.listen:
        # CLI Trigger mode (for Wayland shortcuts)
        logger.info("Sending trigger signal to Vocalis App...")
        
        if send_signal("TOGGLE"):
            logger.info("Signal sent successfully.")
        else:
            logger.error("Could not connect to Vocalis. Is the GUI application running?")
            logger.error("Please start 'vocalis --gui' first.")
        
        return

    if args.gui:
        # Check single instance only for GUI
        sock = ensure_single_instance()
        from app.ui import run_ui
        run_ui()
        return

    # Default if no args
    parser.print_help()

if __name__ == "__main__":
    main()
