#!/usr/bin/env python3
"""Populate ``## Files owned`` sections in ``knowledge/subsystems/*.md``.

Derives the file ownership from the subsystem slug's implicit directory
mapping:

  access-heap        →  src/backend/access/heap/, src/include/access/heapam*
  access-nbtree      →  src/backend/access/nbtree/, src/include/access/nbtree*
  storage-buffer     →  src/backend/storage/buffer/, src/include/storage/buf*
  storage-lmgr       →  src/backend/storage/lmgr/,  src/include/storage/lock*
  storage-ipc        →  src/backend/storage/ipc/,   src/include/storage/ipc*
  utils-mmgr         →  src/backend/utils/mmgr/,    src/include/utils/mem*
  utils-cache        →  src/backend/utils/cache/,   src/include/utils/*cache*
  contrib-<name>     →  contrib/<name>/
  executor           →  src/backend/executor/,      src/include/executor/
  optimizer          →  src/backend/optimizer/,     src/include/optimizer/
  parser-and-rewrite →  src/backend/parser/, src/backend/rewrite/,
                        src/include/parser/, src/include/rewrite/
  libpq-backend      →  src/backend/libpq/,         src/include/libpq/
  replication        →  src/backend/replication/,   src/include/replication/
  tcop / foreign / jit / main / port / partitioning →
                        src/backend/<slug>/,        src/include/<slug>/

For each subsystem, enumerate `knowledge/files/**/*.md` under its owned
paths and emit a `## Files owned` section with a table. Only file docs
that already exist are included — we don't invent.

Idempotent: re-runs replace the block between markers.
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
SUBSYSTEMS = ROOT / "knowledge" / "subsystems"
FILES_DOCS = ROOT / "knowledge" / "files"

MARKER_OPEN = "<!-- files-owned:auto -->"
MARKER_CLOSE = "<!-- /files-owned:auto -->"

BLOCK_RE = re.compile(
    r"\n*## Files owned\s*\n" + re.escape(MARKER_OPEN) + r".*?" + re.escape(MARKER_CLOSE) + r"\n*",
    re.DOTALL,
)

INSERT_BEFORE = re.compile(
    r"\n(## (Open questions|Unverified|Cross-references|Related|See also|Confidence)\b[^\n]*)"
)


# Manual overrides where slug doesn't match directory 1-to-1.
CUSTOM_PATHS: dict[str, list[str]] = {
    "parser-and-rewrite": [
        "src/backend/parser", "src/include/parser",
        "src/backend/rewrite", "src/include/rewrite",
    ],
    "libpq-backend": ["src/backend/libpq", "src/include/libpq"],
    "headers-wave3": [],  # unclear scope — skip
    "port": ["src/backend/port", "src/port", "src/include/port"],
    "main": ["src/backend/main"],
    "storage-buffer": [
        "src/backend/storage/buffer",
        "src/include/storage",  # buf_internals.h, buf.h, bufmgr.h, bufpage.h
    ],
    "storage-lmgr": [
        "src/backend/storage/lmgr",
        "src/include/storage",
    ],
    "storage-ipc": [
        "src/backend/storage/ipc",
        "src/include/storage",
    ],
    "utils-mmgr": [
        "src/backend/utils/mmgr",
        "src/include/utils",
        "src/include/nodes",
    ],
    "utils-cache": [
        "src/backend/utils/cache",
        "src/include/utils",
    ],
    "access-heap": [
        "src/backend/access/heap",
        "src/include/access",
    ],
    "access-nbtree": [
        "src/backend/access/nbtree",
        "src/include/access",
    ],
    "access-transam": [
        "src/backend/access/transam",
        "src/include/access",
    ],
    "tcop": ["src/backend/tcop", "src/include/tcop"],
    "executor": ["src/backend/executor", "src/include/executor"],
    "optimizer": ["src/backend/optimizer", "src/include/optimizer"],
    "partitioning": ["src/backend/partitioning", "src/include/partitioning"],
    "foreign": ["src/backend/foreign", "src/include/foreign"],
    "jit": ["src/backend/jit", "src/include/jit"],
    "replication": ["src/backend/replication", "src/include/replication"],
}

# For headers-under-shared-dirs, use a filename hint to filter includes.
INCLUDE_FILTERS: dict[str, list[str]] = {
    "storage-buffer": ["buf", "bufmgr", "bufpage"],
    "storage-lmgr": ["lock", "lwlock", "lmgr", "proc", "predicate"],
    "storage-ipc": ["ipc", "shm", "latch", "pmsignal", "sinval", "procarray", "procsignal"],
    "utils-mmgr": ["palloc", "memutil", "memnodes", "mcxt", "aset", "generation", "slab", "bump"],
    "utils-cache": ["cache", "syscache", "catcache", "relcache", "typcache", "plancache", "inval"],
    "access-heap": ["heapam", "heap", "hio", "visibilitymap", "vacuum", "tuple", "htup"],
    "access-nbtree": ["nbtree", "nbtxlog"],
    "access-transam": ["xact", "xlog", "commit_ts", "clog", "multixact", "subtrans", "transam", "twophase"],
}


def slug_to_paths(slug: str) -> list[str]:
    if slug in CUSTOM_PATHS:
        return list(CUSTOM_PATHS[slug])
    if slug.startswith("contrib-"):
        name = slug[len("contrib-"):]
        return [f"contrib/{name}"]
    # Fallback: single-segment slug → src/backend/<slug>/
    return [f"src/backend/{slug}"]


def files_under(paths: list[str], filters: list[str] | None = None) -> list[str]:
    """Return sorted source-relative paths whose file docs exist."""
    hits: list[str] = []
    for p in paths:
        base = FILES_DOCS / p
        if not base.exists():
            continue
        for md in base.rglob("*.md"):
            rel = md.relative_to(FILES_DOCS).with_suffix("").as_posix()
            # If this is an include-dir with a filter, apply it.
            is_include = "/include/" in md.as_posix()
            if is_include and filters is not None:
                name = md.stem
                if not any(f in name for f in filters):
                    continue
            hits.append(rel)
    return sorted(set(hits))


def render_row(src_path: str) -> str:
    # Link to the file doc under knowledge/files/.
    rel = f"../files/{src_path}.md"
    return f"| [`{src_path}`]({rel}) |"


def build_section(files: list[str], slug: str) -> str:
    lines = [
        "## Files owned",
        MARKER_OPEN,
        "",
        f"*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*",
        "",
    ]
    if not files:
        lines.append("_(no file docs under the derived paths — check `CUSTOM_PATHS` in the refresh script if this is wrong)_")
        lines.append("")
        lines.append(MARKER_CLOSE)
        return "\n".join(lines) + "\n"
    lines.append(f"**{len(files)} files.**")
    lines.append("")
    lines.append("| File |")
    lines.append("|---|")
    for f in files:
        lines.append(render_row(f))
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
    if not SUBSYSTEMS.exists() or not FILES_DOCS.exists():
        print("subsystems or files dir missing")
        return 1
    updated = 0
    empty = []
    for p in sorted(SUBSYSTEMS.glob("*.md")):
        if p.name.lower() in {"readme.md", "_index.md", "template.md"}:
            continue
        slug = p.stem
        paths = slug_to_paths(slug)
        if not paths:
            empty.append(slug)
            continue
        files = files_under(paths, INCLUDE_FILTERS.get(slug))
        text = p.read_text()
        section = build_section(files, slug)
        new = upsert(text, section)
        if new != text:
            p.write_text(new)
            updated += 1
            print(f"{slug}: {len(files):4d} files owned")
        if not files:
            empty.append(slug)

    print()
    print(f"Updated: {updated}")
    if empty:
        print(f"Empty (no matching file docs): {len(empty)}")
        for e in empty:
            print(f"  - {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
