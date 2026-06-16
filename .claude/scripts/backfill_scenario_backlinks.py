#!/usr/bin/env python3
"""Layer C1 — file→scenario backlinks.

Walk knowledge/scenarios/*.md, parse each scenario's "File checklist"
markdown table, collect every (scenario_slug, file_path) pair, and
append an idempotent "## Appears in scenarios" section to the
matching per-file doc under knowledge/files/.

Idempotent: re-running replaces the existing block, not appends.

Usage: python3 .claude/scripts/backfill_scenario_backlinks.py [--dry-run]
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO / "knowledge" / "scenarios"
FILES_DIR = REPO / "knowledge" / "files"

# Sentinel comment lets us re-run idempotently.
SECTION_HEADER = "## Appears in scenarios"
SENTINEL_BEGIN = "<!-- scenarios:auto:begin -->"
SENTINEL_END = "<!-- scenarios:auto:end -->"

# Regex to find a backticked file path in the second column of a
# markdown table row. Scenario checklist rows look like:
#   | 1 | `src/include/catalog/pg_type.dat` | … | [link] | catalog-conventions |
TABLE_ROW_RE = re.compile(
    r"^\s*\|\s*(?:\d+|—|-)\s*\|\s*`([^`]+)`\s*\|", re.MULTILINE
)


def parse_scenario(path: Path):
    """Return (slug, title, [file_paths]) for one scenario file."""
    text = path.read_text(encoding="utf-8")
    slug = path.stem
    # Title = first H1
    m = re.search(r"^# (.+?)$", text, re.MULTILINE)
    title = m.group(1).strip() if m else slug

    # Find the file checklist section
    cl = re.search(
        r"^## File checklist.*?(?=^## )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not cl:
        return slug, title, []

    rows = TABLE_ROW_RE.findall(cl.group(0))
    files = []
    for path_str in rows:
        # Strip a leading or trailing "(NEW)" / parenthetical
        path_str = path_str.strip()
        # Some entries may have "*" wildcards — keep them as-is for
        # the backlink; we'll only emit backlinks where a per-file
        # doc actually exists.
        files.append(path_str)
    return slug, title, files


def per_file_doc(path_str: str) -> Path | None:
    """Map a scenario-cited source path to its per-file doc, if it exists.

    Conventions: knowledge/files/<source-path>.md. Wildcards return None.

    Fallback heuristics (catalog .dat → companion .h, etc.):
    - If `pg_foo.dat`, try `pg_foo.h.md`. The catalog .h files document
      both the schema (.h) and the seed data (.dat).
    - If a wildcard token like `<name>` or `<typname>` appears, treat as
      a new file (no per-file doc); return None.
    """
    if "<" in path_str or "*" in path_str or "?" in path_str:
        return None
    if path_str.endswith("/"):
        return None

    candidate = FILES_DIR / (path_str + ".md")
    if candidate.exists():
        return candidate

    # .dat → .h fallback for catalog files
    if path_str.endswith(".dat"):
        h_candidate = FILES_DIR / (path_str[:-4] + ".h.md")
        if h_candidate.exists():
            return h_candidate

    # parenthetical / qualifier inside the path (e.g. "src/.../foo.c (NEW)")
    cleaned = re.split(r"\s+\(", path_str)[0].strip()
    if cleaned != path_str:
        candidate = FILES_DIR / (cleaned + ".md")
        if candidate.exists():
            return candidate
        if cleaned.endswith(".dat"):
            h_candidate = FILES_DIR / (cleaned[:-4] + ".h.md")
            if h_candidate.exists():
                return h_candidate

    return None


def render_block(entries):
    """Render the auto-block from a list of (slug, title) pairs."""
    lines = [SENTINEL_BEGIN, ""]
    for slug, title in sorted(entries, key=lambda x: x[0]):
        # The link is relative from a knowledge/files/.../X.md back up to
        # knowledge/scenarios/<slug>.md. Number of `..` depends on depth.
        lines.append(f"- [{title}](scenarios:{slug})  <!-- {slug} -->")
    lines += ["", SENTINEL_END]
    return "\n".join(lines)


def relative_link(file_doc: Path, slug: str) -> str:
    """Build a markdown link from file_doc back to scenarios/<slug>.md."""
    target = SCENARIOS_DIR / f"{slug}.md"
    try:
        rel = Path(__import__("os").path.relpath(target, file_doc.parent))
    except ValueError:
        rel = Path(str(target))
    return str(rel)


def upsert_section(file_doc: Path, entries, dry_run: bool):
    """Append or replace the auto-section in `file_doc`."""
    text = file_doc.read_text(encoding="utf-8")

    # Build the auto-block content (real links).
    body_lines = [SENTINEL_BEGIN, ""]
    for slug, title in sorted(entries, key=lambda x: x[0]):
        link = relative_link(file_doc, slug)
        body_lines.append(f"- [{title}]({link})")
    body_lines += ["", SENTINEL_END]
    body = "\n".join(body_lines)

    new_section = f"\n## {SECTION_HEADER[3:]}\n\n{body}\n"

    # If the section already exists (sentinels present), replace just
    # the block between sentinels. Otherwise append at EOF.
    sentinel_re = re.compile(
        re.escape(SENTINEL_BEGIN) + r".*?" + re.escape(SENTINEL_END),
        re.DOTALL,
    )
    if SENTINEL_BEGIN in text:
        new_text = sentinel_re.sub(body, text)
    elif SECTION_HEADER in text:
        # Header exists but no sentinels — replace from header to next H2
        # (or EOF).
        pat = re.compile(
            r"^" + re.escape(SECTION_HEADER) + r"\n.*?(?=^## |\Z)",
            re.MULTILINE | re.DOTALL,
        )
        new_text = pat.sub(f"{SECTION_HEADER}\n\n{body}\n", text, count=1)
    else:
        # Append at end, ensuring exactly one trailing newline before it.
        sep = "" if text.endswith("\n") else "\n"
        new_text = text + sep + new_section

    if new_text == text:
        return False
    if not dry_run:
        file_doc.write_text(new_text, encoding="utf-8")
    return True


def main(argv):
    dry_run = "--dry-run" in argv

    # Pass 1: collect (slug, title, [file_paths]) per scenario, skip
    # _README/_template/_index.
    scenarios = []
    for p in sorted(SCENARIOS_DIR.glob("*.md")):
        if p.name.startswith("_") or p.name == "README.md":
            continue
        scenarios.append(parse_scenario(p))

    # Pass 2: invert — for each unique file path, accumulate scenarios.
    backlinks = {}  # file_doc_path -> [(slug, title)]
    missing = []   # (slug, file_path) when no per-file doc exists
    for slug, title, files in scenarios:
        for fp in files:
            doc = per_file_doc(fp)
            if doc is None:
                missing.append((slug, fp))
                continue
            backlinks.setdefault(doc, []).append((slug, title))

    # Pass 3: upsert.
    updated = 0
    for doc, entries in sorted(backlinks.items()):
        if upsert_section(doc, entries, dry_run):
            updated += 1

    print(f"scenarios:    {len(scenarios)}")
    print(f"backlinks:    {sum(len(v) for v in backlinks.values())} edges")
    print(f"per-file docs updated: {updated}")
    if missing:
        print(f"\nfile_paths without a per-file doc: {len(missing)} "
              "(NEW files or wildcards — expected; logged below)")
        for slug, fp in missing[:30]:
            print(f"  {slug}: {fp}")
        if len(missing) > 30:
            print(f"  ... and {len(missing) - 30} more")


if __name__ == "__main__":
    main(sys.argv[1:])
