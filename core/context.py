import logging
import shutil
import subprocess
try:
    import pyperclip
except ImportError:
    pyperclip = None

logger = logging.getLogger(__name__)

class ContextManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def get_clipboard(self) -> str:
        """
        Retrieves clipboard content safely.
        Respects 'allow_clipboard_access' config.
        Tries pyperclip first, then falls back to wl-paste (Wayland).
        """
        config = self.config_manager.get()
        if not getattr(config, "allow_clipboard_access", True):
            logger.info("Clipboard access denied by settings.")
            return "[Clipboard Access Denied]"

        content = ""
        
        # Strategy 1: pyperclip
        if pyperclip:
            try:
                content = pyperclip.paste()
            except Exception as e:
                logger.debug(f"pyperclip failed: {e}")
        
        # Strategy 2: wl-paste (if empty or failed, and on Wayland)
        if not content and shutil.which("wl-paste"):
            try:
                res = subprocess.run(
                    ["wl-paste", "--no-newline"], 
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    content = res.stdout
            except Exception as e:
                logger.debug(f"wl-paste failed: {e}")

        return content if content else ""
