# Vocalis on Wayland

Wayland inherently prevents applications from snooping on global input (keystrokes) for security reasons. This means Vocalis cannot simply "listen" for a global hotkey like `Super+Shift+Space` unless it is an OS-level shortcut.

## Setup Instructions for GNOME (Ubuntu 24.04)

To make Vocalis feel like a native global hotkey app, you must register a Custom Shortcut in GNOME Settings.

1. **Open Settings** -> **Keyboard** -> **View and Customize Shortcuts**.
2. Scroll down to **Custom Shortcuts**.
3. Click **Add Shortcut**.
   - **Name**: Start Vocalis Listening
   - **Command**: `vocalis --listen`
   - **Shortcut**: `Super+Shift+Space` (or your preferred combo)
4. Click **Add**.

## Usage

- **Press the Shortcut**: Vocalis will immediately start recording.
- **Speak**: Dictate your text.
- **Wait**: Vocalis will record for ~10 seconds (default) or until silence is detected (future update), then transcribe.
- **Paste**: The text will be copied to your clipboard. A notification will appear. Press `Ctrl+V` to paste it.

## Limitations

- **No "Push-to-Talk"**: The current implementation triggers a fixed-duration recording window or toggles recording on/off.
- **Simulated Paste**: On strict Wayland setups, Vocalis cannot simulate `Ctrl+V` automatically. You must manually paste the result.
