import sqlite3
from pathlib import Path

from toxic_analyzer.build_mixed_toxic_dataset import (
    MixedDatasetBuildConfig,
    parse_ok_line,
    run_build,
)


def test_parse_ok_line_supports_multiple_labels() -> None:
    labels, text = parse_ok_line("__label__INSULT,__label__THREAT сколько вас еще терпеть")

    assert labels == ["__label__INSULT", "__label__THREAT"]
    assert text == "сколько вас еще терпеть"


def test_run_build_creates_mixed_dataset_with_bool_labels(tmp_path: Path) -> None:
    dvach_csv = tmp_path / "labeled.csv"
    dvach_csv.write_text(
        "comment,toxic\n"
        "\"toxic dvach\",1.0\n"
        "\"safe dvach 1\",0.0\n"
        "\"safe dvach 2\",0.0\n",
        encoding="utf-8",
    )

    ok_dataset = tmp_path / "dataset.txt"
    ok_dataset.write_text(
        "__label__INSULT toxic ok\n"
        "__label__NORMAL safe ok 1\n"
        "__label__NORMAL safe ok 2\n",
        encoding="utf-8",
    )

    habr_db = tmp_path / "habr.sqlite3"
    too_long_text = "x" * 251
    connection = sqlite3.connect(habr_db)
    try:
        connection.executescript(
            """
            CREATE TABLE comments (
                id INTEGER PRIMARY KEY,
                comment_id INTEGER NOT NULL UNIQUE,
                habr_score INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                toxic_label TEXT,
                label_status TEXT NOT NULL
            );
            INSERT INTO comments (id, comment_id, habr_score, raw_text, toxic_label, label_status)
            VALUES
                (1, 101, 0, 'habr one', NULL, 'pending'),
                (2, 102, 0, 'habr [code] skip', NULL, 'pending'),
                (3, 103, 0, 'habr two', NULL, 'pending');
            """
        )
        connection.execute(
            """
            INSERT INTO comments (
                id, comment_id, habr_score, raw_text, toxic_label, label_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (4, 104, 0, too_long_text, None, "pending"),
        )
        connection.commit()
    finally:
        connection.close()

    output_db = tmp_path / "mixed.sqlite3"
    report_path = tmp_path / "report.json"
    report = run_build(
        MixedDatasetBuildConfig(
            dvach_csv=dvach_csv,
            ok_dataset=ok_dataset,
            habr_db=habr_db,
            output_db=output_db,
            report_path=report_path,
            random_seed=7,
            rebuild=True,
        )
    )

    assert report["totals"] == {"rows": 6, "labeled_rows": 4, "pending_rows": 2}
    assert report["sources"]["habr"]["total"] == 2
    assert report["sources"]["dvach"]["non_toxic"] == 1
    assert report["sources"]["ok"]["non_toxic"] == 1

    connection = sqlite3.connect(output_db)
    try:
        rows = connection.execute(
            """
            SELECT source, source_row_id, source_comment_id, raw_text, is_toxic, label_status
            FROM comments
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    assert sorted(rows) == sorted(
        [
            ("dvach", "1", None, "toxic dvach", 1, "labeled"),
            ("dvach", "3", None, "safe dvach 2", 0, "labeled"),
            ("ok", "1", None, "toxic ok", 1, "labeled"),
            ("ok", "2", None, "safe ok 1", 0, "labeled"),
            ("habr", "1", 101, "habr one", None, "pending"),
            ("habr", "3", 103, "habr two", None, "pending"),
        ]
    )

    source_runs = 1
    for left, right in zip(rows, rows[1:], strict=False):
        if left[0] != right[0]:
            source_runs += 1
    assert source_runs > 3
