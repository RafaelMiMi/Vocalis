import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class SnippetManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def process(self, text: str) -> str:
        """
        Scans text for snippet trigger phrases and replaces them with expanded text.
        Supports placeholders: {date}, {time}, {cursor} (though cursor is just kept as text for now).
        """
        config = self.config_manager.get()
        if not config.snippets or not text:
            return text

        # Sort triggers by length (descending)
        sorted_triggers = sorted(config.snippets.keys(), key=len, reverse=True)

        processed_text = text
        
        # We need to handle dynamic replacements (date/time) at the moment of expansion
        for trigger in sorted_triggers:
            if trigger.lower() in processed_text.lower():
                raw_snippet = config.snippets[trigger]
                expanded_snippet = self._expand_placeholders(raw_snippet)
                
                # Case-insensitive replacement
                pattern = re.compile(re.escape(trigger), re.IGNORECASE)
                processed_text = pattern.sub(expanded_snippet, processed_text)

        return processed_text

    def _expand_placeholders(self, snippet: str) -> str:
        now = datetime.now()
        
        # Simple string replacements
        snippet = snippet.replace("{date}", now.strftime("%Y-%m-%d"))
        snippet = snippet.replace("{time}", now.strftime("%H:%M"))
        
        # {cursor} is special - usually we might split the string or just remove it 
        # for simple text paste. For now, let's just remove it or handle it in OutputAction 
        # if we get fancy. Given current architecture, let's keep it clean:
        # If output action is 'type', maybe we can simulate arrow keys? 
        # For Phase 1, we will just remove the marker so it doesn't show up in text.
        snippet = snippet.replace("{cursor}", "") 
        
        return snippet
