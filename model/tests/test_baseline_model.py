import json
import sqlite3
from pathlib import Path

from toxic_analyzer.baseline_data import create_dataset_bundle
from toxic_analyzer.baseline_model import (
    BaselineTrainingConfig,
    ToxicityBaselineModel,
    train_baseline_model,
)
from toxic_analyzer.hard_case_dataset import load_hard_case_dataset


def build_training_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE comments (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                text_length INTEGER NOT NULL,
                is_toxic INTEGER,
                label_status TEXT NOT NULL
            );
            """
        )
        rows = []
        row_id = 1
        for source in ("habr", "ok", "dvach"):
            for index in range(12):
                safe_text = (
                    f"{source} спокойное обсуждение технологии {index} "
                    "полезный разбор без оскорблений"
                )
                toxic_text = (
                    f"{source} тупой мерзкий автор {index} "
                    "оскорбление и агрессия в адрес собеседника"
                )
                rows.append((row_id, source, safe_text, len(safe_text), 0, "labeled"))
                row_id += 1
                rows.append((row_id, source, toxic_text, len(toxic_text), 1, "labeled"))
                row_id += 1
        connection.executemany(
            """
            INSERT INTO comments (id, source, raw_text, text_length, is_toxic, label_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def test_train_baseline_model_predicts_label_and_score(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_training_db(dataset_path)
    bundle = create_dataset_bundle(dataset_path=dataset_path, random_seed=11)

    model, report = train_baseline_model(
        bundle,
        config=BaselineTrainingConfig(
            random_seed=11,
            min_df=1,
            max_word_features=500,
            max_char_features=500,
            select_k_best=200,
            threshold_grid_size=41,
        ),
    )

    prediction = model.predict_one("ты мерзкий тупой человек")

    assert prediction.label in {0, 1}
    assert 0.0 <= prediction.score <= 1.0
    assert 0.0 <= prediction.toxic_probability <= 1.0
    assert "test" in report["metrics"]
    assert "overall" in report["metrics"]["test"]


def test_baseline_model_roundtrip_preserves_predictions(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_training_db(dataset_path)
    bundle = create_dataset_bundle(dataset_path=dataset_path, random_seed=13)

    model, _ = train_baseline_model(
        bundle,
        config=BaselineTrainingConfig(
            random_seed=13,
            min_df=1,
            max_word_features=500,
            max_char_features=500,
            select_k_best=200,
            threshold_grid_size=41,
        ),
    )
    model_path = tmp_path / "baseline.pkl"
    model.save(model_path)
    restored = ToxicityBaselineModel.load(model_path)

    original = model.predict_one("полезный и спокойный комментарий")
    reloaded = restored.predict_one("полезный и спокойный комментарий")

    assert original.to_dict() == reloaded.to_dict()


def test_train_baseline_model_reports_hard_case_metrics(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_training_db(dataset_path)
    hard_case_path = tmp_path / "hard_cases.jsonl"
    hard_case_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"text": "ты мерзкий идиот", "label": 1, "tags": ["targeted_insult"]},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"text": "Он неплохо справляется!", "label": 0, "tags": ["benign"]},
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    bundle = create_dataset_bundle(dataset_path=dataset_path, random_seed=17)
    hard_case_dataset = load_hard_case_dataset(hard_case_path)

    _, report = train_baseline_model(
        bundle,
        config=BaselineTrainingConfig(
            random_seed=17,
            min_df=1,
            max_word_features=500,
            max_char_features=500,
            select_k_best=200,
            threshold_grid_size=41,
            calibration_method="sigmoid",
        ),
        hard_case_dataset=hard_case_dataset,
    )

    assert "hard_cases" in report
    assert report["hard_cases"]["summary"]["rows"] == 2
    assert "targeted_insult" in report["hard_cases"]["per_tag"]


def test_train_baseline_model_reports_seed_dataset_summary(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_training_db(dataset_path)
    seed_path = tmp_path / "seed.jsonl"
    seed_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {"text": "ты чудище", "label": 1, "tags": ["seed"]},
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"text": "это плохой код", "label": 0, "tags": ["seed"]},
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    bundle = create_dataset_bundle(dataset_path=dataset_path, random_seed=19)
    seed_dataset = load_hard_case_dataset(seed_path)

    _, report = train_baseline_model(
        bundle,
        config=BaselineTrainingConfig(
            random_seed=19,
            min_df=1,
            max_word_features=500,
            max_char_features=500,
            select_k_best=200,
            threshold_grid_size=41,
        ),
        seed_dataset=seed_dataset,
    )

    assert report["seed_dataset"]["rows"] == 2
