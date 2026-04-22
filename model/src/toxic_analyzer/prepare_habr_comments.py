"""Download, flatten and clean Habr comments for manual toxicity annotation."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import html
import json
import re
import sqlite3
import sys
import tomllib
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download, list_repo_files

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT_DIR / "configs" / "habr_comments.toml"

ARTICLE_COLUMNS = [
    "id",
    "language",
    "url",
    "title",
    "time_published",
    "statistics",
    "comments",
]

URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
HTML_TAG_PATTERN = re.compile(r"(?is)<[^>]+>")
HTML_BREAK_PATTERN = re.compile(r"(?i)<\s*(?:br|/p|/div|/li)\s*/?>")
HTML_BLOCKQUOTE_PATTERN = re.compile(r"(?is)<blockquote[^>]*>")
HTML_CODE_BLOCK_PATTERN = re.compile(r"(?is)<(?:pre|code)[^>]*>.*?</(?:pre|code)>")
MARKDOWN_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
WHITESPACE_PATTERN = re.compile(r"[ \t\f\v]+")
NEWLINE_PATTERN = re.compile(r"\n{3,}")
WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]+")
CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁё]")
LATIN_PATTERN = re.compile(r"[A-Za-z]")

RUSSIAN_STOPWORDS = {
    "а",
    "без",
    "был",
    "бы",
    "быть",
    "в",
    "вам",
    "вас",
    "вот",
    "все",
    "вы",
    "где",
    "да",
    "для",
    "его",
    "ее",
    "если",
    "есть",
    "еще",
    "же",
    "за",
    "здесь",
    "и",
    "из",
    "или",
    "им",
    "их",
    "к",
    "как",
    "когда",
    "кто",
    "ли",
    "мне",
    "мы",
    "на",
    "надо",
    "не",
    "него",
    "нет",
    "но",
    "ну",
    "о",
    "об",
    "она",
    "они",
    "оно",
    "от",
    "по",
    "под",
    "после",
    "потому",
    "при",
    "про",
    "раз",
    "с",
    "со",
    "так",
    "там",
    "тем",
    "то",
    "только",
    "ты",
    "у",
    "уж",
    "уже",
    "хоть",
    "чего",
    "что",
    "чтобы",
    "эта",
    "эти",
    "это",
    "я",
}

CODE_KEYWORDS = {
    "api",
    "class",
    "const",
    "curl",
    "def",
    "docker",
    "else",
    "function",
    "git",
    "html",
    "if",
    "import",
    "json",
    "kubectl",
    "lambda",
    "let",
    "pip",
    "public",
    "private",
    "return",
    "select",
    "sql",
    "sudo",
    "var",
    "xml",
}


@dataclass(slots=True)
class SourceConfig:
    repo_id: str
    repo_type: str
    remote_pattern: str
    article_batch_size: int
    max_shards: int


@dataclass(slots=True)
class OutputConfig:
    prepared_jsonl: Path
    report_json: Path
    dedup_sqlite: Path
    progress_json: Path


@dataclass(slots=True)
class FilterConfig:
    min_cyrillic_letters: int
    strict_cyrillic_ratio: float
    mixed_cyrillic_ratio: float
    short_comment_cyrillic_ratio: float
    min_short_comment_letters: int
    min_meaningful_words: int


@dataclass(slots=True)
class PreparationConfig:
    source: SourceConfig
    output: OutputConfig
    filters: FilterConfig


class DedupStore:
    """Disk-backed deduplication by `clean_text` hash."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS seen (hash TEXT PRIMARY KEY)")
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def add(self, text: str) -> bool:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        try:
            self.connection.execute("INSERT INTO seen (hash) VALUES (?)", (digest,))
        except sqlite3.IntegrityError:
            return False
        return True

    def flush(self) -> None:
        self.connection.commit()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the TOML config file.",
    )
    parser.add_argument(
        "--max-shards",
        type=int,
        default=None,
        help="Optional override for the number of remote parquet shards to process.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing JSONL/Dedup state instead of starting from scratch.",
    )
    parser.add_argument(
        "--start-shard",
        type=int,
        default=None,
        help="1-based shard index to start from. Useful together with --resume.",
    )
    return parser.parse_args(argv)


