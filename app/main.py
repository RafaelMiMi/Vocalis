import sys
import os
import logging
import argparse
import time
from app import output_actions
from core.config import ConfigManager
from core.ipc import send_signal
from core.audio import AudioRecorder

# Setup logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Vocalis")

def main():
    parser = argparse.ArgumentParser(description="Vocalis - Voice to Text Assistant")
    parser.add_argument("--listen", action="store_true", help="Trigger one-shot listening immediately")
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
        from app.ui import run_ui
        run_ui()
        return

    # Default if no args
    parser.print_help()

if __name__ == "__main__":
    main()
