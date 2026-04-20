from toxic_analyzer.prepare_habr_comments import (
    FilterConfig,
    build_comment_record,
    clean_text_for_annotation,
    describe_text,
    detect_mostly_code,
    detect_russian,
    html_to_text,
    infer_resume_start_shard,
)

DEFAULT_FILTERS = FilterConfig(
    min_cyrillic_letters=3,
    strict_cyrillic_ratio=0.55,
    mixed_cyrillic_ratio=0.35,
    short_comment_cyrillic_ratio=0.85,
    min_short_comment_letters=4,
    min_meaningful_words=1,
)


def test_html_to_text_removes_tags() -> None:
    value = "<div>Привет<br/>мир</div>"
    assert html_to_text(value) == "Привет\nмир"


def test_clean_text_preserves_latin_and_masks_urls() -> None:
    value = "Пишу на Python, docs: https://example.com"
    assert clean_text_for_annotation(value) == "Пишу на Python, docs: <URL>"


def test_detect_russian_accepts_mixed_technical_comment() -> None:
    stats = describe_text("Я использую Python и Docker в проде")
    assert detect_russian(
        article_language="ru",
        text_stats=stats,
        filters=DEFAULT_FILTERS,
        is_mostly_latin=False,
    )


def test_detect_mostly_code_marks_code_blocks() -> None:
    text = "def foo():\n    return 1\nprint(foo())"
    assert detect_mostly_code(text)


def test_build_comment_record_filters_english_comment_inside_ru_article() -> None:
    article = {
        "id": 1,
        "language": "ru",
        "url": "https://habr.com/ru/post/1/",
        "title": "Test",
        "time_published": 1,
        "statistics": {"score": 5},
    }
    comment = {
        "id": 2,
        "parent_id": 0,
        "level": 0,
        "time_published": 2,
        "score": 1,
        "votes": 1,
        "message_html": "<div>Hello world</div>",
        "message_markdown": "Hello world",
        "author": "tester",
    }

    record = build_comment_record(article, comment, DEFAULT_FILTERS)

    assert record["is_russian"] is False
    assert record["is_annotation_ready"] is False


def test_infer_resume_start_shard_uses_progress_when_no_manual_override() -> None:
    progress = {"next_shard_index": 8}
    assert infer_resume_start_shard(total_shards=31, start_shard=None, progress=progress) == 8


def test_infer_resume_start_shard_prefers_manual_override() -> None:
    progress = {"next_shard_index": 8}
    assert infer_resume_start_shard(total_shards=31, start_shard=5, progress=progress) == 5
