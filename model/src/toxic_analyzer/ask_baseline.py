"""User-friendly CLI for baseline toxicity predictions."""


import argparse
import sys
from pathlib import Path
from typing import Callable, Protocol, Sequence

from toxic_analyzer.baseline_model import ExplainedToxicityPrediction, ToxicityPrediction
from toxic_analyzer.inference_service import ToxicityInferenceService
from toxic_analyzer.model_runtime import (
    DEFAULT_MODEL_PATH,
    build_missing_model_message,
)


class SupportsSinglePrediction(Protocol):
    def predict_one(self, text: str) -> ToxicityPrediction:
        ...

    def predict_one_explained(self, text: str, *, top_n: int = 10) -> ExplainedToxicityPrediction:
        ...


EXIT_COMMANDS = {"exit", "quit", "q", "выход"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="number of top positive and negative feature contributions to display",
    )
    parser.add_argument("text", nargs="*")
    return parser.parse_args(argv)


def format_prediction(text: str, prediction: ToxicityPrediction) -> str:
    verdict = "токсичный" if prediction.label == 1 else "нетоксичный"
    return (
        f"Текст: {text}\n"
        f"Вердикт модели: {verdict}\n"
        f"label: {prediction.label}\n"
        f"p(toxic): {prediction.toxic_probability:.6f}"
    )


def format_explained_prediction(text: str, prediction: ExplainedToxicityPrediction) -> str:
    lines = [
        format_prediction(text, prediction),
        "======",
        f"raw_model_probability: {prediction.raw_model_probability:.6f}",
        f"calibrated_probability: {prediction.calibrated_probability:.6f}",
        f"posthoc_adjusted_probability: {prediction.posthoc_adjusted_probability:.6f}",
        f"threshold: {prediction.threshold:.6f}",
        "canonical_tokens: " + ", ".join(prediction.explanation.canonical_tokens),
        "======",
        "Top positive features:",
    ]
    for index, item in enumerate(prediction.explanation.top_positive_features, start=1):
        lines.append(
            f"{index}. {item.feature_group}: {item.feature_name} => {item.contribution:+.3f}"
        )
    lines.append("Top negative features:")
    for index, item in enumerate(prediction.explanation.top_negative_features, start=1):
        lines.append(
            f"{index}. {item.feature_group}: {item.feature_name} => {item.contribution:+.3f}"
        )
    lines.append("Triggered expert features:")
    for index, item in enumerate(prediction.explanation.triggered_expert_features, start=1):
        lines.append(f"{index}. expert_feature: {item.feature_name} => {item.feature_value:.3f}")
    lines.append("Applied adjustments:")
    for index, item in enumerate(prediction.explanation.applied_adjustments, start=1):
        lines.append(f"{index}. posthoc_adjustment: {item.adjustment_name} => {item.delta:+.3f}")
    return "\n".join(lines)


def sanitize_text(text: str) -> str:
    sanitized = text.lstrip("\ufeff")
    for broken_prefix in ("п»ї", "п»—"):
        if sanitized.startswith(broken_prefix):
            sanitized = sanitized[len(broken_prefix) :]
            break
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
    top_n: int = 10,
    output_fn: Callable[[str], None],
) -> None:
    output_fn(format_explained_prediction(text, service.predict_one_explained(text, top_n=top_n)))


def interactive_loop(
    service: SupportsSinglePrediction,
    *,
    top_n: int = 10,
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
        run_single_prediction(service, text, top_n=top_n, output_fn=output_fn)
        output_fn("")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    service = load_service(args.model_path)
    if args.text:
        run_single_prediction(
            service,
            sanitize_text(" ".join(args.text)),
            top_n=args.top_n,
            output_fn=print,
        )
        return 0

    interactive_loop(service, top_n=args.top_n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
