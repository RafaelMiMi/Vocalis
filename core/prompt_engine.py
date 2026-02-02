import logging

logger = logging.getLogger(__name__)

from core.llm import LLMClient

class PromptEngine:
    def __init__(self, config_manager):
        self.config_manager = config_manager

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
        
        # Check if we should use AI
        # We use AI if the provider is NOT local (implies we have an API key) or if explicitly forced?
        # Actually, simpler: If we have an API key in config, let's try to use LLM for prompts that need it.
        # But wait, 'Quick Dictate' shouldn't hit LLM unless requested.
        # The prompt_id existence implies we want processing.
        
        # Check if simple template (just replacement) or complex
        # For now, let's assume ALL prompts go through LLM *IF* an LLM is configured.
        # IF NOT, we do string replacement.
        
        use_llm = config.transcription_provider in ["openai", "groq"] and config.api_key
        
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
