# multixact_read_v18.h

## Purpose

Declares the `OldMultiXactReader` interface for reading
`pg_multixact/offsets` and `pg_multixact/members` from a pre-v19
cluster. The format change between v18 and v19 is that
`MultiXactOffset` widened from `uint32` to `uint64`; this header
defines a `MultiXactOffset32` typedef so the reader doesn't collide
with the new backend's macros.

## Role in pg_upgrade

Used exclusively by `multixact_rewrite.c` (writer) for the
pre-v19→current format conversion. Driven from `pg_upgrade.c` for the
"create new objects" phase.

## Public surface

- `MultiXactOffset32` = `uint32` (line 18).
- `OldMultiXactReader` struct (lines 20-27): `nextMXact`, `nextOffset`
  (32-bit), and two `SlruSegState *` for offsets and members.
- `AllocOldMultiXactRead(pgdata, nextMulti, nextOffset)` — opens both
  SLRUs at `<pgdata>/pg_multixact/offsets` and `.../members` with
  `long_segment_names=false` (the pre-v19 short-name format).
- `GetOldMultiXactIdSingleMember(state, multi, &member)` — returns one
  member per multi (the updating XID if present, else first locking).
  Returns false on invalid entry.
- `FreeOldMultiXactReader(state)`.

## Phase D notes

- The header explicitly refuses `multixact_internal.h` include (see
  the `#error` in multixact_read_v18.c:28) — prevents the old/new
  macro collision that would silently corrupt the reader.
- 32-bit width is fixed in stone here; the wraparound math in
  `GetOldMultiXactIdSingleMember` (multixact_read_v18.c:225-249) is
  tied to this width.

[from-comment] "MultiXactOffset changed from uint32 to uint64 between
versions 18 and 19" — header comment line 14.
