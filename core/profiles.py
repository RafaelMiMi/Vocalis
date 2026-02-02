import logging
import subprocess
import shutil
import sys

logger = logging.getLogger(__name__)

class ProfileManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def detect_active_app(self) -> str:
        """
        Attempts to detect the active application/window title.
        Returns a lowercase string identifier or None.
        """
        if sys.platform == "darwin":
             try:
                 script = 'tell application "System Events" to get name of first application process whose frontmost is true'
                 res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
                 if res.returncode == 0:
                     return res.stdout.strip().lower()
             except Exception:
                 pass
             return None

        if shutil.which("xdotool"):
            # 1. Try Window Title
            try:
                res = subprocess.run(
                    ["xdotool", "getwindowfocus", "getwindowname"], 
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    title = res.stdout.strip().lower()
                    if title: return title
            except Exception:
                pass

            # 2. Try Window Class (often better for identifying apps like 'code')
            try:
                res = subprocess.run(
                    ["xdotool", "getwindowfocus", "getwindowclassname"], 
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    classname = res.stdout.strip().lower()
                    if classname: return classname
            except Exception:
                pass

            except Exception:
                pass

        # 3. GNOME Shell Wayland (try gdbus)
        # Requires 'unsafe-mode' often, but worth a try for some setups
        if shutil.which("gdbus"):
            try:
                # Returns (true, 'Code') or similar
                cmd = "global.display.focus_window ? global.display.focus_window.get_wm_class() : ''"
                res = subprocess.run(
                    ["gdbus", "call", "--session", "--dest", "org.gnome.Shell", 
                     "--object-path", "/org/gnome/Shell", "--method", "org.gnome.Shell.Eval", cmd],
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0 and "true" in res.stdout:
                    # Output format: (true, 'Code')
                    parts = res.stdout.split("'")
                    if len(parts) >= 2:
                        return parts[1].lower()
            except Exception:
                pass

        # 4. KDE Plasma (try qdbus)
        if shutil.which("qdbus"):
            try:
                res = subprocess.run(
                    ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.activeWindow"],
                    capture_output=True, text=True, check=False
                )
                # Returns window ID, we'd need to query it. Complex. 
                # Simpler: org.kde.KWin /Scripting org.kde.KWin.Scripting.loadScript ...
                pass
            except Exception:
                pass

        return None

    def get_profile(self, app_identifier: str):
        """
        Checks if the detected app identifier matches any configured rules.
        Returns the mode_id or None.
        """
        if not app_identifier:
            return None

        config = self.config_manager.get()
        if not config.app_profiles:
            return None

        # profiles is Dict[rule_string, mode_id]
        # We check if rule_string is in app_identifier
        for rule, mode_id in config.app_profiles.items():
            if rule.lower() in app_identifier:
                return mode_id
        
        return None
