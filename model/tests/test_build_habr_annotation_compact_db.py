import sqlite3
from pathlib import Path

from toxic_analyzer.build_habr_annotation_compact_db import (
    CompactBuildConfig,
    normalize_label_status_from_ready,
    run_build,
)


def create_input_jsonl(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                '{"comment_id":101,"habr_score":4,"raw_text":"first","is_annotation_ready":true}',
                '{"comment_id":102,"habr_score":7,"raw_text":"second","is_annotation_ready":true}',
                '{"comment_id":103,"habr_score":0,"raw_text":"third","is_annotation_ready":false}',
            ]
        ),
        encoding="utf-8",
    )


def test_normalize_label_status_from_ready_uses_pending_and_excluded_only() -> None:
    assert normalize_label_status_from_ready(True) == "pending"
    assert normalize_label_status_from_ready(False) == "excluded"


def test_run_build_creates_compact_sqlite_from_jsonl(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "source.jsonl"
    output_db = tmp_path / "compact.sqlite3"
    create_input_jsonl(input_jsonl)

    stats = run_build(
        CompactBuildConfig(
            input_jsonl=input_jsonl,
            output_db=output_db,
            rebuild=True,
        )
    )

    assert stats == {
        "rows": 3,
        "pending_rows": 2,
        "labeled_rows": 0,
        "excluded_rows": 1,
    }

    connection = sqlite3.connect(output_db)
    try:
        rows = connection.execute(
            """
            SELECT id, comment_id, habr_score, raw_text, toxic_label, label_status
            FROM comments
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [
        (1, 101, 4, "first", None, "pending"),
        (2, 102, 7, "second", None, "pending"),
        (3, 103, 0, "third", None, "excluded"),
    ]
