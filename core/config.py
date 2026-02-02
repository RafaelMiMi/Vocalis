import toml
import os
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class DictationMode:
    name: str
    prompt_id: str = None
    output_action: str = "clipboard" # clipboard, paste, file
    paste_method: str = "auto" # auto, ctrl_v, type, copy_only
    file_path: str = None # for file output

@dataclass
class Prompt:
    id: str
    name: str
    description: str
    template: str
    system_prompt: str = "You are a helpful assistant."

@dataclass
class AppConfig:
    # ASR Settings
    transcription_provider: str = "local" # local, openai, groq
    api_key: str = None
    model_preset: str = "balanced" # fast, balanced, high_quality
    model_size: str = "small" # Derived or manual override (local)
    remote_model_name: str = "whisper-1" # for API
    device: str = "auto" # cpu, cuda, auto
    language: str = "auto"

    # Input/Output
    input_device: int = None
    hotkey: str = "<super>+<shift>+space"
    
    # Modes & Behavior
    current_mode: str = "quick" # quick, command, note
    show_visualizer: bool = True
    modes: dict = None # Dict[str, DictationMode]
    prompts: dict = None # Dict[str, Prompt]
    dictionary: dict = None # Dict[str, str] (Spoken -> Written)
    snippets: dict = None # Dict[str, str] (Trigger -> Replacement)
    app_profiles: dict = None # Dict[str, str] (Window Title Substring -> Mode ID)
    
    paste_delay: float = 0.5  # Seconds to wait before pasting (allows focus restore)

    # Privacy / Permissions
    allow_clipboard_access: bool = True
    
    # History
    history_size: int = 20
    logs_path: str = "~/Documents/vocalis_transcripts.txt"

    def __post_init__(self):
        # Defaults if None
        if self.modes is None:
            self.modes = {
                "quick": {"name": "Quick Dictate", "output_action": "paste", "paste_method": "auto", "prompt_id": None},
                "command": {"name": "Command Mode", "output_action": "clipboard", "paste_method": "auto", "prompt_id": "command"},
                "note": {"name": "Note Mode", "output_action": "file", "paste_method": "auto", "prompt_id": None, "file_path": "~/Documents/vocalis_notes.md"}
            }
        if self.prompts is None:
            self.prompts = {
                "command": {"id": "command", "name": "Command Format", "description": "Format as system command", "template": "Command: {text}", "system_prompt": "You are a command line formatting assistant."},
                "email": {"id": "email", "name": "Email Polish", "description": "Rewrite as professional email", "template": "Subject: [Topic]\n\n{text}", "system_prompt": "You are a professional email assistant. Rewrite the input into a clear, concise email."},
                "bullet": {"id": "bullet", "name": "Bullet Points", "description": "Summarize as bullets", "template": "{text}", "system_prompt": "Summarize the following text into concise bullet points."},
                "clean": {"id": "clean", "name": "Clean Speech", "description": "Remove fillers and fix grammar", "template": "{text}", "system_prompt": "You are a helpful editor. Remove speech fillers (um, ah, like), false starts, and correct basic grammar while preserving the original meaning and tone."}
            }
        
        if self.dictionary is None:
            self.dictionary = {}
        if self.snippets is None:
            self.snippets = {}
        if self.app_profiles is None:
            self.app_profiles = {}

class ConfigManager:
    def __init__(self):
        self.config_dir = os.path.join(
            os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
            "vocalis"
        )
        self.config_file = os.path.join(self.config_dir, "config.toml")
        self.config = AppConfig()
        self.load()

    def load(self):
        if not os.path.exists(self.config_file):
            self.save()  # Create default
            return

        try:
            with open(self.config_file, "r") as f:
                data = toml.load(f)
                # Update config with loaded values, ignore unknown keys
                # This is a simple merge
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def save(self):
        os.makedirs(self.config_dir, exist_ok=True)
        try:
            with open(self.config_file, "w") as f:
                toml.dump(asdict(self.config), f)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get(self) -> AppConfig:
        return self.config