def load_config(path: Path, max_shards_override: int | None = None) -> PreparationConfig:
    with path.open("rb") as handle:
        raw_config = tomllib.load(handle)

    source = raw_config["source"]
    output = raw_config["output"]
    filters = raw_config["filters"]

    max_shards = int(source["max_shards"])
    if max_shards_override is not None:
        max_shards = max_shards_override

    return PreparationConfig(
        source=SourceConfig(
            repo_id=source["repo_id"],
            repo_type=source["repo_type"],
            remote_pattern=source["remote_pattern"],
            article_batch_size=int(source["article_batch_size"]),
            max_shards=max_shards,
        ),
        output=OutputConfig(
            prepared_jsonl=resolve_from_root(output["prepared_jsonl"]),
            report_json=resolve_from_root(output["report_json"]),
            dedup_sqlite=resolve_from_root(output["dedup_sqlite"]),
            progress_json=resolve_from_root(output["progress_json"]),
        ),
        filters=FilterConfig(
            min_cyrillic_letters=int(filters["min_cyrillic_letters"]),
            strict_cyrillic_ratio=float(filters["strict_cyrillic_ratio"]),
            mixed_cyrillic_ratio=float(filters["mixed_cyrillic_ratio"]),
            short_comment_cyrillic_ratio=float(filters["short_comment_cyrillic_ratio"]),
            min_short_comment_letters=int(filters["min_short_comment_letters"]),
            min_meaningful_words=int(filters["min_meaningful_words"]),
        ),
    )


def resolve_from_root(relative_path: str) -> Path:
    return (ROOT_DIR / relative_path).resolve()


def list_remote_parquet_files(config: SourceConfig) -> list[str]:
    files = [
        path
        for path in list_repo_files(config.repo_id, repo_type=config.repo_type)
        if fnmatch.fnmatch(path, config.remote_pattern)
    ]
    files.sort()
    if config.max_shards > 0:
        return files[: config.max_shards]
    return files


def iter_article_rows(parquet_paths: Iterable[Path], batch_size: int) -> Iterator[dict[str, Any]]:
    for parquet_path in parquet_paths:
        parquet_file = pq.ParquetFile(parquet_path)
        for batch in parquet_file.iter_batches(
            batch_size=batch_size,
            columns=ARTICLE_COLUMNS,
            use_threads=True,
        ):
            yield from batch.to_pylist()


def extract_comment_text(comment: dict[str, Any]) -> tuple[str, str]:
    markdown = (comment.get("message_markdown") or "").strip()
    html_value = comment.get("message_html") or ""
    if markdown:
        raw_text = markdown
    else:
        raw_text = html_to_text(html_value)
    clean_text = clean_text_for_annotation(raw_text)
    return raw_text, clean_text


def html_to_text(value: str) -> str:
    text = html.unescape(value)
    text = HTML_CODE_BLOCK_PATTERN.sub(" <CODE_BLOCK> ", text)
    text = HTML_BLOCKQUOTE_PATTERN.sub("\n> ", text)
    text = HTML_BREAK_PATTERN.sub("\n", text)
    text = HTML_TAG_PATTERN.sub(" ", text)
    return normalize_text(text)


def clean_text_for_annotation(value: str) -> str:
    text = html.unescape(value)
    text = MARKDOWN_CODE_BLOCK_PATTERN.sub(" <CODE_BLOCK> ", text)
    text = EMAIL_PATTERN.sub(" <EMAIL> ", text)
    text = URL_PATTERN.sub(" <URL> ", text)
    return normalize_text(text)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    text = NEWLINE_PATTERN.sub("\n\n", text)
    return text.strip()


