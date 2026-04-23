"""Helpers for loading and evaluating curated hard-case examples."""


import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class HardCaseItem:
    text: str
    label: int
    tags: list[str]


@dataclass(slots=True)
class HardCaseDataset:
    path: Path
    items: list[HardCaseItem]

    @property
    def texts(self) -> list[str]:
        return [item.text for item in self.items]

    @property
    def labels(self) -> list[int]:
        return [item.label for item in self.items]

    @property
    def unique_tags(self) -> list[str]:
        tags = {tag for item in self.items for tag in item.tags}
        return sorted(tags)

    def summary(self) -> dict[str, Any]:
        positive = sum(item.label for item in self.items)
        return {
            "path": str(self.path),
            "rows": len(self.items),
            "positive_rows": positive,
            "negative_rows": len(self.items) - positive,
            "tags": self.unique_tags,
        }


def load_hard_case_dataset(path: Path) -> HardCaseDataset:
    if not path.exists():
        raise FileNotFoundError(path)
    items: list[HardCaseItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            text = str(payload["text"]).strip()
            label = int(payload["label"])
            if label not in {0, 1}:
                raise ValueError(f"Unsupported hard-case label={label!r} at line {line_number}.")
            tags = [str(tag) for tag in payload.get("tags", [])]
            items.append(HardCaseItem(text=text, label=label, tags=tags))
    if not items:
        raise ValueError(f"Hard-case dataset is empty: {path}")
    return HardCaseDataset(path=path.resolve(), items=items)
