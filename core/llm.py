import logging
import os

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config):
        self.config = config
        self.client = None
        self._setup_client()

    def _setup_client(self):
        provider = self.config.transcription_provider
        api_key = self.config.api_key
        
        if not api_key:
             # Try env var
             api_key = os.environ.get("OPENAI_API_KEY") if provider == "openai" else os.environ.get("GROQ_API_KEY")
             
        if not api_key:
            return

        try:
            from openai import OpenAI
            base_url = None
            if provider == "groq":
                base_url = "https://api.groq.com/openai/v1"
            
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            logger.error("openai module not found")

    def process(self, system_prompt: str, user_text: str, model=None) -> str:
        if not self.client:
            return user_text # Fallback/Error state handled by caller usually
            
        if not model:
            # Default models for chat
            if self.config.transcription_provider == "groq":
                model = "llama3-70b-8192" # Good default for Groq
            else:
                model = "gpt-3.5-turbo" # Default for OpenAI

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise
