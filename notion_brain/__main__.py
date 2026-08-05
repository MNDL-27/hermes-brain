"""CLI: ``python -m notion_brain reset``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import bootstrap
from . import schema as S


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notion_brain")
    parser.add_argument("--home", default=os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))
    sub = parser.add_subparsers(dest="cmd", required=True)

    rs = sub.add_parser("reset", help="Archive and recreate DBs whose schema no longer matches.")
    rs.add_argument("--only", help="Comma-separated DB keys to reset (default: all)")
    rs.add_argument("--dry-run", action="store_true", help="Show what would be reset without touching Notion")
    rs.add_argument("--force", action="store_true", help="Reset every cached DB, not just mismatched ones")

    url = sub.add_parser("url", help="Print the Notion URL of the Hermes Brain parent page.")
    url.add_argument("--all", action="store_true", help="Also print URLs for every cached database.")

    sub.add_parser("health", help="Summarize each DB: schema match, entry count, last entry.")

    args = parser.parse_args(argv)

    if not bootstrap.store.get_api_key():
        print("error: NOTION_API_KEY is not set", file=sys.stderr)
        return 2

    if args.cmd == "reset":
        only = {x.strip() for x in args.only.split(",")} if args.only else None
        unknown = only - set(S.DATABASES) if only else set()
        if unknown:
            print(f"error: unknown DB key(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        target = only or set(S.DATABASES)
        reset = bootstrap.reset_databases(
            args.home, only=target, dry_run=args.dry_run, force=args.force,
        )
        verb = "would reset" if args.dry_run else "reset"
        print(f"{verb} {len(reset)} DB(s): {', '.join(reset) or '(none)'}")
        return 0

    if args.cmd == "url":
        output = bootstrap.get_url(args.home, db=getattr(args, "all", False))
        if output:
            print(output)
        else:
            print("error: no URLs available (run `python -m notion_brain` to bootstrap first)", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "health":
        mismatched = []
        for key in S.DATABASES:
            db_id = bootstrap._load_cache(Path(args.home) / S.CACHE_FILE).get(f"db_{key}")
            if not db_id:
                continue
            try:
                if not bootstrap._database_schema_matches(bootstrap.store.get_database(db_id), bootstrap._PROPS[key]):
                    mismatched.append(key)
            except Exception:
                pass
        print(bootstrap.health_report(args.home))
        if mismatched:
            print(f"\nAuto-repairing {len(mismatched)} mismatched DB(s): {', '.join(mismatched)}")
            fixed = bootstrap.reset_databases(args.home, only=set(mismatched))
            print(f"Reset completed: {', '.join(fixed)}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
