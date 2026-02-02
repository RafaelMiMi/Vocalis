import logging
from core.dictionary import DictionaryManager
from core.snippets import SnippetManager

logger = logging.getLogger(__name__)

class TextProcessor:
    def __init__(self, config_manager, prompt_engine):
        self.config_manager = config_manager
        self.prompt_engine = prompt_engine
        self.dictionary_manager = DictionaryManager(config_manager)
        self.snippet_manager = SnippetManager(config_manager)

    def process(self, text: str, mode_data: dict) -> str:
        """
        Runs the full text processing pipeline:
        1. AI Prompt (if configured)
        2. Personal Dictionary (Replacements)
        3. Snippets (Expansion)
        """
        processed_text = text
        
        # 1. AI Prompt
        prompt_id = mode_data.get("prompt_id")
        if prompt_id:
            logger.info(f"Applying AI Prompt: {prompt_id}")
            processed_text = self.prompt_engine.process(processed_text, prompt_id)
            
        # 2. Dictionary
        # We perform dictionary replacements *after* AI, assuming AI fixes grammar 
        # but might mishandle specific proper nouns if not context-aware. 
        # Or should we do it before? Doing it after ensures our custom terms override AI output.
        logger.info("Applying Personal Dictionary...")
        processed_text = self.dictionary_manager.apply(processed_text)
        
        # 3. Snippets
        # Snippets should definitely be last, as they expand into formatted text 
        # that shouldn't be altered by AI.
        logger.info("Checking for Snippets...")
        processed_text = self.snippet_manager.process(processed_text)
        
        return processed_text
