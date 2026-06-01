# spccache.h

- **Source path:** `source/src/include/utils/spccache.h`
- **Lines:** 21
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `spccache.c` (impl).

## Purpose

Three accessor declarations: `get_tablespace_page_costs(spcid, &random, &seq)`, `get_tablespace_io_concurrency(spcid)`, `get_tablespace_maintenance_io_concurrency(spcid)`. The `TableSpaceOpts` struct itself is private to `tablespace.h`/`spccache.c`.

## Confidence tag tally

verified-by-code: 1 — from-comment: 0 — from-readme: 0 — inferred: 0 — unverified: 0
