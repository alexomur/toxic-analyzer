import sqlite3
from pathlib import Path

from toxic_analyzer.build_habr_annotation_db import (
    BuildConfig,
    build_annotation_context,
    comment_to_row,
    run_build,
)


def test_build_annotation_context_includes_parent_when_available() -> None:
    context = build_annotation_context(
        article_title="Тестовая статья",
        clean_text="Комментарий",
        parent_clean_text="Родитель",
    )

    assert "Статья: Тестовая статья" in context
    assert "Родительский комментарий:\nРодитель" in context
    assert "Комментарий:\nКомментарий" in context


def test_comment_to_row_marks_non_ready_comment_as_excluded() -> None:
    record = {
        "article_id": 1,
        "article_title": "Test",
        "article_url": "https://example.com",
        "article_time_published": 10,
        "comment_id": 2,
        "parent_id": 0,
        "level": 1,
        "time_published": 11,
        "habr_score": 3,
        "votes": 7,
        "raw_text": "raw",
        "clean_text": "clean",
        "is_russian": True,
        "is_mostly_code": False,
        "is_low_content": True,
        "is_annotation_ready": False,
    }

    row = comment_to_row(record, "IlyaGusev/habr", "2026-01-01T00:00:00+00:00")

    assert row["annotation_status"] == "excluded"
    assert row["parent_comment_id"] is None


def test_run_build_creates_sqlite_with_parent_context(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "sample.jsonl"
    output_db = tmp_path / "sample.sqlite3"
    input_jsonl.write_text(
        "\n".join(
            [
                (
                    '{"article_id":1,"article_title":"Статья","article_url":"https://example.com",'
                    '"article_time_published":1,"comment_id":10,"parent_id":0,"level":0,'
                    '"time_published":2,"habr_score":5,"votes":3,"raw_text":"Первый","clean_text":"Первый",'
                    '"is_russian":true,"is_mostly_code":false,"is_low_content":false,'
                    '"is_annotation_ready":true}'
                ),
                (
                    '{"article_id":1,"article_title":"Статья","article_url":"https://example.com",'
                    '"article_time_published":1,"comment_id":11,"parent_id":10,"level":1,'
                    '"time_published":3,"habr_score":2,"votes":1,"raw_text":"Второй","clean_text":"Второй",'
                    '"is_russian":true,"is_mostly_code":false,"is_low_content":false,'
                    '"is_annotation_ready":true}'
                ),
            ]
        ),
        encoding="utf-8",
    )

    stats = run_build(
        BuildConfig(
            input_jsonl=input_jsonl,
            output_db=output_db,
            source_dataset="IlyaGusev/habr",
            batch_size=2,
            rebuild=True,
        )
    )

    assert stats["imported_rows"] == 2
    assert stats["pending_rows"] == 2
    assert stats["rows_with_parent_context"] == 1

    connection = sqlite3.connect(output_db)
    try:
        row = connection.execute(
            """
            SELECT annotation_status, parent_clean_text, annotation_context
            FROM comments
            WHERE comment_id = 11
            """
        ).fetchone()
    finally:
        connection.close()

    assert row[0] == "pending"
    assert row[1] == "Первый"
    assert "Родительский комментарий:\nПервый" in row[2]
