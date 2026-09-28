"""CLI: ``python -m notion_brain reset|url|health|import``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import bootstrap
from . import schema as S


def _self_heal(home: str) -> None:
    """Re-validate cached DB IDs before read commands; rebind stale ones.

    Databases deleted in Notion (or cache pointing at a removed duplicate)
    would otherwise 404 with a raw API error. ensure_brain() already
    rebinds the cache to the live databases on the parent page — this
    just runs it first so users never see the dead-end error.
    """
    try:
        bootstrap.ensure_brain(home)
    except Exception:
        pass  # health/wipe will surface a readable report instead


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="notion_brain")
    parser.add_argument(
        "--home", default=os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    rs = sub.add_parser("reset", help="Archive and recreate DBs whose schema no longer matches.")
    rs.add_argument("--only", help="Comma-separated DB keys to reset (default: all)")
    rs.add_argument(
        "--dry-run", action="store_true", help="Show what would be reset without touching Notion"
    )
    rs.add_argument(
        "--force", action="store_true", help="Reset every cached DB, not just mismatched ones"
    )

    url = sub.add_parser("url", help="Print the Notion URL of the Hermes Brain parent page.")
    url.add_argument(
        "--all", action="store_true", help="Also print URLs for every cached database."
    )

    sub.add_parser("health", help="Summarize each DB: schema match, entry count, last entry.")

    wp = sub.add_parser(
        "wipe", help="Wipe noisy rows from Entities, Tasks, Projects (or specified DBs)."
    )
    wp.add_argument(
        "--dbs", help="Comma-separated DB keys to wipe (default: entities,tasks,projects)"
    )
    wp.add_argument(
        "--dry-run", action="store_true", help="Show what would be wiped without modifying Notion"
    )

    im = sub.add_parser(
        "import", help="Import local memory files (MEMORY.md/USER.md/CLAUDE.md) into Notion."
    )
    im.add_argument(
        "--files", help="Comma-separated markdown files to import (default: auto-discover)"
    )
    im.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without writing to Notion",
    )

    stp = sub.add_parser(
        "setup",
        help="Interactive or automated onboarding wizard to configure standard and custom databases.",
    )
    stp.add_argument(
        "--standard-dbs", help="Comma-separated list of standard DBs to create (default: all)"
    )
    stp.add_argument("--custom-json", help="JSON string or file path defining custom databases")
    stp.add_argument(
        "--non-interactive", action="store_true", help="Run without interactive prompts"
    )

    up = sub.add_parser(
        "update",
        help=(
            "Detect drift between installed and latest GitHub release "
            "(detect+instruct only; never mutates the install)."
        ),
    )
    up.add_argument(
        "--check",
        action="store_true",
        help="Only check for updates, never modify the install (default behavior)",
    )
    up.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (implies --check)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "update":
        return _cmd_update(
            check_only=getattr(args, "check", False),
            json_output=getattr(args, "json", False),
        )

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
            args.home,
            only=target,
            dry_run=args.dry_run,
            force=args.force,
        )
        verb = "would reset" if args.dry_run else "reset"
        print(f"{verb} {len(reset)} DB(s): {', '.join(reset) or '(none)'}")
        return 0

    if args.cmd == "url":
        output = bootstrap.get_url(args.home, db=getattr(args, "all", False))
        if output:
            print(output)
        else:
            print(
                "error: no URLs available (run `python -m notion_brain` to bootstrap first)",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.cmd == "health":
        _self_heal(args.home)
        report = bootstrap.health_report(args.home)
        print(report)
        # Exit 1 when anything failed — installers and scripts gate on this.
        return 1 if ("ERROR" in report or "MISSING" in report or "NOT SHARED" in report) else 0

    if args.cmd == "wipe":
        _self_heal(args.home)
        dbs = (
            {x.strip() for x in args.dbs.split(",")}
            if getattr(args, "dbs", None)
            else {"entities", "tasks", "projects"}
        )
        deleted = bootstrap.wipe_database_rows(args.home, databases=dbs, dry_run=args.dry_run)
        verb = "Would wipe" if args.dry_run else "Wiped"
        total = sum(deleted.values())
        print(
            f"{verb} {total} row(s) across: {', '.join(f'{k} ({v})' for k, v in deleted.items())}"
        )
        return 0

    if args.cmd == "import":
        return _cmd_import(args)

    if args.cmd == "setup":
        answers: dict[str, Any] = {}
        if getattr(args, "standard_dbs", None):
            answers["standard_dbs"] = [x.strip() for x in args.standard_dbs.split(",") if x.strip()]
        if getattr(args, "custom_json", None):
            raw_c = args.custom_json.strip()
            if os.path.isfile(raw_c):
                answers["custom_dbs"] = json.loads(Path(raw_c).read_text(encoding="utf-8"))
            else:
                answers["custom_dbs"] = json.loads(raw_c)
        elif getattr(args, "non_interactive", False):
            answers["custom_dbs"] = []

        res = bootstrap.interactive_setup(args.home, answers=answers or None)
        print(f"✓ Setup complete: parent page '{res['parent_page_id']}'")
        print(
            f"  Created {res.get('standard_count', 0)} standard DB(s) and {res.get('custom_count', 0)} custom DB(s)"
        )
        return 0

    parser.print_help()
    return 1


def _cmd_update(check_only: bool = False, json_output: bool = False) -> int:
    """Detect drift between installed and latest GitHub release (UPD-01..UPD-05).

    Detect+instruct only. Never runs `pip install`, `git pull`, or any other
    mutation. Exit codes: 0 = no drift, 2 = drift available. JSON mode
    serializes the structured payload to stdout.
    """
    from . import update as update_mod

    pkg_dir = _repo_dir()
    result = update_mod.check_for_update(repo_dir=pkg_dir)

    if json_output:
        print(update_mod.format_json(result))
    else:
        print(update_mod.format_human(result))
    return 2 if result.get("drift") else 0


def _repo_dir() -> Path:
    """Find the hermes-brain git repo directory."""
    pkg_dir = Path(__file__).resolve().parent.parent
    if (pkg_dir / ".git").is_dir():
        return pkg_dir
    default = Path.home() / ".hermes-brain"
    if (default / ".git").is_dir():
        return default
    return pkg_dir


# import subcommand

# Heading → domain mapping (headings we recognize; anything else stays "memory").
_HEADING_DOMAIN: dict[str, str] = {
    "memory": "memory",
    "memories": "memory",
    "tasks": "daily_work",
    "todos": "daily_work",
    "projects": "projects",
    "content": "social_content",
    "social": "social_content",
    "research": "research",
    "career": "career",
    "entities": "entities",
    "people": "entities",
    "preferences": "entities",
    "user": "entities",
}


def _discover_memory_files(home: str) -> list[Path]:
    """Find candidate memory markdown files in common locations."""
    candidates = [
        Path(home) / "memories" / "MEMORY.md",
        Path(home) / "memories" / "USER.md",
        Path(home) / "MEMORY.md",
        Path(home) / "USER.md",
        Path.home() / ".claude" / "CLAUDE.md",
        Path.cwd() / "MEMORY.md",
    ]
    seen = set()
    out = []
    for p in candidates:
        rp = p.resolve() if p.exists() else p
        if rp not in seen and p.is_file() and p.stat().st_size > 0:
            seen.add(rp)
            out.append(p)
    return out


def _parse_markdown(content: str) -> list[dict]:
    """Parse markdown into entries using the enhanced multi-format parser."""
    from . import helpers

    return helpers.parse_disk_memory_text(content)


def _classify(entry: dict) -> dict:
    """Attach kind/tags via the existing heuristic classifier."""
    from . import extract

    classification = extract.classify_text(entry["content"])
    entry["kind"] = classification.get("kind", "note")
    # extract.classify_text returns {domain,title,kind} — no tags. Ignore its
    # domain too: heading wins because file structure beats a one-liner guess.
    entry["tags"] = []
    return entry


def _cmd_import(args) -> int:
    from . import remember as remember_fn

    files = (
        [Path(x.strip()).expanduser() for x in args.files.split(",")]
        if args.files
        else _discover_memory_files(args.home)
    )
    files = [f for f in files if f.is_file()]
    if not files:
        print("No memory files found.")
        print("Looked for: MEMORY.md, USER.md (in HERMES_HOME), ~/.claude/CLAUDE.md, ./MEMORY.md")
        print("Pass --files to point at specific files.")
        return 1

    print(f"Found {len(files)} file(s):")
    plan: list[dict] = []
    for f in files:
        content = f.read_text(encoding="utf-8", errors="replace")
        fentries = _parse_markdown(content)
        print(f"  {f}: {len(fentries)} entries")
        for e in fentries:
            plan.append({**e, "_file": str(f)})

    if not plan:
        print("Nothing importable found (no bullets or paragraphs).")
        return 1

    if args.dry_run:
        print("\nDry run — would import:")
        for e in plan:
            print(f"  [{e['domain']}/{_classify(e).get('kind', 'note')}] {e['title'][:60]}")
        print(f"\n{len(plan)} entries total. Re-run without --dry-run to import.")
        return 0

    # ponytail: re-import relies on title-match PATCH for dedupe; no pre-flight
    # duplicate scan against Notion. Add explicit diff when brains get large.
    saved = 0
    errors = 0
    for e in plan:
        _classify(e)
        try:
            remember_fn(
                title=e["title"],
                content=e["content"],
                domain=e["domain"],
                kind=e["kind"],
                tags=e["tags"],
            )
            saved += 1
        except Exception as exc:
            errors += 1
            print(
                f"  error importing '{e['title'][:40]}': {S.redact_secrets(str(exc))}",
                file=sys.stderr,
            )
    print(f"\nImported {saved} entries ({errors} errors).")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
