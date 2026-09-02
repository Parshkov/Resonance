"""Operational commands for R11 persistence.

Examples:
  python -m src.persistence --db var/resonance-pilot.sqlite health
  python -m src.persistence --db var/resonance-pilot.sqlite seed-r7
  python -m src.persistence --db var/resonance-pilot.sqlite seed-pilot --count 100
  python -m src.persistence --db var/resonance-pilot.sqlite export --out var/backup.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .factory import open_repository
from .seed import seed_pilot_scale, seed_r7
from .service import LiveCorpusService


def _health_payload(service: LiveCorpusService) -> dict:
    health = service.health()
    return {
        "ok": health.ok,
        "backend": health.backend,
        "schema_version": health.schema_version,
        "users": health.users,
        "sessions": health.sessions,
        "discoverable": health.discoverable,
        "engine_snapshot": health.engine_snapshot,
        "db_generation": health.db_generation,
        "serving_generation": health.serving_generation,
        "index_current": health.index_current,
        "details": dict(health.details),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resonance-persist")
    parser.add_argument("--db", default=None, help="SQLite path or postgres:// DSN")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sub.add_parser("health")
    sub.add_parser("reset")
    sub.add_parser("seed-r7")
    pilot = sub.add_parser("seed-pilot")
    pilot.add_argument("--count", type=int, default=100)
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

        service = LiveCorpusService(repo)
        if args.cmd == "health":
            payload = _health_payload(service)
            print(json.dumps(payload, sort_keys=True, indent=2))
            return 0 if payload["ok"] else 1
        if args.cmd == "reset":
            service.reset()
            print(json.dumps({"reset": True, **_health_payload(service)}, sort_keys=True))
            return 0
        if args.cmd == "seed-r7":
            n = seed_r7(service)
            print(json.dumps({"seeded": n, **_health_payload(service)}, sort_keys=True))
            return 0
        if args.cmd == "seed-pilot":
            if args.count < 1:
                parser.error("--count must be >= 1")
            n = seed_pilot_scale(service, n=args.count)
            print(json.dumps({"seeded": n, **_health_payload(service)}, sort_keys=True))
            return 0
        if args.cmd == "export":
            service.export_backup(args.out)
            print(json.dumps({"exported": args.out, **_health_payload(service)}, sort_keys=True))
            return 0
        if args.cmd == "import-backup":
            service.import_backup(Path(args.path))
            print(json.dumps({"imported": args.path, **_health_payload(service)}, sort_keys=True))
            return 0
        return 2
    finally:
        repo.close()


if __name__ == "__main__":
    sys.exit(main())
