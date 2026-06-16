#!/usr/bin/env python3
"""Layer C3 — file→issue-register backlinks.

For every per-file doc that contains an [ISSUE-*] tag, add a link
to its matching knowledge/issues/<subsystem>.md register in the
"Cross-references" / "Cross-refs" section. Idempotent.

Mapping heuristics (per-file doc path → issue register filename):

  src/backend/<area>/<sub>/<f>.md   → <area>-<sub>.md OR <area>.md OR <sub>.md
  src/backend/<area>/<f>.md         → <area>.md
  src/include/<area>/<f>.md         → include-<area>.md OR <area>.md
  src/bin/<area>/<f>.md             → <area>.md
  src/interfaces/<area>/<f>.md      → <area>.md
  contrib/<area>/<f>.md             → <area>.md
  src/test/modules/<f>              → test-modules.md
  src/port/<f>                      → port.md
  src/timezone/<f>                  → timezone.md
  src/fe_utils/<f>                  → fe_utils.md
  src/pl/<area>/<f>                 → <area>.md

We try each candidate, picking the first that exists.
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FILES_DIR = REPO / "knowledge" / "files"
ISSUES_DIR = REPO / "knowledge" / "issues"

SENTINEL_BEGIN = "<!-- issues:auto:begin -->"
SENTINEL_END = "<!-- issues:auto:end -->"
ISSUE_TAG = re.compile(r"\[ISSUE-[a-z-]+:")


def candidates_for(rel_path: Path) -> list[str]:
    """Yield issue-register filenames to try, in priority order.

    rel_path is the per-file doc path relative to FILES_DIR, e.g.
    `src/backend/utils/adt/varbit.c.md` or `contrib/pgcrypto/sha1.c.md`.
    """
    parts = rel_path.parts
    out: list[str] = []

    if len(parts) >= 4 and parts[0] == "src" and parts[1] == "backend":
        area = parts[2]
        sub = parts[3] if len(parts) >= 5 else None
        if sub:
            out.append(f"{area}-{sub}.md")
            out.append(f"{sub}.md")
        out.append(f"{area}.md")
    elif len(parts) >= 4 and parts[0] == "src" and parts[1] == "include":
        # src/include/<area>/<f>.md — area is the subdir
        area = parts[2]
        out.append(f"include-{area}.md")
        out.append(f"{area}.md")
    elif len(parts) == 3 and parts[0] == "src" and parts[1] == "include":
        # src/include/<f>.md — top-level header; no subdir → include-misc
        out.append("include-misc.md")
    elif len(parts) >= 3 and parts[0] == "src" and parts[1] in ("bin", "interfaces"):
        area = parts[2]
        out.append(f"{area}.md")
        # Smaller src/bin utilities fold into bin-singletons.md
        if parts[1] == "bin":
            out.append("bin-singletons.md")
    elif len(parts) >= 2 and parts[0] == "contrib":
        area = parts[1]
        out.append(f"{area}.md")
    elif len(parts) >= 4 and parts[0] == "src" and parts[1] == "test" and parts[2] == "modules":
        out.append("test-modules.md")
    elif len(parts) >= 2 and parts[0] == "src" and parts[1] in ("port", "timezone", "fe_utils"):
        out.append(f"{parts[1]}.md")
    elif len(parts) >= 3 and parts[0] == "src" and parts[1] == "pl":
        # pl/tcl → pltcl.md (the language name)
        out.append(f"pl{parts[2]}.md")
        out.append(f"{parts[2]}.md")

    # Generic backstop: filename stem (handles a few edge cases)
    if len(parts) >= 2:
        stem = parts[-2] if parts[-1].endswith(".md") else parts[-1]
        out.append(f"{stem}.md")

    # Final fallback for any src/include/... path: include-misc.md
    if len(parts) >= 2 and parts[0] == "src" and parts[1] == "include":
        out.append("include-misc.md")

    return out


def resolve_register(rel_path: Path) -> Path | None:
    for cand in candidates_for(rel_path):
        # Try as-is then with `_` rewritten to `-` (storage-large-object.md
        # vs storage/large_object/ underscore mismatch).
        for variant in (cand, cand.replace("_", "-")):
            candidate = ISSUES_DIR / variant
            if candidate.exists():
                return candidate
    return None


def upsert_block(file_doc: Path, register: Path, dry_run: bool) -> bool:
    text = file_doc.read_text(encoding="utf-8")
    rel = Path(__import__("os").path.relpath(register, file_doc.parent))
    link_line = f"- [Issue register — `{register.stem}`]({rel})"
    block = f"{SENTINEL_BEGIN}\n{link_line}\n{SENTINEL_END}"

    if SENTINEL_BEGIN in text:
        new_text = re.sub(
            re.escape(SENTINEL_BEGIN) + r".*?" + re.escape(SENTINEL_END),
            block,
            text,
            flags=re.DOTALL,
        )
    else:
        # Find Cross-references / Cross-refs section
        section_re = re.compile(
            r"^## (Cross-references|Cross-refs)\s*\n",
            re.MULTILINE,
        )
        m = section_re.search(text)
        if m:
            # Insert at end of section: find next "## " or EOF
            section_start = m.end()
            next_section = re.search(r"^## ", text[section_start:], re.MULTILINE)
            if next_section:
                insert_at = section_start + next_section.start()
                new_text = (
                    text[:insert_at].rstrip() + "\n\n" + block + "\n\n" + text[insert_at:]
                )
            else:
                new_text = text.rstrip() + "\n\n" + block + "\n"
        else:
            new_text = text.rstrip() + "\n\n## Cross-references\n\n" + block + "\n"

    if new_text == text:
        return False
    if not dry_run:
        file_doc.write_text(new_text, encoding="utf-8")
    return True


def main(argv):
    dry_run = "--dry-run" in argv

    matches = 0
    updated = 0
    unresolved = []
    for p in FILES_DIR.rglob("*.md"):
        text = p.read_text(encoding="utf-8")
        if not ISSUE_TAG.search(text):
            continue
        rel = p.relative_to(FILES_DIR)
        matches += 1
        register = resolve_register(rel)
        if register is None:
            unresolved.append(rel)
            continue
        if upsert_block(p, register, dry_run):
            updated += 1

    print(f"per-file docs with [ISSUE-*] tags: {matches}")
    print(f"updated:                           {updated}")
    print(f"unresolved (no issue register):    {len(unresolved)}")
    if unresolved:
        for r in unresolved[:15]:
            print(f"  {r} (tried: {candidates_for(r)[:3]})")
        if len(unresolved) > 15:
            print(f"  ... and {len(unresolved) - 15} more")


if __name__ == "__main__":
    main(sys.argv[1:])
