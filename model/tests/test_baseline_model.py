import sqlite3
from pathlib import Path

from toxic_analyzer.baseline_data import create_dataset_bundle
from toxic_analyzer.baseline_model import (
    BaselineTrainingConfig,
    ToxicityBaselineModel,
    train_baseline_model,
)


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
