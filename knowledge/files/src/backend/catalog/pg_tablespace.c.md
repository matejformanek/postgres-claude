# pg_tablespace.c

- **Source path:** `source/src/backend/catalog/pg_tablespace.c`
- **Lines:** ~80
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_tablespace relation." Tiny: just the directory-existence check used by CREATE TABLESPACE. Most tablespace logic lives in `commands/tablespace.c`.

## Public surface

- `directory_is_empty` — predicate over a filesystem path used at CREATE/DROP TABLESPACE.

## Confidence tag tally

`[inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
