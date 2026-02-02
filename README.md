# Vocalis 🎙️

**A private, powerful, and customizable Voice-to-Text assistant for Linux (Wayland & X11).**

Vocalis allows you to dictate text anywhere. It listens to your global hotkey, records your voice, transcribes it locally (or via Cloud AI), and pastes it directly into your active application.

![Vocalis Banner](https://via.placeholder.com/800x200?text=Vocalis+Voice+Assistant) (*Add actual screenshot here*)

## ✨ Features

-   **Global Hotkeys**: Works on **Wayland** (Ubuntu 24.04+) and X11.
-   **Dictation Modes**:
    -   ⚡ **Quick**: Fast, raw transcription.
    -   🧠 **AI Formatting**: Use LLMs (OpenAI/Groq) to clean up grammar, summarize, or rewrite text.
    -   📝 **Note Taking**: Append dictations to a daily markdown file.
-   **Privacy-First**: Supports **Local Transcription** using `faster-whisper` (runs offline).
-   **Visual Feedback**: A sleek, non-intrusive floating visualizer shows you when it's listening.
-   **Auto-Paste**: Automatically types text into your active window (supports `ydotool` for Wayland).
-   **History**: Keep a history of your transcriptions.

## 🚀 Installation

### Prerequisites
-   Ubuntu 22.04 or 24.04 (Recommended)
-   Python 3.10+
-   `ffmpeg`

### Quick Start
 Clone the repository and run the installer:

```bash
git clone https://github.com/RafaelMiMi/Vocalis.git
cd Vocalis/packaging
./install_ubuntu_24_04.sh
```

This will install dependencies, set up the virtual environment, and create a desktop entry.

## 📖 Usage

### 1. Launching
Open **Vocalis** from your applications menu. A blue **"V"** icon will appear in your system tray.

### 2. The Hotkey
-   **Default**: `<Super>+<Shift>+<Space>`
-   **Action**: Press ONCE to start listening. Press AGAIN to stop.
-   *Wayland Note*: If the default hotkey doesn't work, go to **Settings** -> **General** and follow the instructions to set a system shortcut for `vocalis --listen`.

### 3. Settings
Right-click the tray icon and select **Settings** to configure:
-   **Microphone**: Select your input device.
-   **AI Provider**: accurate local models or smart cloud models (OpenAI/Groq).
-   **Prompts**: Create custom AI instructions (e.g., "Make this sound professional").

## 📚 Documentation
For a detailed guide on all features, AI prompts, and advanced configuration, read the **[User Guide](docs/user_guide.md)**.

## 🛠️ Development

To run from source:
```bash
# Activate venv
source venv/bin/activate

# Run App
python -m app.main --gui
```

## 📄 License
MIT License. Free to use and modify.
