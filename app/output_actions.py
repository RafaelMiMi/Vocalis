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
        method = kwargs.get("paste_method", "auto")
        
        # Always copy to clipboard first
        ClipboardAction().execute(text)
        
        # Give clipboard time to settle/sync (critical for Wayland)
        time.sleep(0.3)
        
        if method == "copy_only":
            self._notify("Text copied to clipboard.")
            return

        session_type = os.environ.get("XDG_SESSION_TYPE")
        
        if session_type == "wayland":
            logger.info(f"Wayland paste requested. Method: {method}")
            
            # Method: Type (ydotool)
            if method == "type" or (method == "auto" and shutil.which("ydotool")):
                 if self._try_ydotool(text): return
                 if method == "type": # Failed but requested explicitly
                     self._notify("ydotool failed. Text in clipboard.")
                     return

            # Method: Ctrl+V (wtype)
            if method == "ctrl_v" or (method == "auto" and shutil.which("wtype")):
                if self._try_wtype(): return
                if method == "ctrl_v":
                    self._notify("wtype failed. Text in clipboard.")
                    return
            
            # Fallback for Auto
            self._notify("Text copied. Press Ctrl+V (Auto-paste failed).")
            
        else:
            # X11 or other
            try:
                # X11 doesn't distinguish much, usually xdotool key ctrl+v is best
                # forcing type could be done via xdotool type
                if method == "type":
                    subprocess.run(["xdotool", "type", "--delay", "1", text], check=True)
                else:
                    time.sleep(0.1)
                    subprocess.run(["xdotool", "key", "ctrl+v"], check=True)
            except Exception as e:
                logger.error(f"X11 paste failed: {e}")
                self._notify("Paste failed. Text in clipboard.")

    def _try_wtype(self):
        try:
            # wtype -M ctrl -k v -m ctrl
            res = subprocess.run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"], check=False)
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"wtype exception: {e}")
            return False

    def _try_ydotool(self, text):
        if not shutil.which("ydotool"): return False
        try:
            # Check if ydotool works (it needs daemon)
            # Actually, just try running it.
            # Adding a small delay to ensure focus is correct? 
            # Or pass delay to ydotool (key -d)? type doesn't have delay.
            # We can rely on global delay we added above.
            subprocess.run(["ydotool", "type", text], check=False)
            return True
        except Exception as e:
            logger.warning(f"ydotool exception: {e}")
            return False

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
