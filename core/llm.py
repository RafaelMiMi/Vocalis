import logging
import os

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config):
        self.config = config
        self.client = None
        self.provider = self.config.transcription_provider
        self._setup_client()

    def _setup_client(self):
        self.provider = self.config.transcription_provider
        api_key = self.config.api_key
        
        # Resolve API Key based on provider
        if not api_key:
            if self.provider == "openai":
                api_key = os.environ.get("OPENAI_API_KEY")
            elif self.provider == "groq":
                api_key = os.environ.get("GROQ_API_KEY")
            elif self.provider == "deepseek":
                api_key = os.environ.get("DEEPSEEK_API_KEY")
            elif self.provider in ["glm", "zhipu"]:
                api_key = os.environ.get("ZHIPU_API_KEY")
            elif self.provider in ["claude", "anthropic"]:
                api_key = os.environ.get("ANTHROPIC_API_KEY")
             
        if not api_key:
            return

        try:
            if self.provider in ["claude", "anthropic"]:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=api_key)
            else:
                from openai import OpenAI
                base_url = None
                if self.provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                elif self.provider == "deepseek":
                    base_url = "https://api.deepseek.com"
                elif self.provider in ["glm", "zhipu"]:
                    base_url = "https://open.bigmodel.cn/api/paas/v4/"
                
                self.client = OpenAI(api_key=api_key, base_url=base_url)
                
        except ImportError as e:
            logger.error(f"Failed to import client library for {self.provider}: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider} client: {e}")

    def process(self, system_prompt: str, user_text: str, model=None) -> str:
        if not self.client:
            return user_text 
            
        if not model:
            model = self._get_default_model()

        try:
            if self.provider in ["claude", "anthropic"]:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_text}
                    ]
                )
                return response.content[0].text
            else:
                # OpenAI-compatible providers
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text}
                    ]
                )
                return response.choices[0].message.content.strip()
                
        except Exception as e:
            logger.error(f"LLM request failed ({self.provider}): {e}")
            raise

    def _get_default_model(self):
        if self.config.remote_model_name and self.config.remote_model_name != "whisper-1":
             # Use configured model if it looks like an LLM model (not the default whisper one)
             return self.config.remote_model_name

        if self.provider == "groq":
            return "llama3-70b-8192"
        elif self.provider == "deepseek":
            return "deepseek-chat"
        elif self.provider in ["glm", "zhipu"]:
            return "glm-4"
        elif self.provider in ["claude", "anthropic"]:
            return "claude-3-5-sonnet-20240620"
        else:
            return "gpt-3.5-turbo"
