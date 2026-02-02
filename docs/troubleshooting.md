# Vocalis Troubleshooting Guide

## 1. Hotkey Setup (GNOME / Wayland)
On **Wayland** (especially GNOME on Ubuntu 22.04/24.04, Zorin OS, Fedora), applications cannot capture global hotkeys directly for security reasons. You must configure a system shortcut manually.

### Steps to set up the hotkey:
1.  Open **Settings** -> **Keyboard**.
2.  Scroll down to **View and Customize Shortcuts**.
3.  Select **Custom Shortcuts**.
4.  Click the **+** button to add a new shortcut.
5.  Fill in the details:
    *   **Name**: `Vocalis Listen`
    *   **Command**: `vocalis --listen`
    *   **Shortcut**: Press your desired keys (e.g., `<Super>+<Shift>+Space`)
6.  Click **Add**.

Now, when you press that key combination, it will instantly trigger Vocalis in "one-shot" mode without stealing focus from your active window.

---

## 2. Auto-Paste Issues (Wayland)
Vocalis attempts to type the transcribed text into your active window.

### Requirements:
-   **ydotool**: Must be installed (`sudo apt install ydotool`).
-   **Permissions**: The user needs permission to write to the underlying input device.

If the app sends a notification saying **"Text copied. Press Ctrl+V (Auto-paste failed)"**, it means `ydotool` is not working correctly.

### Fix `ydotool` permissions:
Run the following in a terminal:
```bash
sudo usermod -aG input $USER
```
**Important:** You must **log out and log back in** for this change to take effect.
