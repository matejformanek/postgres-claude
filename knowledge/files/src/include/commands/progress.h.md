# src/include/commands/progress.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 207 [verified-by-code]

## Role

Constant register file for `pg_stat_progress_*` views. Defines the
**slot indices and enumerated phase / mode values** that long-running
commands publish via `pgstat_progress_update_param()` and that
system views materialize.

## Public API (constant groups)

- VACUUM (`:21-51`): 13 slots; `PROGRESS_VACUUM_PHASE` (6 phases),
  `PROGRESS_VACUUM_MODE` (NORMAL / AGGRESSIVE / FAILSAFE),
  `PROGRESS_VACUUM_STARTED_BY` (MANUAL / AUTOVACUUM /
  AUTOVACUUM_WRAPAROUND).
- ANALYZE (`:54-74`): 10 slots; 5 phases; STARTED_BY.
- REPACK (formerly CLUSTER) (`:77-106`): 10 slots; 8 phases. Comment
  notes CLUSTER is "now deprecated" so the values are shared
  (`:81-83`).
- CREATE INDEX (`:109-141`): 15 slots; 9 phases (mostly WAIT_*); 4
  subphases reserved for the AM; 4 commands (CREATE /
  CREATE_CONCURRENTLY / REINDEX / REINDEX_CONCURRENTLY).
- WAITFOR (`:145-147`): generic lock-waitee slots.
- SCAN_BLOCKS (`:150-151`): generic 15/16 slot pair for any
  relation-scan phase.
- pg_basebackup (`:154-170`): 6 slots; 5 phases; FULL / INCREMENTAL.
- COPY (`:173-189`): 7 slots; FROM/TO; FILE / PROGRAM / PIPE /
  CALLBACK type.
- DATACHECKSUMS (`:192-205`): 7 slots; 5 phases — added in PG18 for the
  background `datachecksumsworker`.

## Invariants

- INV-PROGRESS-SYNCH-VIEWS: header comment line 6-8 [from-comment]
  warns that updating these constants **also requires updating
  `system_views.sql`** — the views literally hard-code the slot
  indices. Drift between this header and that SQL produces silent
  mis-labelled columns in `pg_stat_progress_*`.
- INV-PROGRESS-SLOT-CAP: backend status has a fixed number of progress
  parameter slots (`PgBackendStatus.st_progress_param[]`); a command
  registering > that limit overflows. Max is in
  `backend_status.h`/`stat.c` (not this header).
- Slot indices are **NOT** unique across commands — each command
  reuses the small-integer space. The view definition disambiguates
  by joining on `progress_command`.

## Trust boundary / Phase D surface

- **A11 / A14 monitoring-as-extraction.** `pg_stat_progress_*` views
  are readable by any role with `pg_read_all_stats` (or any role that
  meets `has_privs_of_role(MEMBER OF target_role)`). The progress
  counters leak:
  - block counts of any relation being VACUUM-ed → relation-size oracle.
  - `PROGRESS_REPACK_INDEX_RELID` (`:87`) → catalog OID exposure of
    indexes the role wouldn't otherwise see.
  - `PROGRESS_ANALYZE_CURRENT_CHILD_TABLE_RELID` (`:61`) → partition
    catalog OIDs.
  - `PROGRESS_COPY_BYTES_*` (`:173-174`) → file size of `COPY ... FROM
    '/etc/passwd'` (the actual read is gated, but the byte counter
    is published).
- **A11 echo (cleartext exposure).** Progress reporting itself does
  not capture query text, so it's NOT the cleartext-password leak
  vector. `queryjumble.h` / `pg_stat_statements` are that vector.
- **Side-channel:** phase transitions are visible at sub-second
  granularity; an attacker watching `pg_stat_progress_vacuum` for a
  target table can infer table size + tuple distribution.

## Cross-references

- `utils/backend_progress.h` — the `pgstat_progress_*` update API.
- `backend/utils/activity/backend_progress.c` — implementation.
- `src/backend/catalog/system_views.sql` — the view DDL that consumes
  these constants by index.
- `commands/wait.h` — A18 WAIT statement; conceptually progress-adjacent.
- `commands/repack.h` — issues these REPACK_* values.

## Issues / drift

- `[ISSUE-TRUST: A11/A14 — relation OIDs and byte counters published in pg_stat_progress_* are readable by pg_read_all_stats but not filtered by per-relation SELECT privilege (medium)] — source/src/include/commands/progress.h:21-205`
- `[ISSUE-DOC: comment says "you probably also need to update the views" but no CI lint enforces it; silent drift possible (medium)] — source/src/include/commands/progress.h:6-8`
- `[ISSUE-CODE: slot-index space is reused across commands (e.g. slot 0 means different things for VACUUM vs COPY); a future X-macro consolidation would catch typos (low)] — source/src/include/commands/progress.h:21-205`
