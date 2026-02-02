# Vocalis Features
## Dictation Modes
Vocalis v2 supports multiple modes for different workflows:
- **Quick Dictate**: Captures audio, transcribes, and immediately pastes it (or copies to clipboard). Good for instant messaging.
- **Command Mode**: Wraps the dictation in a command template (e.g. `Command: {text}`). Can be extended for LLM processing.
- **Note Mode**: Appends transcription to a daily note file (default: `~/Documents/vocalis_notes.md`) for journaling.

## AI Prompts
Apply templates to your transcription before outputting.
- **Command Format**: Prefixes text.
- **Email Polish**: Formats text as a structured email.
- **Bullet Points**: Converts sentences to a bulleted list.

## Quality Presets
- **Fast**: Uses `tiny` model. Quickest response.
- **Balanced**: Uses `small` model. Good balance of speed and accuracy.
- **High Quality**: Uses `medium` model. Best accuracy, slower.

## History
Access the last 20 transcripts from the system tray menu. Click any item to re-copy it to the clipboard.
