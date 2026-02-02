import logging

logger = logging.getLogger(__name__)

from core.llm import LLMClient
from core.context import ContextManager

class PromptEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.context_manager = ContextManager(config_manager)

    def process(self, text: str, prompt_id: str) -> str:
        config = self.config_manager.get()
        prompts = config.prompts
        
        if not prompt_id or prompt_id not in prompts:
            return text
        
        prompt_data = prompts[prompt_id]
        
        # Determine template content
        if isinstance(prompt_data, dict):
            template = prompt_data.get("template", "{text}")
            system_prompt = prompt_data.get("system_prompt", "You are a helpful assistant.")
        else:
             # If dataclass (future proofing)
            template = getattr(prompt_data, "template", "{text}")
            system_prompt = getattr(prompt_data, "system_prompt", "You are a helpful assistant.")
            
        logger.info(f"Applying prompt '{prompt_id}'")
        
        # Context Substitution
        if "{clipboard}" in template:
            clipboard_content = self.context_manager.get_clipboard()
            template = template.replace("{clipboard}", clipboard_content)

        # Check if we should use AI
        # If we have an API key, we should use the LLM for prompts that require intelligence.
        # This enables "Hybrid Mode": Local Whisper for transcription + OpenAI/Groq for processing.
        use_llm = bool(config.api_key and config.api_key.strip())
        
        if use_llm:
            try:
                # Prepare the user message part
                user_content = template.replace("{text}", text)
                
                client = LLMClient(config)
                return client.process(system_prompt, user_content)
            except Exception as e:
                logger.error(f"AI Prompting failed: {e}")
                # Fallback to simple replace
                return template.replace("{text}", text)
        else:
            # Simple string replacement
            try:
                processed_text = template.replace("{text}", text)
                
                # Simple "AI" Mocks based on ID (Legacy Fallback)
                if prompt_id == "bullet" and "- " not in processed_text:
                    lines = text.split(". ")
                    processed_text = "\n".join([f"- {line.strip()}" for line in lines if line.strip()])
                
                return processed_text
            except Exception as e:
                logger.error(f"Prompt processing failed: {e}")
                return text

    def update_prompts(self, new_prompts: dict):
        self.prompts = new_prompts