def build_comment_record(
    article: dict[str, Any],
    comment: dict[str, Any],
    filters: FilterConfig,
) -> dict[str, Any]:
    raw_text, clean_text = extract_comment_text(comment)
    text_stats = describe_text(clean_text)

    is_low_content = detect_low_content(clean_text, text_stats, filters)
    is_mostly_code = detect_mostly_code(clean_text)
    is_mostly_latin = detect_mostly_latin(text_stats, filters)
    is_russian = detect_russian(
        article_language=article.get("language", ""),
        text_stats=text_stats,
        filters=filters,
        is_mostly_latin=is_mostly_latin,
    )
    is_annotation_ready = is_russian and not is_low_content and not is_mostly_code

    statistics = article.get("statistics") or {}
    return {
        "article_id": int(article["id"]),
        "article_url": article.get("url") or "",
        "article_title": article.get("title") or "",
        "article_language": article.get("language") or "",
        "article_time_published": int(article.get("time_published") or 0),
        "article_habr_score": int(statistics.get("score") or 0),
        "comment_id": int(comment["id"]),
        "parent_id": int(comment.get("parent_id") or 0),
        "level": int(comment.get("level") or 0),
        "time_published": int(comment.get("time_published") or 0),
        "habr_score": int(comment.get("score") or 0),
        "votes": int(comment.get("votes") or 0),
        "author": comment.get("author") or "",
        "raw_text": raw_text,
        "clean_text": clean_text,
        "has_russian_stopword": text_stats["has_russian_stopword"],
        "word_count": text_stats["word_count"],
        "letter_count": text_stats["letter_count"],
        "cyrillic_letters": text_stats["cyrillic_letters"],
        "latin_letters": text_stats["latin_letters"],
        "cyrillic_ratio": round(text_stats["cyrillic_ratio"], 4),
        "is_russian": is_russian,
        "is_mostly_code": is_mostly_code,
        "is_mostly_latin": is_mostly_latin,
        "is_low_content": is_low_content,
        "is_annotation_ready": is_annotation_ready,
    }


def describe_text(text: str) -> dict[str, Any]:
    words = [token.lower() for token in WORD_PATTERN.findall(text)]
    letter_count = len(CYRILLIC_PATTERN.findall(text)) + len(LATIN_PATTERN.findall(text))
    cyrillic_letters = len(CYRILLIC_PATTERN.findall(text))
    latin_letters = len(LATIN_PATTERN.findall(text))
    cyrillic_ratio = cyrillic_letters / letter_count if letter_count else 0.0
    has_russian_stopword = any(token in RUSSIAN_STOPWORDS for token in words)

    return {
        "word_count": len(words),
        "letter_count": letter_count,
        "cyrillic_letters": cyrillic_letters,
        "latin_letters": latin_letters,
        "cyrillic_ratio": cyrillic_ratio,
        "has_russian_stopword": has_russian_stopword,
        "words": words,
    }


def detect_low_content(text: str, stats: dict[str, Any], filters: FilterConfig) -> bool:
    masked_only = re.sub(r"<(?:URL|EMAIL|CODE_BLOCK)>", " ", text)
    masked_only = normalize_text(masked_only)
    if not masked_only:
        return True
    if stats["word_count"] < filters.min_meaningful_words:
        return True
    if stats["letter_count"] == 0:
        return True
    if stats["word_count"] == 1 and stats["letter_count"] < filters.min_short_comment_letters:
        return True
    if re.fullmatch(r"[\W_]+", masked_only):
        return True
    return False


def detect_mostly_latin(stats: dict[str, Any], filters: FilterConfig) -> bool:
    if stats["latin_letters"] < filters.min_short_comment_letters:
        return False
    return (
        stats["cyrillic_letters"] < filters.min_cyrillic_letters
        and stats["latin_letters"] > stats["cyrillic_letters"]
    )


def detect_russian(
    *,
    article_language: str,
    text_stats: dict[str, Any],
    filters: FilterConfig,
    is_mostly_latin: bool,
) -> bool:
    if article_language != "ru":
        return False
    if is_mostly_latin:
        return False
    if text_stats["cyrillic_letters"] < filters.min_cyrillic_letters:
        return False
    if text_stats["word_count"] <= 2:
        return (
            text_stats["cyrillic_letters"] >= filters.min_short_comment_letters
            and text_stats["cyrillic_ratio"] >= filters.short_comment_cyrillic_ratio
        )
    if text_stats["cyrillic_ratio"] >= filters.strict_cyrillic_ratio:
        return True
    if (
        text_stats["cyrillic_ratio"] >= filters.mixed_cyrillic_ratio
        and text_stats["has_russian_stopword"]
    ):
        return True
    return False


