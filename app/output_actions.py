import pyperclip
import logging
import subprocess
import os
import time
import shutil
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class OutputAction(ABC):
    @abstractmethod
    def execute(self, text: str, **kwargs):
        pass

class ClipboardAction(OutputAction):
    def execute(self, text: str, **kwargs):
        try:
            pyperclip.copy(text)
            logger.info("Copied to clipboard.")
        except Exception as e:
            logger.error(f"Clipboard copy failed: {e}")

class PasteAction(OutputAction):
    def execute(self, text: str, **kwargs):
        # First ensure it's in clipboard using the shared logic
        ClipboardAction().execute(text)
        
        session_type = os.environ.get("XDG_SESSION_TYPE")
        
        if session_type == "wayland":
            logger.info("Wayland paste requested.")
            
            # Try ydotool if installed
            if shutil.which("ydotool"):
                try:
                    # ydotool key 29:1 47:1 47:0 29:0  (Ctrl down, V down, V up, Ctrl up)
                    # Key codes: 29=KEY_LEFTCTRL, 47=KEY_V
                    subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=False)
                    return
                except Exception as e:
                    logger.warning(f"ydotool failed: {e}")

            # Fallback
            self._notify("Text copied. Press Ctrl+V.")
        else:
            # X11 fallback
            try:
                time.sleep(0.1)
                subprocess.run(["xdotool", "key", "ctrl+v"], check=True)
            except Exception as e:
                logger.error(f"X11 paste failed: {e}")
                self._notify("Paste failed. Text in clipboard.")

    def _notify(self, message):
         try:
            subprocess.run(["notify-send", "Vocalis", message], check=False)
         except:
            pass

class FileAction(OutputAction):
    def execute(self, text: str, **kwargs):
        file_path = kwargs.get("file_path")
        if not file_path:
            logger.error("File action requested but no file path provided.")
            return

        expanded_path = os.path.expanduser(file_path)
        
        try:
            os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
            with open(expanded_path, "a") as f:
                timestamp = time.strftime("[%H:%M:%S] ")
                f.write(f"\n{timestamp}{text}\n")
            
            ClipboardAction().execute(text) 
            self._notify(f"Appended to {os.path.basename(expanded_path)}")
        except Exception as e:
            logger.error(f"File write failed: {e}")
            self._notify(f"Failed to write to file: {e}")

    def _notify(self, message):
         try:
            subprocess.run(["notify-send", "Vocalis", message], check=False)
         except:
            pass

class ActionFactory:
    @staticmethod
    def get_action(action_type: str) -> OutputAction:
        if action_type == "paste":
            return PasteAction()
        elif action_type == "file":
            return FileAction()
        else:
            return ClipboardAction()

def execute(action_type: str, text: str, **kwargs):
    action = ActionFactory.get_action(action_type)
    action.execute(text, **kwargs)
