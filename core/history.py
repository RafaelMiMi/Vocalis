import json
import os
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)

@dataclass
class HistoryItem:
    timestamp: str
    text: str
    mode: str

class HistoryManager:
    def __init__(self, max_items=20):
        self.max_items = max_items
        self.history_dir = os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
            "vocalis"
        )
        self.history_file = os.path.join(self.history_dir, "history.json")
        self.items: List[HistoryItem] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                self.items = [HistoryItem(**item) for item in data]
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    def _save(self):
        os.makedirs(self.history_dir, exist_ok=True)
        try:
            with open(self.history_file, 'w') as f:
                json.dump([asdict(item) for item in self.items], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add(self, text: str, mode: str):
        item = HistoryItem(
            timestamp=datetime.now().isoformat(),
            text=text,
            mode=mode
        )
        self.items.insert(0, item)
        if len(self.items) > self.max_items:
            self.items = self.items[:self.max_items]
        self._save()

    def get_recent(self) -> List[HistoryItem]:
        return self.items

    def clear(self):
        self.items = []
        self._save()
