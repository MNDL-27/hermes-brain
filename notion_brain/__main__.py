"""CLI: ``python -m notion_brain reset|url|health|import``."""

from __future__ import annotations

import argparse
import os
import re
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

    wp = sub.add_parser("wipe", help="Wipe noisy rows from Entities, Tasks, Projects (or specified DBs).")
    wp.add_argument("--dbs", help="Comma-separated DB keys to wipe (default: entities,tasks,projects)")
    wp.add_argument("--dry-run", action="store_true", help="Show what would be wiped without modifying Notion")

    im = sub.add_parser("import", help="Import local memory files (MEMORY.md/USER.md/CLAUDE.md) into Notion.")
    im.add_argument("--files", help="Comma-separated markdown files to import (default: auto-discover)")
    im.add_argument("--dry-run", action="store_true", help="Show what would be imported without writing to Notion")

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
        print(bootstrap.health_report(args.home))
        return 0

    if args.cmd == "wipe":
        dbs = {x.strip() for x in args.dbs.split(",")} if getattr(args, "dbs", None) else {"entities", "tasks", "projects"}
        deleted = bootstrap.wipe_database_rows(args.home, databases=dbs, dry_run=args.dry_run)
        verb = "Would wipe" if args.dry_run else "Wiped"
        total = sum(deleted.values())
        print(f"{verb} {total} row(s) across: {', '.join(f'{k} ({v})' for k, v in deleted.items())}")
        return 0

    if args.cmd == "import":
        return _cmd_import(args)

    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# import subcommand
# ---------------------------------------------------------------------------

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
        Path(home) / "MEMORY.md",
        Path(home) / "USER.md",
        Path.home() / ".claude" / "CLAUDE.md",
        Path.cwd() / "MEMORY.md",
    ]
    return [p for p in candidates if p.is_file() and p.stat().st_size > 0]


def _parse_markdown(content: str) -> list[dict]:
    """Parse markdown into entries: one per bullet under a recognized heading.

    Falls back to one entry per paragraph when no bullets exist.
    Uses ``extract.classify_text`` for kind/tags heuristics.
    """
    from . import extract

    entries: list[dict] = []
    domain = "memory"
    current_title = ""
    current_body = ""

    def flush() -> None:
        nonlocal current_title, current_body
        if current_title and current_body:
            entries.append({
                "domain": domain,
                "title": current_title,
                "content": current_body,
            })
        current_title = ""
        current_body = ""

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and set(stripped) & set(" ") or (stripped.startswith("## ")):
            heading = stripped.lstrip("#").strip().lower()
            flush()
            domain = _HEADING_DOMAIN.get(heading, "memory")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            flush()
            text = stripped[2:].strip()
            # **Bold label**: body → label becomes title
            m = re.match(r"\*\*([^*]+)\*\*:?\s*(.*)", text)
            if m and m.group(2).strip():
                current_title, current_body = m.group(1).strip(), m.group(2).strip()
            else:
                words = text.split()
                current_title = " ".join(words[:8])[:120]
                current_body = text
        elif current_body and stripped:
            current_body += " " + stripped
        elif not current_title and stripped and not stripped.startswith("#"):
            # paragraph fallback (no bullets) — collect
            current_title = " ".join(stripped.split()[:8])[:120]
            current_body = stripped

    flush()
    return entries


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
    total = 0
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
            print(f"  error importing '{e['title'][:40]}': {S.redact_secrets(str(exc))}", file=sys.stderr)
    print(f"\nImported {saved} entries ({errors} errors).")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
