import logging
import threading
import os
import time
try:
    from pynput import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)

class HotkeyManager:
    def __init__(self, callback, hotkey_str="<super>+<shift>+space"):
        self.callback = callback
        self.hotkey_str = hotkey_str
        self.running = False
        self.thread = None

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def update_hotkey(self, new_hotkey):
        self.hotkey_str = new_hotkey
        if self.running:
            self.stop()
            self.start()

class WaylandHotkeyManager(HotkeyManager):
    def start(self):
        self.running = True
        logger.info("Wayland Hotkey Manager started (Passive Mode).")
        logger.info("Configured Trigger: Run 'vocalis --listen' via OS shortcuts.")
        # In this mode, we don't actually register a global hotkey because we can't.
        # We rely on the user binding a system key to the CLI command.
        
    def stop(self):
        self.running = False
        logger.info("Wayland Hotkey Manager stopped.")

class X11HotkeyManager(HotkeyManager):
    def __init__(self, callback, hotkey_str):
        super().__init__(callback, hotkey_str)
        self.listener = None

    def _on_activate(self):
        logger.info("Global hotkey pressed (X11)")
        if self.callback:
            # Run in separate thread to avoid blocking input
            threading.Thread(target=self.callback).start()

    def start(self):
        if not keyboard:
            logger.error("pynput not installed, cannot use X11 hotkeys")
            return

        self.running = True
        logger.info(f"Registering X11 hotkey: {self.hotkey_str}")
        
        # Convert config string to pynput format if needed
        # Expected config format: "<super>+<shift>+space" or "cmd+shift+space"
        # pynput expects: "<cmd>+<shift>+<space>"
        
        try:
            # Simple normalization for pynput
            # Pynput uses <cmd> for Super/Windows key
            pynput_str = self.hotkey_str.replace("<super>", "<cmd>")
            
            hotkey_map = {pynput_str: self._on_activate}
            self.listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener.start()
        except Exception as e:
            logger.error(f"Failed to register hotkey: {e}")

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None

def get_manager(callback, hotkey_str) -> HotkeyManager:
    session_type = os.environ.get("XDG_SESSION_TYPE")
    if session_type == "wayland":
        return WaylandHotkeyManager(callback, hotkey_str)
    else:
        return X11HotkeyManager(callback, hotkey_str)
