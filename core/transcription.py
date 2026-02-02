import os
import logging
from abc import ABC, abstractmethod
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class TranscriberBase(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str = None) -> str:
        pass

class LocalTranscriber(TranscriberBase):
    def __init__(self, model_preset="balanced", model_size=None, device="auto", compute_type="default"):
        self.model_preset = model_preset
        if not model_size:
            self.model_size = self._get_size_from_preset(model_preset)
        else:
            self.model_size = model_size
            
        self.device = self._detect_device(device)
        self.compute_type = compute_type
        self.model = None
        self._load_model()

    def _get_size_from_preset(self, preset):
        presets = {
            "fast": "tiny",
            "balanced": "small",
            "high_quality": "medium"
        }
        return presets.get(preset, "small")

    def _detect_device(self, device_request):
        if device_request != "auto":
            return device_request
        return "cpu"

    def _load_model(self):
        logger.info(f"Loading faster-whisper model: {self.model_size} ({self.model_preset}) on {self.device}")
        xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        download_root = os.path.join(xdg_data, "vocalis", "models")
        os.makedirs(download_root, exist_ok=True)
        
        try:
            self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type, download_root=download_root)
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def transcribe(self, audio_path: str, language: str = None) -> str:
        if not self.model:
            raise RuntimeError("Model not loaded")
            
        logger.info(f"Transcribing {audio_path}...")
        segments, info = self.model.transcribe(audio_path, language=language, beam_size=5)
        
        logger.info(f"Detected language '{info.language}' with probability {info.language_probability}")
        
        text_segments = []
        for segment in segments:
            text_segments.append(segment.text)
            
        return "".join(text_segments).strip()

class RemoteTranscriber(TranscriberBase):
    def __init__(self, provider="openai", api_key=None, model_name="whisper-1"):
        self.provider = provider
        self.api_key = api_key
        self.model_name = model_name
        
        if not self.api_key:
             # Try env var
             self.api_key = os.environ.get("OPENAI_API_KEY") if provider == "openai" else os.environ.get("GROQ_API_KEY")
             
        if not self.api_key:
            raise ValueError(f"API Key required for {provider}")

    def transcribe(self, audio_path: str, language: str = None) -> str:
        logger.info(f"Transcribing via {self.provider} ({self.model_name})...")
        
        try:
            from openai import OpenAI
            
            base_url = None
            if self.provider == "groq":
                base_url = "https://api.groq.com/openai/v1"
                if not self.model_name: self.model_name = "distil-whisper-large-v3-en"
            
            client = OpenAI(api_key=self.api_key, base_url=base_url)
            
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    language=language
                )
            
            return transcript.text
            
        except ImportError:
            raise ImportError("openai package is required for remote transcription. Install it with: pip install openai")
        except Exception as e:
            logger.error(f"Remote transcription failed: {e}")
            raise

class TranscriberFactory:
    @staticmethod
    def get_transcriber(config):
        if config.transcription_provider == "local":
            return LocalTranscriber(
                model_preset=config.model_preset,
                model_size=config.model_size,
                device=config.device
            )
        else:
            # openai or groq
            return RemoteTranscriber(
                provider=config.transcription_provider,
                api_key=config.api_key,
                model_name=config.remote_model_name
            )
