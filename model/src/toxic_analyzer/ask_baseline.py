"""User-friendly CLI for baseline toxicity predictions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Protocol, Sequence

from toxic_analyzer.baseline_model import ToxicityPrediction
from toxic_analyzer.inference_service import ToxicityInferenceService
from toxic_analyzer.model_runtime import (
    DEFAULT_MODEL_PATH,
    build_missing_model_message,
)


class SupportsSinglePrediction(Protocol):
    def predict_one(self, text: str) -> ToxicityPrediction:
        ...


EXIT_COMMANDS = {"exit", "quit", "q", "выход"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("text", nargs="*")
    return parser.parse_args(argv)


def format_prediction(text: str, prediction: ToxicityPrediction) -> str:
    verdict = "токсичный" if prediction.label == 1 else "нетоксичный"
    return (
        f"Текст: {text}\n"
        f"Вердикт модели: {verdict}\n"
        f"label: {prediction.label}\n"
        f"score: {prediction.score:.6f}\n"
        f"p(toxic): {prediction.toxic_probability:.6f}"
    )


def sanitize_text(text: str) -> str:
    sanitized = text.lstrip("\ufeff")
    if sanitized.startswith("п»ї"):
        sanitized = sanitized[3:]
    return sanitized.strip()


def load_service(model_path: Path) -> ToxicityInferenceService:
    try:
        return ToxicityInferenceService.from_path(model_path)
    except FileNotFoundError as exc:
        missing_path = Path(str(exc.args[0]))
        raise SystemExit(build_missing_model_message(missing_path)) from exc


def run_single_prediction(
    service: SupportsSinglePrediction,
    text: str,
    *,
    output_fn: Callable[[str], None],
) -> None:
    output_fn(format_prediction(text, service.predict_one(text)))


def interactive_loop(
    service: SupportsSinglePrediction,
    *,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    output_fn("Интерактивный режим. Введите фразу для проверки.")
    output_fn("Для выхода нажмите Enter на пустой строке или введите `exit`.")
    while True:
        try:
            text = sanitize_text(input_fn("> "))
        except EOFError:
            output_fn("Завершение.")
            return
        if not text or text.lower() in EXIT_COMMANDS:
            output_fn("Завершение.")
            return
        run_single_prediction(service, text, output_fn=output_fn)
        output_fn("")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    service = load_service(args.model_path)
    if args.text:
        run_single_prediction(service, sanitize_text(" ".join(args.text)), output_fn=print)
        return 0

    interactive_loop(service)
    return 0


if __name__ == "__main__":
    sys.exit(main())
