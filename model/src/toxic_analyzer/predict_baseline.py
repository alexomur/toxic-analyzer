"""Run inference with a saved baseline toxicity model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from toxic_analyzer.inference_service import ToxicityInferenceService
from toxic_analyzer.model_runtime import DEFAULT_MODEL_PATH, build_missing_model_message


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

    try:
        service = ToxicityInferenceService.from_path(args.model_path)
    except FileNotFoundError as exc:
        missing_path = Path(str(exc.args[0]))
        raise SystemExit(build_missing_model_message(missing_path)) from exc

    payload = (
        service.build_single_response_payload(texts[0])
        if len(texts) == 1
        else service.build_batch_response_payload(texts)
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
