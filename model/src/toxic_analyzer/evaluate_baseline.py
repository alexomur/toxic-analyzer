"""Evaluate the saved baseline model on labeled text fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np

from toxic_analyzer.baseline_model import compute_binary_metrics
from toxic_analyzer.inference_service import ToxicityInferenceService
from toxic_analyzer.model_runtime import DEFAULT_MODEL_PATH, ROOT_DIR, build_missing_model_message

DEFAULT_DATASET_PATH = ROOT_DIR / "data" / "processed" / "test_text.txt"
_RECORD_PATTERN = re.compile(r"(.*?)\s*\^\s*([01])\s*;", re.DOTALL)


@dataclass(frozen=True, slots=True)
class LabeledTextCase:
    text: str
    label: int


@dataclass(frozen=True, slots=True)
class ModelErrorCase:
    index: int
    text: str
    expected_label: int
    predicted_label: int
    toxic_probability: float

    @property
    def error_type(self) -> str:
        if self.expected_label == 0 and self.predicted_label == 1:
            return "false_positive"
        if self.expected_label == 1 and self.predicted_label == 0:
            return "false_negative"
        raise ValueError("ModelErrorCase can only describe misclassified rows.")

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "error_type": self.error_type,
            "expected_label": self.expected_label,
            "predicted_label": self.predicted_label,
            "toxic_probability": round(self.toxic_probability, 6),
            "text": self.text,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--encoding", default="utf-8")
    return parser.parse_args(argv)


def parse_labeled_text_cases(payload: str) -> list[LabeledTextCase]:
    cases: list[LabeledTextCase] = []
    position = 0
    payload_length = len(payload)

    while position < payload_length:
        while position < payload_length and payload[position].isspace():
            position += 1
        if position >= payload_length:
            break

        match = _RECORD_PATTERN.match(payload, pos=position)
        if match is None:
            trailing_preview = payload[position : position + 120].strip()
            raise ValueError(
                "Failed to parse labeled test data near: "
                f"{trailing_preview!r}. Expected '<text> ^ <toxicity>;' entries."
            )

        text = match.group(1).strip()
        if not text:
            raise ValueError("Encountered an empty text entry in the labeled test data.")

        cases.append(LabeledTextCase(text=text, label=int(match.group(2))))
        position = match.end()

    if not cases:
        raise ValueError("No labeled test entries were found in the dataset.")

    return cases


def load_labeled_text_cases(path: Path, *, encoding: str) -> list[LabeledTextCase]:
    return parse_labeled_text_cases(path.read_text(encoding=encoding))


def _build_confusion_counts(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
) -> dict[str, int]:
    predictions = (probabilities >= threshold).astype(int)
    return {
        "true_positive": int(np.sum((predictions == 1) & (labels == 1))),
        "true_negative": int(np.sum((predictions == 0) & (labels == 0))),
        "false_positive": int(np.sum((predictions == 1) & (labels == 0))),
        "false_negative": int(np.sum((predictions == 0) & (labels == 1))),
    }


def _collect_model_errors(
    cases: Sequence[LabeledTextCase],
    probabilities: np.ndarray,
    threshold: float,
) -> list[ModelErrorCase]:
    predictions = (probabilities >= threshold).astype(int)
    errors: list[ModelErrorCase] = []
    for index, (case, predicted_label, probability) in enumerate(
        zip(cases, predictions.tolist(), probabilities.tolist(), strict=True),
        start=1,
    ):
        if predicted_label == case.label:
            continue
        errors.append(
            ModelErrorCase(
                index=index,
                text=case.text,
                expected_label=case.label,
                predicted_label=int(predicted_label),
                toxic_probability=float(probability),
            )
        )
    return errors


def build_evaluation_payload(
    service: ToxicityInferenceService,
    cases: Sequence[LabeledTextCase],
    *,
    dataset_path: Path,
) -> dict[str, object]:
    texts = [case.text for case in cases]
    labels = np.asarray([case.label for case in cases], dtype=int)
    probabilities = np.asarray(
        [prediction.toxic_probability for prediction in service.predict_many(texts)],
        dtype=float,
    )
    threshold = float(service.model.threshold)
    metrics = compute_binary_metrics(labels, probabilities, threshold=threshold)
    metrics.update(_build_confusion_counts(labels, probabilities, threshold))
    errors = _collect_model_errors(cases, probabilities, threshold)

    return {
        "dataset": {
            "path": str(dataset_path.resolve()),
            "rows": int(len(cases)),
            "positive_labels": int(np.sum(labels == 1)),
            "negative_labels": int(np.sum(labels == 0)),
        },
        "model": service.get_model_info().to_dict(),
        "metrics": metrics,
        "errors": [error.to_dict() for error in errors],
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        service = ToxicityInferenceService.from_path(args.model_path)
    except FileNotFoundError as exc:
        missing_path = Path(str(exc.args[0]))
        raise SystemExit(build_missing_model_message(missing_path)) from exc

    cases = load_labeled_text_cases(args.dataset_path, encoding=args.encoding)
    payload = build_evaluation_payload(service, cases, dataset_path=args.dataset_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
