# `src/backend/storage/file/reinit.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~400
- **Source:** `source/src/backend/storage/file/reinit.c`

## Purpose

Reinitializes unlogged relations after a crash restart. Unlogged
relations are not WAL-logged, so on crash their data fork is gone
(unreliable); but PG also keeps an `_init` fork that contains the
empty-relation image. On restart, the startup process calls
`ResetUnloggedRelations` which (a) deletes the main fork of every
unlogged rel and (b) copies the `_init` fork into its place.
[from-comment] (`reinit.c:1-12`, `36-45`)

## Top of file

`ResetUnloggedRelations(op)` takes a bitmask of:
- `UNLOGGED_RELATION_CLEANUP` — drop main/FSM/VM forks of any rel that
  has an init fork.
- `UNLOGGED_RELATION_INIT` — copy init fork → main fork.

Both phases happen at startup, in that order.

## Public surface (reinit.h)

- `ResetUnloggedRelations(int op)`
- `parse_filename_for_nontemp_relation(name, ...)` — helper that
  parses a filename like `12345_init.1` into (relnumber, fork, segno).

## Types

- `unlogged_relation_entry` (lines 32–35): hash entry, just an
  RelFileNumber, for "this rel needs reinit".

## Cross-refs

- Outbound: `copy_file` (copydir.c), `RemoveDir`/`unlink_if_exists`
  helpers.
- Inbound: `startup.c` (StartupXLOG → ResetUnloggedRelations).

## Tag tally

`[from-comment]` 3 / `[verified-by-code]` 0 / `[unverified]` 0.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