def detect_mostly_code(text: str) -> bool:
    if "<CODE_BLOCK>" in text:
        return True

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False

    code_like_lines = 0
    for line in lines:
        words = {token.lower() for token in WORD_PATTERN.findall(line)}
        indicators = 0
        if re.search(r"[{}();=<>]{2,}", line):
            indicators += 1
        if words & CODE_KEYWORDS:
            indicators += 1
        if re.search(r"^(?:\$|#|>>>|\w+@\w+[:~$])", line):
            indicators += 1
        if re.search(r"</?[A-Za-z][^>]*>", line):
            indicators += 1
        if re.search(r"\b\w+\([^)]*\)", line):
            indicators += 1
        if indicators >= 2:
            code_like_lines += 1

    return code_like_lines >= 2 and code_like_lines / len(lines) >= 0.5


def ensure_parent_dirs(config: PreparationConfig) -> None:
    config.output.prepared_jsonl.parent.mkdir(parents=True, exist_ok=True)
    config.output.report_json.parent.mkdir(parents=True, exist_ok=True)
    config.output.dedup_sqlite.parent.mkdir(parents=True, exist_ok=True)
    config.output.progress_json.parent.mkdir(parents=True, exist_ok=True)


def remove_previous_outputs(config: PreparationConfig) -> None:
    for path in (
        config.output.prepared_jsonl,
        config.output.report_json,
        config.output.dedup_sqlite,
        config.output.progress_json,
    ):
        if path.exists():
            path.unlink()


