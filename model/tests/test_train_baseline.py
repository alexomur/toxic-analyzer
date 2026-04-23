
import json
import sqlite3
from pathlib import Path

from toxic_analyzer import train_baseline


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
                safe_text = f"{source} calm technical discussion {index}"
                toxic_text = f"{source} stupid toxic insult {index}"
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


def test_train_baseline_main_keeps_sqlite_cli_working(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    model_output = tmp_path / "baseline.pkl"
    report_output = tmp_path / "report.json"
    build_training_db(dataset_path)

    exit_code = train_baseline.main(
        [
            "--dataset-db",
            str(dataset_path),
            "--model-output",
            str(model_output),
            "--report-output",
            str(report_output),
            "--min-df",
            "1",
            "--max-word-features",
            "200",
            "--max-char-features",
            "200",
            "--select-k-best",
            "100",
            "--threshold-grid-size",
            "31",
            "--hard-case-dataset",
            str(tmp_path / "missing-hard-cases.jsonl"),
            "--seed-dataset",
            str(tmp_path / "missing-seed.jsonl"),
        ]
    )

    assert exit_code == 0
    assert model_output.exists()
    report = json.loads(report_output.read_text(encoding="utf-8"))
    assert report["dataset"]["dataset_source"]["kind"] == "sqlite"
    assert report["dataset"]["dataset_source"]["path"] == str(dataset_path.resolve())
    assert report["metrics"]["test"]["overall"]["rows"] > 0
