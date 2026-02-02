import logging
import re

logger = logging.getLogger(__name__)

class DictionaryManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def apply(self, text: str) -> str:
        """
        Applies personal dictionary replacements to the text.
        Performs case-insensitive matching for keys, preserves case of value.
        """
        config = self.config_manager.get()
        if not config.dictionary or not text:
            return text

        # Sort keys by length (descending) to match longest phrases first
        # This prevents "Super App" being partially replaced by "Super"
        sorted_keys = sorted(config.dictionary.keys(), key=len, reverse=True)

        processed_text = text
        for key in sorted_keys:
            replacement = config.dictionary[key]
            # Create case-insensitive regex pattern
            # \b ensures we match whole words (so "cat" doesn't replace inside "concatenation")
            # However, for some terms user might want partial? Usually whole word is safer.
            # Using \b for safety.
            pattern = re.compile(re.escape(key), re.IGNORECASE)
            processed_text = pattern.sub(replacement, processed_text)
            
        return processed_text
