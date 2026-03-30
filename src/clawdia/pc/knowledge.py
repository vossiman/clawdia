from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml


class KnowledgeBase:
    """YAML-backed knowledge base of learned facts about the user's PC setup."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.data: dict = {}
        if self.path.exists():
            text = self.path.read_text()
            if text.strip():
                self.data = yaml.safe_load(text) or {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.dump(self.data, default_flow_style=False, sort_keys=False))

    def update(self, section: str, key: str, value: str | dict) -> None:
        if section not in self.data:
            self.data[section] = {}
        self.data[section][key] = value
        self._save()

    def add_preference(self, preference: str) -> None:
        if "preferences" not in self.data:
            self.data["preferences"] = []
        if preference not in self.data["preferences"]:
            self.data["preferences"].append(preference)
        self._save()

    def add_correction(self, trigger: str, learned: str) -> None:
        if "corrections" not in self.data:
            self.data["corrections"] = []
        self.data["corrections"].append({
            "trigger": trigger,
            "learned": learned,
            "date": str(date.today()),
        })
        self._save()

    def to_prompt_context(self) -> str:
        if not self.data:
            return ""
        return yaml.dump(self.data, default_flow_style=False, sort_keys=False).strip()
