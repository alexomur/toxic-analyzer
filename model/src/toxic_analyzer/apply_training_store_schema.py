"""Apply PostgreSQL schema files for the model training store."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from toxic_analyzer.postgres_store import apply_postgres_migrations, resolve_postgres_settings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-dsn")
    parser.add_argument("--postgres-schema")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = resolve_postgres_settings(
        dsn=args.postgres_dsn,
        schema=args.postgres_schema,
        require=True,
    )
    applied_files = apply_postgres_migrations(settings)
    print(
        "[apply-training-store-schema] Done: "
        f"schema={settings.schema} files={len(applied_files)}",
        flush=True,
    )
    print(f"[apply-training-store-schema] Target: {settings.redacted_dsn()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
