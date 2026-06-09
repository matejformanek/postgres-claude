# `src/include/access/rmgrdesc_utils.h`

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**23 lines.**

## Role

Shared helpers for per-rmgr `*_desc` callbacks (the routines that
format a WAL record for `pg_waldump` output). Centralizes formatting
of arrays-of-offsets, redirect pointers, and OIDs so that each rmgrdesc
file in `src/backend/access/rmgrdesc/` doesn't reinvent the wheel.
[verified-by-code] `source/src/include/access/rmgrdesc_utils.h:1-22`

## Public API

Four extern functions (lines 15-20):

- `array_desc(buf, array, elem_size, count, elem_desc, data)` —
  generic per-element renderer; calls a user-supplied `elem_desc`
  function for each element with a `StringInfo` buffer.
- `offset_elem_desc(buf, offset, data)` — prints an `OffsetNumber`.
- `redirect_elem_desc(buf, offset, data)` — prints an HOT-redirect
  pointer (offset → offset).
- `oid_elem_desc(buf, relid, data)` — prints an `Oid`.

The `(void *elem, void *data)` signature is the standard
"iterator-with-context" idiom in PG.

## Invariants

- Output goes to a `StringInfo` (caller-allocated). Callers
  conventionally append `", "` between elements (the helpers do not).
- These functions are called from `*_desc` callbacks which run inside
  `pg_waldump` AND inside the startup process when
  `wal_debug = on` — so they MUST NOT longjmp or palloc into a
  short-lived context unexpectedly.

## Notable internals

The header is implementation-light; only function decls. Actual code is
in `src/backend/access/rmgrdesc/rmgrdescutils.c`.

## Trust-boundary / Phase D surface

These helpers run on **untrusted WAL bytes** during `pg_waldump`. A
malformed offset array could in principle cause an over-read of the
caller's buffer if the per-rmgr `*_desc` doesn't validate `count`
against the record length before calling `array_desc`. The bounds
discipline lives in the per-rmgr `desc` routines, not here.

## Cross-refs

- `access/rmgrlist.h` — defines which `*_desc` is registered.
- `src/backend/access/rmgrdesc/` — the consumers.
- `access/xlog_internal.h` — `XLogRecGetData` / `XLogRecGetBlockData`
  which feed these helpers.

## Issues

- **ISSUE-doc**: the `void *data` parameter is undocumented at the
  header level; callers must read `rmgrdescutils.c` to learn that
  most helpers ignore it.
