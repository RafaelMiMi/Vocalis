# Vocalis User Guide

## Introduction
Vocalis is a powerful voice-to-text assistant for Linux that allows you to dictate text anywhere using global hotkeys. It supports local offline transcription (via Faster-Whisper) and cloud-based AI processing (OpenAI, Groq) for intelligent formatting.

## Getting Started

### Installation
1.  Navigate to the packaging directory: `cd packaging`
2.  Run the installer: `./install_ubuntu_24_04.sh`
3.  The app will launch automatically. You can also find "Vocalis" in your application menu.

### First Run
When you first launch Vocalis, you will see a system tray icon (blue "V").
-   **Left-Click**: Toggle Listening (if a window is active).
-   **Right-Click**: Open Menu (Settings, History, Quit).

---

## Core Features

### 1. Global Hotkey
Trigger Vocalis from anywhere without losing focus on your current window.
-   **Default**: `<Super>+<Shift>+<Space>` (Configurable in Settings).
-   **Behavior**: Press once to **Start Listening**. Press again to **Stop**.
-   **Visualizer**: A floating pill window appears to show audio levels and status.
-   **Output**: Transcribed text is automatically typed into your active window or copied to the clipboard, depending on the active Mode.

### 2. Dictation Modes
Modes allow you to switch between different behaviors easily.
-   **Quick (Default)**: Simple raw transcription. Types text immediately.
-   **Command**: Formats text as a system command (e.g., lowercase, no punctuation).
-   **Note**: Saves the transcription to a daily markdown file instead of typing it.
-   **AI Modes**: Apply intelligent transformations (e.g., "Email Polish", "Clean Speech").

**Switching Modes:**
Right-click the tray icon -> **Mode** -> Select your desired mode.

### 3. AI Prompts & Templates
Vocalis can use LLMs (OpenAI or Groq) to rewrite your speech.
-   **Clean Speech**: Removes "ums", "ahs", and fixes grammar.
-   **Bullet Points**: Summarizes your dictation into a bulleted list.
-   **Email Polish**: Turns a rough ramble into a professional email.

**Configuration:**
Go to **Settings -> Prompts** to create your own custom prompts/system instructions.

### 4. History
Accidentally pasted over your text? No problem.
-   Right-click the tray icon -> **History**.
-   View the last 5 transcriptions.
-   Click an item to copy it back to your clipboard.

---

## Settings Guide

### General
-   **Microphone**: Select your specific input device if the default one isn't working appropriately.
-   **Global Hotkey**: Click to record a new key combination.
    -   *Note for Wayland Users*: You must manually set a system shortcut to run `vocalis --listen`. Follow the on-screen instructions in Settings.
-   **Run on Startup**: Toggle to automatically start Vocalis when you log in.

### Models
-   **Provider**: Choose between **Local** (Offline, Private) or **OpenAI / Groq** (Cloud, Smarter).
-   **API Key**: Required for cloud providers.
-   **Model Preset**: For local models, choose "Fast" (lower accuracy) to "High Quality" (slower).

### Modes
Create and edit your custom modes here.
-   **Name**: Display name for the menu.
-   **Prompt**: Link an AI prompt (e.g., "Clean Speech") to this mode.
-   **Action**:
    -   `paste`: Types text directly (default).
    -   `clipboard`: Copies to clipboard only.
    -   `file`: Appends to a file (requires File Path).

### Prompts
Manage the AI instructions.
-   **System Prompt**: Instructions for the AI (e.g., "You are a helpful coder").
-   **Template**: How to wrap the user input (e.g., "Translate this to Spanish: {text}").

---

## Troubleshooting

**"The app doesn't listen or stops immediately"**
-   Check your **Microphone** selection in Settings.
-   Ensure no other app has exclusive control of the audio device.

**"Hotkey doesn't work"**
-   If you are on Ubuntu 22.04+/Wayland, global hotkeys are blocked by the OS. You MUST set a custom system shortcut to run `/home/YOUR_USER/.local/bin/vocalis --listen`.

**"AI Prompts aren't working"**
-   Ensure you have selected **OpenAI** or **Groq** as the provider and entered a valid **API Key**. Local models only support basic transcription.