def load_progress(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_progress(
    *,
    config: PreparationConfig,
    total_shards: int,
    shard_index: int,
    remote_path: str,
    counters: Counter[str],
    resumed: bool,
) -> None:
    progress = {
        "status": "running",
        "resumed": resumed,
        "total_shards": total_shards,
        "last_completed_shard_index": shard_index,
        "next_shard_index": shard_index + 1,
        "last_completed_remote_path": remote_path,
        "counters": dict(sorted(counters.items())),
    }
    config.output.progress_json.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def finalize_progress(
    *,
    config: PreparationConfig,
    total_shards: int,
    counters: Counter[str],
    resumed: bool,
) -> None:
    progress = {
        "status": "completed",
        "resumed": resumed,
        "total_shards": total_shards,
        "last_completed_shard_index": total_shards,
        "next_shard_index": total_shards + 1,
        "counters": dict(sorted(counters.items())),
    }
    config.output.progress_json.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def infer_resume_start_shard(
    *,
    total_shards: int,
    start_shard: int | None,
    progress: dict[str, Any] | None,
) -> int:
    if start_shard is not None:
        if start_shard < 1 or start_shard > total_shards:
            raise ValueError(
                f"--start-shard must be within 1..{total_shards}, got {start_shard}."
            )
        return start_shard

    if progress:
        next_shard_index = int(progress.get("next_shard_index", 1))
        if next_shard_index < 1 or next_shard_index > total_shards + 1:
            raise ValueError(
                "Invalid progress checkpoint: next_shard_index is outside the known shard range."
            )
        return next_shard_index

    return 1


def seed_counters_from_progress(progress: dict[str, Any] | None) -> Counter[str]:
    counters: Counter[str] = Counter()
    if progress:
        counters.update(progress.get("counters") or {})
    return counters


def rebuild_dedup_from_output(output_path: Path, dedup: DedupStore) -> int:
    if not output_path.exists():
        return 0

    restored = 0
    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            record = json.loads(payload)
            clean_text = record.get("clean_text")
            if not clean_text:
                continue
            dedup.add(clean_text)
            restored += 1
            if restored % 10000 == 0:
                dedup.flush()

    dedup.flush()
    return restored


def write_report(
    *,
    config: PreparationConfig,
    shard_count: int,
    counters: Counter[str],
    resumed: bool,
    start_shard: int,
) -> None:
    report = {
        "source": {
            "repo_id": config.source.repo_id,
            "repo_type": config.source.repo_type,
            "remote_pattern": config.source.remote_pattern,
            "processed_shards": shard_count,
            "start_shard": start_shard,
            "resumed": resumed,
        },
        "output": {
            "prepared_jsonl": str(config.output.prepared_jsonl),
            "report_json": str(config.output.report_json),
            "progress_json": str(config.output.progress_json),
        },
        "counters": dict(sorted(counters.items())),
        "filters": asdict(config.filters),
    }
    config.output.report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_preparation(
    config: PreparationConfig,
    *,
    resume: bool = False,
    start_shard: int | None = None,
) -> Counter[str]:
    ensure_parent_dirs(config)
    remote_files = list_remote_parquet_files(config.source)
    total_shards = len(remote_files)

    if not resume:
        remove_previous_outputs(config)

    progress = load_progress(config.output.progress_json) if resume else None
    shard_start = infer_resume_start_shard(
        total_shards=total_shards,
        start_shard=start_shard,
        progress=progress,
    )

    counters = seed_counters_from_progress(progress) if resume else Counter()
    if resume and config.output.report_json.exists():
        config.output.report_json.unlink()

    dedup = DedupStore(config.output.dedup_sqlite)
    restored_kept = rebuild_dedup_from_output(config.output.prepared_jsonl, dedup) if resume else 0
    if resume:
        counters["comments_kept"] = max(counters.get("comments_kept", 0), restored_kept)
        counters["resume_rebuilt_kept"] = restored_kept

    output_mode = "a" if resume else "w"

    try:
        with config.output.prepared_jsonl.open(output_mode, encoding="utf-8") as output_file:
            for shard_index, remote_path in enumerate(remote_files, start=1):
                if shard_index < shard_start:
                    continue

                local_path = hf_hub_download(
                    config.source.repo_id,
                    remote_path,
                    repo_type=config.source.repo_type,
                )
                parquet_path = Path(local_path)
                print(
                    (
                        "[prepare-habr-comments] "
                        f"Shard {shard_index}/{total_shards}: {parquet_path.name}"
                    ),
                    flush=True,
                )
                counters["remote_shards"] += 1
                for article in iter_article_rows([parquet_path], config.source.article_batch_size):
                    counters["articles_seen"] += 1
                    comments = article.get("comments") or []
                    if article.get("language") != "ru":
                        counters["articles_non_ru"] += 1
                        continue
                    if not comments:
                        counters["articles_without_comments"] += 1
                        continue

                    for comment in comments:
                        counters["comments_seen"] += 1
                        record = build_comment_record(article, comment, config.filters)

                        if not record["is_russian"]:
                            counters["comments_non_russian"] += 1
                            continue
                        if record["is_low_content"]:
                            counters["comments_low_content"] += 1
                            continue
                        if record["is_mostly_code"]:
                            counters["comments_mostly_code"] += 1
                            continue
                        if not dedup.add(record["clean_text"]):
                            counters["comments_duplicate"] += 1
                            continue

                        counters["comments_kept"] += 1
                        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                    if counters["articles_seen"] % 1000 == 0:
                        dedup.flush()
                        print(
                            "[prepare-habr-comments] "
                            f"articles={counters['articles_seen']} "
                            f"comments={counters['comments_seen']} "
                            f"kept={counters['comments_kept']}",
                            flush=True,
                        )

                dedup.flush()
                write_progress(
                    config=config,
                    total_shards=total_shards,
                    shard_index=shard_index,
                    remote_path=remote_path,
                    counters=counters,
                    resumed=resume,
                )
    finally:
        dedup.flush()
        dedup.close()

    finalize_progress(
        config=config,
        total_shards=total_shards,
        counters=counters,
        resumed=resume,
    )
    write_report(
        config=config,
        shard_count=counters["remote_shards"],
        counters=counters,
        resumed=resume,
        start_shard=shard_start,
    )
    return counters


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config, max_shards_override=args.max_shards)
    counters = run_preparation(
        config,
        resume=args.resume,
        start_shard=args.start_shard,
    )
    print(
        "[prepare-habr-comments] Done: "
        f"kept={counters['comments_kept']} comments from {counters['comments_seen']} seen.",
        flush=True,
    )
    print(
        f"[prepare-habr-comments] Output: {config.output.prepared_jsonl}",
        flush=True,
    )
    print(
        f"[prepare-habr-comments] Report: {config.output.report_json}",
        flush=True,
    )
    print(
        f"[prepare-habr-comments] Progress: {config.output.progress_json}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
