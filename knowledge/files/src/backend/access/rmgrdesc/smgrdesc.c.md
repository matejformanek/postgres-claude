---
path: src/backend/access/rmgrdesc/smgrdesc.c
anchor_sha: 4b0bf0788b0
loc: 59
depth: read
---

# smgrdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/smgrdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 59

## Purpose

rmgr descriptor routines for the storage-manager resource manager
(`RM_SMGR_ID`, records from `catalog/storage.c`). Renders the 2 smgr WAL
opcodes — relation-fork file CREATE and TRUNCATE — for `pg_waldump`.
[from-comment, smgrdesc.c:3-4]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `smgr_desc(buf, record)` | `smgrdesc.c:20` | render one smgr record |
| `smgr_identify(info)` | `smgrdesc.c:43` | opcode → short name |

## Invariants & gotchas

- **Renders the relation path via `relpathperm(...).str`**
  (smgrdesc.c:31, 38) — `relpathperm` returns a `RelPathStr` by value
  whose `.str` member is the formatted `base/<db>/<relfilenode>` path.
  CREATE uses the record's `forkNum`; TRUNCATE hardcodes `MAIN_FORKNUM`
  for the path but prints the per-fork `flags` bitmap separately.
  `[verified-by-code]`
- **`relpathperm` returning a struct-by-value is the post-refactor
  API** — older trees returned a `char *` needing `pfree`. The `.str`
  access pattern is the current idiom; a stale citation calling
  `pfree(relpathperm(...))` would be against an old tree.
- **`smgr_desc` is an `if/else if` chain, no final else** — unknown
  opcode → empty string; `smgr_identify` returns `NULL` for unknowns.

## Cross-refs

- `xl_smgr_create` / `xl_smgr_truncate` + `XLOG_SMGR_*` + `SMGR_TRUNCATE_*`
  flags: `[[src/include/catalog/storage_xlog.h]]`.
- `relpathperm` / `RelPathStr`: `[[src/include/common/relpath.h]]`.
- The storage engine: `source/src/backend/catalog/storage.c`.
- Descriptor format conventions: `source/src/backend/access/rmgrdesc/README`.
