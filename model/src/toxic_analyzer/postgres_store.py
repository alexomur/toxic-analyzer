"""PostgreSQL settings and helpers for model training data storage."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_POSTGRES_SCHEMA = "toxic_analyzer_model"
TRAINING_DATASET_VIEW_NAME = "training_examples_for_training"

POSTGRES_DSN_ENV = "TOXIC_ANALYZER_POSTGRES_DSN"
POSTGRES_HOST_ENV = "TOXIC_ANALYZER_POSTGRES_HOST"
POSTGRES_PORT_ENV = "TOXIC_ANALYZER_POSTGRES_PORT"
POSTGRES_DB_ENV = "TOXIC_ANALYZER_POSTGRES_DB"
POSTGRES_USER_ENV = "TOXIC_ANALYZER_POSTGRES_USER"
POSTGRES_PASSWORD_ENV = "TOXIC_ANALYZER_POSTGRES_PASSWORD"
POSTGRES_SSLMODE_ENV = "TOXIC_ANALYZER_POSTGRES_SSLMODE"
POSTGRES_SCHEMA_ENV = "TOXIC_ANALYZER_POSTGRES_SCHEMA"

POSTGRES_CONNECTION_ENV_VARS = (
    POSTGRES_DSN_ENV,
    POSTGRES_HOST_ENV,
    POSTGRES_PORT_ENV,
    POSTGRES_DB_ENV,
    POSTGRES_USER_ENV,
    POSTGRES_PASSWORD_ENV,
    POSTGRES_SSLMODE_ENV,
    POSTGRES_SCHEMA_ENV,
)

POSTGRES_MIGRATION_FILES = (
    ROOT_DIR / "sql" / "postgres" / "001_create_training_store.sql",
    ROOT_DIR / "sql" / "postgres" / "002_create_training_dataset_view.sql",
)

SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ConnectionFactory = Callable[[str], Any]


@dataclass(slots=True, frozen=True)
class PostgresSettings:
    dsn: str
    schema: str = DEFAULT_POSTGRES_SCHEMA

    def __post_init__(self) -> None:
        validate_postgres_identifier(self.schema)

    def redacted_dsn(self) -> str:
        return redact_postgres_dsn(self.dsn)


@dataclass(slots=True, frozen=True)
class CanonicalTrainingImportRow:
    source: str
    source_record_id: str
    raw_text: str
    normalized_text: str
    text_length: int
    label: int
    source_comment_id: str | None = None
    source_labels: str | None = None
    origin_system: str = "mixed_sqlite"
    label_status: str = "labeled"

    def to_db_params(self) -> tuple[object, ...]:
        return (
            self.source,
            self.source_record_id,
            self.source_comment_id,
            self.raw_text,
            self.normalized_text,
            self.text_length,
            self.label,
            self.label_status,
            self.source_labels,
            self.origin_system,
        )


def _close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


def validate_postgres_identifier(value: str) -> str:
    if not SQL_IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(
            "PostgreSQL schema names must match "
            f"{SQL_IDENTIFIER_PATTERN.pattern!r}. Got {value!r}."
        )
    return value


def build_postgres_dsn_from_parts(
    *,
    host: str,
    database: str,
    user: str,
    password: str | None = None,
    port: str | None = None,
    sslmode: str | None = None,
) -> str:
    quoted_user = quote(user, safe="")
    quoted_password = quote(password, safe="") if password else ""
    auth = quoted_user if not quoted_password else f"{quoted_user}:{quoted_password}"
    host_part = host if not port else f"{host}:{port}"
    query = f"?sslmode={quote(sslmode, safe='')}" if sslmode else ""
    return f"postgresql://{auth}@{host_part}/{quote(database, safe='')}{query}"


def redact_postgres_dsn(dsn: str) -> str:
    if "://" not in dsn:
        return re.sub(r"(password=)(\S+)", r"\1***", dsn)

    parts = urlsplit(dsn)
    if not parts.netloc:
        return dsn

    auth = ""
    if parts.username:
        auth = quote(parts.username, safe="")
        if parts.password is not None:
            auth = f"{auth}:***"
        auth = f"{auth}@"
    host_part = parts.hostname or ""
    if parts.port is not None:
        host_part = f"{host_part}:{parts.port}"
    netloc = f"{auth}{host_part}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def default_postgres_connection_factory(dsn: str) -> Any:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL support requires `psycopg`. Install model dependencies with "
            "`python -m pip install -e .[dev]` inside `model/`."
        ) from exc
    return psycopg.connect(dsn)


def resolve_postgres_settings(
    *,
    dsn: str | None = None,
    schema: str | None = None,
    environ: dict[str, str] | None = None,
    require: bool = False,
) -> PostgresSettings | None:
    env = environ or dict(os.environ)
    resolved_schema = schema or env.get(POSTGRES_SCHEMA_ENV) or DEFAULT_POSTGRES_SCHEMA
    validate_postgres_identifier(resolved_schema)

    explicit_dsn = dsn or env.get(POSTGRES_DSN_ENV)
    if explicit_dsn:
        return PostgresSettings(dsn=explicit_dsn, schema=resolved_schema)

    component_values = {
        "host": env.get(POSTGRES_HOST_ENV),
        "port": env.get(POSTGRES_PORT_ENV),
        "database": env.get(POSTGRES_DB_ENV),
        "user": env.get(POSTGRES_USER_ENV),
        "password": env.get(POSTGRES_PASSWORD_ENV),
        "sslmode": env.get(POSTGRES_SSLMODE_ENV),
    }
    if any(component_values.values()):
        missing = [name for name in ("host", "database", "user") if not component_values.get(name)]
        if missing:
            raise ValueError(
                "Incomplete PostgreSQL configuration. Either provide a full "
                f"`{POSTGRES_DSN_ENV}` value or set "
                f"`{POSTGRES_HOST_ENV}`, `{POSTGRES_DB_ENV}`, and `{POSTGRES_USER_ENV}`. "
                f"Missing: {', '.join(missing)}."
            )
        return PostgresSettings(
            dsn=build_postgres_dsn_from_parts(
                host=str(component_values["host"]),
                database=str(component_values["database"]),
                user=str(component_values["user"]),
                password=component_values["password"],
                port=component_values["port"],
                sslmode=component_values["sslmode"],
            ),
            schema=resolved_schema,
        )

    if require:
        raise ValueError(
            "PostgreSQL configuration is required. Provide `--postgres-dsn` or set "
            f"`{POSTGRES_DSN_ENV}`. Component-based configuration is also supported via "
            f"`{POSTGRES_HOST_ENV}`, `{POSTGRES_DB_ENV}`, `{POSTGRES_USER_ENV}`, and "
            f"`{POSTGRES_SCHEMA_ENV}`."
        )
    return None


def get_postgres_migration_paths() -> tuple[Path, ...]:
    return POSTGRES_MIGRATION_FILES


def render_postgres_migration(path: Path, *, schema: str) -> str:
    validate_postgres_identifier(schema)
    return path.read_text(encoding="utf-8").replace("{{SCHEMA}}", schema)


def apply_postgres_migrations(
    settings: PostgresSettings,
    *,
    connection_factory: ConnectionFactory | None = None,
) -> list[str]:
    factory = connection_factory or default_postgres_connection_factory
    connection = factory(settings.dsn)
    try:
        cursor = connection.cursor()
        try:
            for migration_path in get_postgres_migration_paths():
                cursor.execute(render_postgres_migration(migration_path, schema=settings.schema))
        finally:
            _close_quietly(cursor)
        connection.commit()
    finally:
        _close_quietly(connection)
    return [str(path) for path in get_postgres_migration_paths()]


def fetch_training_dataset_overview(
    settings: PostgresSettings,
    *,
    connection_factory: ConnectionFactory | None = None,
) -> dict[str, Any]:
    factory = connection_factory or default_postgres_connection_factory
    query = (
        f"SELECT record_origin, COUNT(*) "
        f"FROM {settings.schema}.{TRAINING_DATASET_VIEW_NAME} "
        f"GROUP BY record_origin "
        f"ORDER BY record_origin"
    )
    connection = factory(settings.dsn)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(query)
            origin_counts = {str(origin): int(count) for origin, count in cursor.fetchall()}
        finally:
            _close_quietly(cursor)
    finally:
        _close_quietly(connection)
    return {
        "rows": sum(origin_counts.values()),
        "origin_counts": dict(sorted(origin_counts.items())),
    }


def chunked(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    if size <= 0:
        raise ValueError(f"batch size must be positive. Got {size!r}.")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def upsert_canonical_training_rows(
    settings: PostgresSettings,
    rows: Sequence[CanonicalTrainingImportRow],
    *,
    batch_size: int = 1000,
    connection_factory: ConnectionFactory | None = None,
) -> int:
    if not rows:
        return 0

    factory = connection_factory or default_postgres_connection_factory
    query = f"""
        INSERT INTO {settings.schema}.canonical_training_texts (
            source,
            source_record_id,
            source_comment_id,
            raw_text,
            normalized_text,
            text_length,
            label,
            label_status,
            source_labels,
            origin_system
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (origin_system, source, source_record_id)
        DO UPDATE SET
            source_comment_id = EXCLUDED.source_comment_id,
            raw_text = EXCLUDED.raw_text,
            normalized_text = EXCLUDED.normalized_text,
            text_length = EXCLUDED.text_length,
            label = EXCLUDED.label,
            label_status = EXCLUDED.label_status,
            source_labels = EXCLUDED.source_labels,
            updated_at = NOW()
    """
    connection = factory(settings.dsn)
    try:
        cursor = connection.cursor()
        try:
            for batch in chunked(list(rows), batch_size):
                cursor.executemany(query, [row.to_db_params() for row in batch])
        finally:
            _close_quietly(cursor)
        connection.commit()
    finally:
        _close_quietly(connection)
    return len(rows)


def fetch_canonical_import_summary(
    settings: PostgresSettings,
    *,
    origin_system: str,
    connection_factory: ConnectionFactory | None = None,
) -> dict[str, Any]:
    factory = connection_factory or default_postgres_connection_factory
    base_table = f"{settings.schema}.canonical_training_texts"
    connection = factory(settings.dsn)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM {base_table} WHERE origin_system = %s",
                (origin_system,),
            )
            total_rows = int(cursor.fetchone()[0])

            cursor.execute(
                f"""
                SELECT source, COUNT(*)
                FROM {base_table}
                WHERE origin_system = %s
                GROUP BY source
                ORDER BY source
                """,
                (origin_system,),
            )
            source_counts = {str(source): int(count) for source, count in cursor.fetchall()}

            cursor.execute(
                f"""
                SELECT label_status, COUNT(*)
                FROM {base_table}
                WHERE origin_system = %s
                GROUP BY label_status
                ORDER BY label_status
                """,
                (origin_system,),
            )
            status_counts = {str(status): int(count) for status, count in cursor.fetchall()}

            cursor.execute(
                f"""
                SELECT label, COUNT(*)
                FROM {base_table}
                WHERE origin_system = %s
                GROUP BY label
                ORDER BY label
                """,
                (origin_system,),
            )
            label_counts = {str(label): int(count) for label, count in cursor.fetchall()}

            cursor.execute(
                f"""
                SELECT source, label_status, COUNT(*)
                FROM {base_table}
                WHERE origin_system = %s
                GROUP BY source, label_status
                ORDER BY source, label_status
                """,
                (origin_system,),
            )
            source_status_counts = {
                f"{source}:{status}": int(count) for source, status, count in cursor.fetchall()
            }
        finally:
            _close_quietly(cursor)
    finally:
        _close_quietly(connection)
    return {
        "rows": total_rows,
        "source_counts": dict(sorted(source_counts.items())),
        "label_status_counts": dict(sorted(status_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "source_status_counts": dict(sorted(source_status_counts.items())),
    }
