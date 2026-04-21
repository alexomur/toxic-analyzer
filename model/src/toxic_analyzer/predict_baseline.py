"""Run inference with a saved baseline toxicity model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from toxic_analyzer.baseline_model import ToxicityBaselineModel

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT_DIR / "artifacts" / "baseline_model_v3.pkl"
FALLBACK_MODEL_PATHS = [
    ROOT_DIR / "artifacts" / "baseline_model_v2.pkl",
    ROOT_DIR / "artifacts" / "baseline_model.pkl",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--text", action="append", default=[])
    parser.add_argument("--stdin", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    texts: list[str] = list(args.text)
    if args.stdin:
        stdin_text = sys.stdin.read().strip()
        if stdin_text:
            texts.append(stdin_text)
    if not texts:
        raise SystemExit("Provide at least one --text value or pass input via --stdin.")

    model_path = args.model_path.resolve()
    if not model_path.exists() and model_path == DEFAULT_MODEL_PATH.resolve():
        for fallback_path in FALLBACK_MODEL_PATHS:
            if fallback_path.resolve().exists():
                model_path = fallback_path.resolve()
                break
    model = ToxicityBaselineModel.load(model_path)
    predictions = [prediction.to_dict() for prediction in model.predict(texts)]
    payload: dict[str, object]
    if len(predictions) == 1:
        payload = {"text": texts[0], "prediction": predictions[0]}
    else:
        payload = {
            "items": [
                {"text": text, "prediction": prediction}
                for text, prediction in zip(texts, predictions, strict=True)
            ]
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
