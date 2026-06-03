---
path: src/bin/psql/large_obj.h
anchor_sha: 4b0bf0788b0
loc: 15
depth: read
---

# large_obj.h

- **Source path:** `source/src/bin/psql/large_obj.h`
- **Lines:** 15
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `large_obj.c` (implementation), `src/interfaces/libpq/fe-lobj.c` (real work — `lo_import`/`lo_export`/`lo_unlink`).

## Purpose

Extern declarations for the three psql `\lo_*` meta-commands.

## Public surface

- `do_lo_export(loid_arg, filename_arg)` — write LOID to file. [verified-by-code, large_obj.h:11]
- `do_lo_import(filename_arg, comment_arg)` — read file to new LO, optionally COMMENT ON. [verified-by-code, large_obj.h:12]
- `do_lo_unlink(loid_arg)` — delete LO. [verified-by-code, large_obj.h:13]

## Phase D notes

- All three accept raw user file paths and OIDs. Argument validation happens in `large_obj.c`. See that doc for filesystem-access surface.
- No header-level security concern; this is just signatures.

## Confidence tag tally
`[verified-by-code]=3`
