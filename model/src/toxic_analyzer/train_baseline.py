"""Train the baseline toxicity classifier on the mixed dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from toxic_analyzer.baseline_data import DEFAULT_MIXED_DATASET_PATH, create_dataset_bundle
from toxic_analyzer.baseline_model import BaselineTrainingConfig, train_baseline_model
from toxic_analyzer.hard_case_dataset import load_hard_case_dataset

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_OUTPUT_PATH = ROOT_DIR / "artifacts" / "baseline_model_v3_2.pkl"
DEFAULT_REPORT_OUTPUT_PATH = ROOT_DIR / "artifacts" / "baseline_training_report_v3_2.json"
DEFAULT_HARD_CASE_DATASET_PATH = ROOT_DIR / "configs" / "baseline_hard_cases_v3.jsonl"
DEFAULT_SEED_DATASET_PATH = ROOT_DIR / "configs" / "baseline_seed_examples_v3.jsonl"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-db", type=Path, default=DEFAULT_MIXED_DATASET_PATH)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL_OUTPUT_PATH)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_OUTPUT_PATH)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--train-size", type=float, default=0.7)
    parser.add_argument("--validation-size", type=float, default=0.15)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--logistic-c", type=float, default=4.0)
    parser.add_argument("--logistic-max-iter", type=int, default=1000)
    parser.add_argument("--min-df", type=int, default=2)
    parser.add_argument("--max-word-features", type=int, default=100_000)
    parser.add_argument("--max-char-features", type=int, default=150_000)
    parser.add_argument("--select-k-best", type=int, default=120_000)
    parser.add_argument("--threshold-grid-size", type=int, default=181)
    parser.add_argument("--calibration-method", choices=["sigmoid", "isotonic"], default="sigmoid")
    parser.add_argument("--no-expert-features", action="store_true")
    parser.add_argument("--hard-case-dataset", type=Path, default=DEFAULT_HARD_CASE_DATASET_PATH)
    parser.add_argument("--seed-dataset", type=Path, default=DEFAULT_SEED_DATASET_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_bundle = create_dataset_bundle(
        dataset_path=args.dataset_db.resolve(),
        train_size=float(args.train_size),
        validation_size=float(args.validation_size),
        test_size=float(args.test_size),
        random_seed=int(args.random_seed),
    )
    config = BaselineTrainingConfig(
        random_seed=int(args.random_seed),
        logistic_c=float(args.logistic_c),
        logistic_max_iter=int(args.logistic_max_iter),
        min_df=int(args.min_df),
        max_word_features=int(args.max_word_features) or None,
        max_char_features=int(args.max_char_features) or None,
        select_k_best=int(args.select_k_best),
        threshold_grid_size=int(args.threshold_grid_size),
        use_expert_features=not bool(args.no_expert_features),
        calibration_method=str(args.calibration_method),
    )
    hard_case_path = args.hard_case_dataset.resolve()
    hard_case_dataset = load_hard_case_dataset(hard_case_path) if hard_case_path.exists() else None
    seed_path = args.seed_dataset.resolve()
    seed_dataset = load_hard_case_dataset(seed_path) if seed_path.exists() else None
    model, report = train_baseline_model(
        dataset_bundle,
        config=config,
        hard_case_dataset=hard_case_dataset,
        seed_dataset=seed_dataset,
    )

    model_output = args.model_output.resolve()
    report_output = args.report_output.resolve()
    model.save(model_output)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    test_metrics = report["metrics"]["test"]["overall"]
    print(
        "[train-baseline] Done: "
        f"threshold={model.threshold:.4f} "
        f"f1={test_metrics['f1']:.4f} "
        f"precision={test_metrics['precision']:.4f} "
        f"recall={test_metrics['recall']:.4f}",
        flush=True,
    )
    if "hard_cases" in report:
        hard_case_metrics = report["hard_cases"]["overall"]
        print(
            "[train-baseline] Hard cases: "
            f"f1={hard_case_metrics['f1']:.4f} "
            f"precision={hard_case_metrics['precision']:.4f} "
            f"recall={hard_case_metrics['recall']:.4f}",
            flush=True,
        )
    if "seed_dataset" in report:
        print(
            f"[train-baseline] Seed examples: rows={report['seed_dataset']['rows']}",
            flush=True,
        )
    print(f"[train-baseline] Model: {model_output}", flush=True)
    print(f"[train-baseline] Report: {report_output}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
