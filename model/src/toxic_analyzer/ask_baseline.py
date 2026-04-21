"""User-friendly CLI for baseline toxicity predictions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable, Sequence

from toxic_analyzer.baseline_model import ToxicityBaselineModel, ToxicityPrediction

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT_DIR / "artifacts" / "baseline_model_v2.pkl"
LEGACY_MODEL_PATH = ROOT_DIR / "artifacts" / "baseline_model.pkl"
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


def load_model(model_path: Path) -> ToxicityBaselineModel:
    resolved_path = model_path.resolve()
    if not resolved_path.exists() and resolved_path == DEFAULT_MODEL_PATH.resolve():
        resolved_path = LEGACY_MODEL_PATH.resolve()
    if not resolved_path.exists():
        raise SystemExit(
            "Файл модели не найден. Сначала обучите baseline командой `train-baseline` "
            f"или укажите путь через --model-path: {resolved_path}"
        )
    return ToxicityBaselineModel.load(resolved_path)


def run_single_prediction(
    model: ToxicityBaselineModel,
    text: str,
    *,
    output_fn: Callable[[str], None],
) -> None:
    output_fn(format_prediction(text, model.predict_one(text)))


def interactive_loop(
    model: ToxicityBaselineModel,
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
        run_single_prediction(model, text, output_fn=output_fn)
        output_fn("")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    model = load_model(args.model_path)
    if args.text:
        run_single_prediction(model, sanitize_text(" ".join(args.text)), output_fn=print)
        return 0

    interactive_loop(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
