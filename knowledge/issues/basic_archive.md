# Issues — `contrib/basic_archive`

Sample WAL archive module. 1 source file / ~298 LOC.

**Parent docs:** `knowledge/files/contrib/basic_archive/basic_archive.c.md`.

**Source:** 2 entries surfaced 2026-06-09 by A14-2.

## Headlines

1. **TOCTOU between `stat` and `durable_rename`** — acknowledged in code comment; in pathological multi-writer-same-dir setups can silently overwrite.
2. GUC check is length-only, no path-safety check — operator's responsibility.

## Entries — `basic_archive.c`

- [ISSUE-defense-in-depth: GUC check is length-only, no path-safety check (nit)] — `:95-117`
- [ISSUE-concurrency: TOCTOU between `stat` and `durable_rename` (maybe)] — `:164,207-211`

## Cross-sweep references

- A14 basebackup_to_shell — sister module.
- A8 archive_command — original cluster.
