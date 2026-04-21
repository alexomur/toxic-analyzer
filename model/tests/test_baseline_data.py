import sqlite3
from pathlib import Path

from toxic_analyzer.baseline_data import create_dataset_bundle, load_labeled_comments


def build_sample_mixed_db(path: Path) -> None:
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
        for source in ("habr", "ok"):
            for index in range(8):
                safe_text = f"{source} safe discussion {index}"
                toxic_text = f"{source} toxic insult {index}"
                rows.append((row_id, source, safe_text, len(safe_text), 0, "labeled"))
                row_id += 1
                rows.append((row_id, source, toxic_text, len(toxic_text), 1, "labeled"))
                row_id += 1
        rows.append(
            (row_id, "ok", "same label duplicate", len("same label duplicate"), 1, "labeled")
        )
        row_id += 1
        rows.append(
            (row_id, "habr", "same label duplicate", len("same label duplicate"), 1, "labeled")
        )
        row_id += 1
        rows.append((row_id, "ok", "ambiguous text", len("ambiguous text"), 0, "labeled"))
        row_id += 1
        rows.append((row_id, "dvach", "ambiguous text", len("ambiguous text"), 1, "labeled"))
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


def test_load_labeled_comments_drops_conflicts_and_duplicate_texts(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_sample_mixed_db(dataset_path)

    records, stats = load_labeled_comments(dataset_path)

    assert stats["loaded_rows"] == 36
    assert stats["dropped_conflicting_rows"] == 2
    assert stats["dropped_duplicate_rows"] == 1
    assert stats["kept_rows"] == 33
    texts = [record.text for record in records]
    assert texts.count("same label duplicate") == 1
    assert "ambiguous text" not in texts


def test_create_dataset_bundle_preserves_source_label_strata(tmp_path: Path) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    build_sample_mixed_db(dataset_path)

    bundle = create_dataset_bundle(dataset_path=dataset_path, random_seed=7)

    assert len(bundle.train) + len(bundle.validation) + len(bundle.test) == 33
    assert bundle.dataset_stats["splits"]["train"]["rows"] == len(bundle.train)
    assert set(bundle.train.sources) == {"habr", "ok"}
    assert set(bundle.validation.sources) == {"habr", "ok"}
    assert set(bundle.test.sources) == {"habr", "ok"}
    assert set(bundle.train.labels) == {0, 1}
    assert set(bundle.validation.labels) == {0, 1}
    assert set(bundle.test.labels) == {0, 1}
