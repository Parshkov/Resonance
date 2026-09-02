"""Operational commands for R11 persistence.

python -m src.persistence.cli migrate
python -m src.persistence.cli health
python -m src.persistence.cli seed-r7
python -m src.persistence.cli reset
python -m src.persistence.cli export --out backup.json
python -m src.persistence.cli import-backup backup.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .factory import open_repository
from .seed import seed_r7
from .service import LiveCorpusService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resonance-persist")
    parser.add_argument("--db", default=None, help="SQLite path or postgres:// DSN")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("health")
    sub.add_parser("reset")
    sub.add_parser("seed-r7")
    exp = sub.add_parser("export")
    exp.add_argument("--out", required=True)
    imp = sub.add_parser("import-backup")
    imp.add_argument("path")
    args = parser.parse_args(argv)

    repo = open_repository(args.db)
    try:
        if args.cmd == "migrate":
            applied = repo.migrate()
            print(json.dumps({"applied": list(applied), **repo.health()}, sort_keys=True))
            return 0
        if args.cmd == "health":
            service = LiveCorpusService(repo)
            health = service.health()
            print(json.dumps({
                "ok": health.ok,
                "backend": health.backend,
                "schema_version": health.schema_version,
                "users": health.users,
                "sessions": health.sessions,
                "discoverable": health.discoverable,
                "engine_snapshot": health.engine_snapshot,
                "details": dict(health.details),
            }, sort_keys=True, indent=2))
            return 0 if health.ok else 1
        if args.cmd == "reset":
            LiveCorpusService(repo).reset()
            print(json.dumps({"reset": True, **repo.health()}, sort_keys=True))
            return 0
        if args.cmd == "seed-r7":
            service = LiveCorpusService(repo)
            n = seed_r7(service)
            print(json.dumps({"seeded": n, **service.health().details}, sort_keys=True))
            return 0
        if args.cmd == "export":
            service = LiveCorpusService(repo)
            service.export_backup(args.out)
            print(json.dumps({"exported": args.out}, sort_keys=True))
            return 0
        if args.cmd == "import-backup":
            service = LiveCorpusService(repo)
            service.import_backup(Path(args.path))
            print(json.dumps({"imported": args.path, **service.health().details}, sort_keys=True))
            return 0
        return 2
    finally:
        repo.close()


if __name__ == "__main__":
    sys.exit(main())
