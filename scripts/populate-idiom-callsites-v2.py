#!/usr/bin/env python3
"""Second-pass extractor for idioms without `source/<path>:<line>` cites.

Some idioms describe patterns via bare backticked C identifiers
(e.g. `fmgr_info`, `Node`, `raw_parser`) rather than file:line
cites. For those, this script cross-references each identifier
against `knowledge/glossary.md` (which links each term to its
`knowledge/files/<path>.md` doc, which resolves to a source path).

Populates a `## Call sites` section for the 4 idioms the primary
extractor skipped:

  - fmgr.md
  - node-types-and-lists.md
  - parser-pipeline.md
  - spi.md

Emitted rows have `—` in the Line column (glossary-derived — the
file is known, the definition line is not without a source-tree
grep, which is a future improvement).

Idempotent: re-runs replace the block between markers, same as v1.
"""
from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

TARGETS = [
    "fmgr.md",
    "node-types-and-lists.md",
    "parser-pipeline.md",
    "spi.md",
]

MARKER_OPEN = "<!-- callsites:auto -->"
MARKER_CLOSE = "<!-- /callsites:auto -->"

BLOCK_RE = re.compile(
    r"\n*## Call sites\s*\n" + re.escape(MARKER_OPEN) + r".*?" + re.escape(MARKER_CLOSE) + r"\n*",
    re.DOTALL,
)

INSERT_BEFORE = re.compile(
    r"\n(## (Open questions|Unverified|Cross-references|Related idioms|See also|Scenarios that use me)\b[^\n]*)"
)

# Match glossary entries: `### term\n<desc>...(via `knowledge/files/<path>.md`).`
GLOSSARY_ENTRY = re.compile(
    r"^### ([A-Za-z_][A-Za-z0-9_]+)\s*\n(.+?)(?=\n### |\n<!-- |\Z)",
    re.DOTALL | re.MULTILINE,
)
VIA_PATH = re.compile(r"via `knowledge/files/([A-Za-z0-9_./+-]+?\.md)`")

# Stop words / non-identifier backticked things.
STOP_WORDS = {
    "true", "false", "NULL", "int", "char", "void", "sizeof", "const",
    "static", "extern", "return", "if", "else", "for", "while", "do",
    "switch", "case", "break", "continue", "goto", "typedef", "struct",
    "union", "enum", "signed", "unsigned", "short", "long", "float",
    "double", "SELECT", "INSERT", "UPDATE", "DELETE", "CALL", "MERGE",
    "EXPLAIN", "RESET", "SET", "SHOW", "PREPARE", "EXECUTE", "DECLARE",
    "FETCH", "CLOSE", "TRANSACTION", "COMMIT", "ROLLBACK", "SAVEPOINT",
    "BEGIN", "END", "GRANT", "REVOKE", "CREATE", "DROP", "ALTER",
}


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
IDIOMS = ROOT / "knowledge" / "idioms"
FILES_DOCS = ROOT / "knowledge" / "files"
GLOSSARY = ROOT / "knowledge" / "glossary.md"


def load_glossary_index() -> dict[str, tuple[str, str]]:
    """term → (source_path, first_sentence_of_desc)."""
    if not GLOSSARY.exists():
        return {}
    text = GLOSSARY.read_text()
    idx: dict[str, tuple[str, str]] = {}
    for m in GLOSSARY_ENTRY.finditer(text):
        term = m.group(1)
        body = m.group(2).strip()
        vm = VIA_PATH.search(body)
        if not vm:
            continue
        file_doc_rel = vm.group(1)  # e.g. src/backend/access/heap/heapam.c.md
        # Convert file-doc path to source path
        if file_doc_rel.endswith(".md"):
            src_path = file_doc_rel[:-3]
        else:
            src_path = file_doc_rel
        # First sentence of desc (strip markdown backticks).
        desc = re.sub(r"\s+", " ", body).strip()
        # Cut at first period followed by space, or at 120 chars.
        first = re.split(r"(?<=[.!?])\s+", desc, maxsplit=1)[0]
        if len(first) > 120:
            first = first[:117].rstrip() + "..."
        idx[term] = (src_path, first)
    return idx


def extract_identifiers(text: str) -> list[str]:
    ids = re.findall(r"`([A-Za-z_][A-Za-z0-9_]{2,})`", text)
    out = []
    seen = set()
    for i in ids:
        if i in STOP_WORDS or i.isdigit():
            continue
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def build_callsites(idiom_text: str, glossary_idx: dict[str, tuple[str, str]]):
    """Return sorted list of (path, None, role) tuples for this idiom."""
    ids = extract_identifiers(idiom_text)
    hits: dict[str, list[tuple[str, str]]] = defaultdict(list)  # path → [(term, role)]
    for term in ids:
        if term in glossary_idx:
            path, desc = glossary_idx[term]
            hits[path].append((term, desc))
    out = []
    for path, entries in sorted(hits.items()):
        entries.sort()
        # Combine role hints from multiple identifiers that live in the same file.
        role = "; ".join(f"`{t}` — {d.split('.')[0]}" for t, d in entries[:2])
        if len(entries) > 2:
            role += f"; +{len(entries) - 2} more terms"
        if len(role) > 140:
            role = role[:137].rstrip() + "..."
        out.append((path, None, role))
    return out


def render_path(source_path: str) -> str:
    doc = FILES_DOCS / f"{source_path}.md"
    if not doc.exists():
        stem = Path(source_path).with_suffix("").as_posix() + ".md"
        doc = FILES_DOCS / stem
    if not doc.exists():
        return f"`{source_path}`"
    rel = Path("..") / doc.relative_to(ROOT / "knowledge")
    return f"[`{source_path}`]({rel.as_posix()})"


def build_section(cites, source_note: str) -> str:
    lines = [
        "## Call sites",
        MARKER_OPEN,
        "",
        f"*{source_note}*",
        "*Refresh via `scripts/populate-idiom-callsites-v2.py` — edits inside this block are overwritten.*",
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
    glossary_idx = load_glossary_index()
    print(f"Glossary index loaded: {len(glossary_idx)} terms → file paths")
    print()

    updated = 0
    for name in TARGETS:
        path = IDIOMS / name
        if not path.exists():
            print(f"SKIP: {name} (not found)")
            continue
        text = path.read_text()
        cites = build_callsites(text, glossary_idx)
        if not cites:
            print(f"{name}: 0 identifier hits in glossary — skipped")
            continue
        section = build_section(
            cites,
            "Auto-extracted via glossary cross-reference of backticked C identifiers in this doc.",
        )
        new = upsert(text, section)
        if new != text:
            path.write_text(new)
            updated += 1
            print(f"{name}: {len(cites)} call sites (via glossary)")

    print()
    print(f"Updated: {updated}/{len(TARGETS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
