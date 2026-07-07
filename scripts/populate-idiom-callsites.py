#!/usr/bin/env python3
"""Populate ``## Call sites`` sections in ``knowledge/idioms/*.md``.

Extraction strategy (evidence-preserving, no invention):

1. Parse each idiom into bullet items (``- ...``), joining continuation
   lines. This mirrors how the corpus already writes cites:

       - `source/foo.c:1234` — description continues here
         and here.

2. Also scan free-text paragraphs for inline ``source/path:LINE`` cites.
3. For each cite, keep the RICHEST description found; the whole bullet
   body wins over a bare inline mention.
4. Emit a ``## Call sites`` section with a compact table, sorted by
   file then line. Anchors without line numbers become "—" in the
   Line column (file-level anchors, still useful).
5. Insert before ``## Open questions`` / ``## Cross-references`` /
   ``## Unverified`` if present, else append. Re-runs replace the
   block between markers.

Idioms with zero cites are listed at the end as needing a manual pass
(the extractor only *structures* existing evidence; it does not
invent).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path(__file__).resolve().parent,
            text=True,
        )
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path(__file__).resolve().parent.parent


ROOT = _repo_root()
FILES_DOCS = ROOT / "knowledge" / "files"
# Default target layer; can be overridden via --layer on the CLI.
IDIOMS = ROOT / "knowledge" / "idioms"

CITE_WITH_LINE = re.compile(
    r"`?source/([A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+):(\d+)`?"
)
CITE_NO_LINE = re.compile(
    r"`source/([A-Za-z0-9_./+-]+?\.[A-Za-z0-9_+-]+)`"
)
TRAILING_TAG = re.compile(r"\s*\[[\w-]+\]\s*")
BULLET_START = re.compile(r"^(\s*)([-*])\s+(.*)$")

MARKER_OPEN = "<!-- callsites:auto -->"
MARKER_CLOSE = "<!-- /callsites:auto -->"

BLOCK_RE = re.compile(
    r"\n?## Call sites\s*\n"
    + re.escape(MARKER_OPEN)
    + r".*?"
    + re.escape(MARKER_CLOSE)
    + r"\n?",
    re.DOTALL,
)

INSERT_BEFORE = re.compile(
    r"\n(## (Open questions|Unverified|Cross-references|Related idioms|See also)\b[^\n]*)"
)


def strip_role(raw: str) -> str:
    s = raw
    s = CITE_WITH_LINE.sub("", s)
    s = CITE_NO_LINE.sub("", s)
    s = TRAILING_TAG.sub(" ", s)
    s = s.replace("**", "").replace("*", "").replace("`", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^[\s—\-:;,`]+", "", s)
    s = re.sub(
        r"^(and|then|calls into|via|see also|entry|see|the|is|which|that)\s+",
        "",
        s,
        flags=re.I,
    )
    # Strip an artifact of line-range cites like `foo.c:100-200`: after
    # capturing 100, "200 —" or "200)" may leak into role. Drop a
    # leading bare integer + punctuation.
    s = re.sub(r"^\d+\s*[—\-:;,)\.]\s*", "", s)
    s = s.strip(" -—:;,`.")
    if len(s) > 110:
        s = s[:107]
        s = re.sub(r"\s+\S*$", "", s) + "..."
    return s


def iter_bullets(text: str):
    lines = text.splitlines()
    current: list[str] | None = None
    current_indent = -1
    for line in lines:
        m = BULLET_START.match(line)
        if m:
            if current is not None:
                yield " ".join(current)
            current = [m.group(3).rstrip()]
            current_indent = len(m.group(1))
        else:
            if current is None:
                continue
            if line.strip() == "":
                yield " ".join(current)
                current = None
                current_indent = -1
                continue
            leading = len(line) - len(line.lstrip())
            if leading > current_indent:
                current.append(line.strip())
            else:
                yield " ".join(current)
                current = None
                current_indent = -1
    if current is not None:
        yield " ".join(current)


def extract_cites(text: str):
    seen: dict[tuple[str, int | None], str] = {}

    for bullet in iter_bullets(text):
        cites_with_line = list(CITE_WITH_LINE.finditer(bullet))
        cites_no_line = list(CITE_NO_LINE.finditer(bullet))
        if not cites_with_line and not cites_no_line:
            continue
        role = strip_role(bullet)
        for m in cites_with_line:
            key = (m.group(1), int(m.group(2)))
            if key not in seen or len(role) > len(seen[key]):
                seen[key] = role
        for m in cites_no_line:
            key = (m.group(1), None)
            if key not in seen or len(role) > len(seen[key]):
                seen[key] = role

    for line in text.splitlines():
        for m in CITE_WITH_LINE.finditer(line):
            key = (m.group(1), int(m.group(2)))
            if key in seen and seen[key]:
                continue
            role = strip_role(line)
            if key not in seen or len(role) > len(seen[key]):
                seen[key] = role

    out = [(p, l, d) for (p, l), d in seen.items()]
    out.sort(key=lambda t: (t[0], t[1] if t[1] is not None else 10**9))
    return out


def path_to_file_doc(source_path: str) -> Path | None:
    doc = FILES_DOCS / f"{source_path}.md"
    if doc.exists():
        return doc
    stem = Path(source_path).with_suffix("").as_posix() + ".md"
    doc = FILES_DOCS / stem
    if doc.exists():
        return doc
    return None


def render_path(source_path: str) -> str:
    doc = path_to_file_doc(source_path)
    if doc is None:
        return f"`{source_path}`"
    try:
        rel = doc.relative_to(IDIOMS)
    except ValueError:
        rel = Path("..") / doc.relative_to(ROOT / "knowledge")
    return f"[`{source_path}`]({rel.as_posix()})"


def build_section(cites) -> str:
    lines = [
        "## Call sites",
        MARKER_OPEN,
        "",
        "*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*",
        "*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*",
        "",
        "| File | Line | Role |",
        "|---|---:|---|",
    ]
    for path, ln, role in cites:
        link = render_path(path)
        role_cell = role.replace("|", "\\|") if role else "—"
        line_cell = str(ln) if ln is not None else "—"
        lines.append(f"| {link} | {line_cell} | {role_cell} |")
    lines.append("")
    lines.append(MARKER_CLOSE)
    return "\n".join(lines) + "\n"


def upsert(text: str, section: str) -> str:
    if BLOCK_RE.search(text):
        return BLOCK_RE.sub("\n\n" + section, text)
    m = INSERT_BEFORE.search(text)
    if m:
        return text[: m.start()] + "\n\n" + section + text[m.start():]
    return text.rstrip() + "\n\n" + section


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--layer",
        default="idioms",
        help="knowledge/ subdirectory to process (default: idioms). Also valid: data-structures.",
    )
    args = ap.parse_args()

    global IDIOMS
    IDIOMS = ROOT / "knowledge" / args.layer

    if not IDIOMS.exists():
        print(f"target dir not found: {IDIOMS}")
        return 1
    total = 0
    updated = 0
    zero_cite: list[str] = []
    for path in sorted(IDIOMS.glob("*.md")):
        if path.name.lower() in {"readme.md", "template.md", "_index.md"}:
            continue
        total += 1
        text = path.read_text()
        cites = extract_cites(text)
        if not cites:
            zero_cite.append(path.name)
            continue
        section = build_section(cites)
        new = upsert(text, section)
        if new != text:
            path.write_text(new)
            updated += 1
            with_line = sum(1 for _, ln, _ in cites if ln is not None)
            print(f"[{updated:3d}] {path.name}: {len(cites):3d} cites ({with_line} with line)")
    print()
    print(f"Total idiom docs scanned: {total}")
    print(f"Updated:                  {updated}")
    print(f"Skipped (zero cites):     {len(zero_cite)}")
    if zero_cite:
        print()
        print("Idioms with zero source cites (need manual attention):")
        for n in zero_cite:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
