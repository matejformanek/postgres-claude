# `src/include/storage/large_object.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 100

## Role

Large object (LO, "inversion") API — `pg_largeobject` table
backing, with `lo_*` SQL functions in `inv_api.c`. Each LO is
stored as a sequence of `pg_largeobject` rows keyed by
(loid, pageno) of `LOBLKSIZE` bytes each.

## Public API

- `LargeObjectDesc { id, snapshot, subid, offset, flags }` —
  open-LO handle (lines 39-51)
- `IFS_RDLOCK` / `IFS_WRLOCK` flags (lines 48-49) — record both
  the mode and that permission was already checked at open time
- `inv_create`, `inv_open`, `inv_close`, `inv_drop`
- `inv_seek`, `inv_tell`, `inv_read`, `inv_write`,
  `inv_truncate`

## Invariants

- INV-1: `LOBLKSIZE = BLCKSZ / 4` (line 70). On default 8 KB
  BLCKSZ → 2 KB chunks. **Changing requires initdb** (line 68).
- INV-2: `MAX_LARGE_OBJECT_SIZE = INT_MAX * LOBLKSIZE`
  (line 76) — page numbers limited by `pg_largeobject.pageno`
  being int32. With 2 KB blocks, max LO is ~4 TB.
- INV-3: as of v11, permission check happens at `inv_open`;
  `IFS_RDLOCK`/`IFS_WRLOCK` flags ASSERT that check passed.
  [from-comment] lines 30-32.
- INV-4: `lo_compat_privileges` GUC (line 82) — backwards-compat
  bypass of permission checks. **Setting this disables
  per-call ACL checks on LO read/write.**

## Trust boundary (Phase D)

- `lo_compat_privileges = on` is a **server-wide privilege
  bypass** for backwards-compat with pre-v11 clients. SecDef
  surface: a superuser GUC; a logged-in role with PGOPTIONS
  cannot self-set this (it's `SUSET`). Worth tagging because
  it's a known security trade-off documented in the manual.
- LO operations are SQL-visible (`lo_create`, `lo_import`,
  `lo_export`); `lo_import`/`lo_export` are superuser-only by
  default. The C API itself bypasses SQL permission machinery
  if called from extensions.
- `inv_read(buf, nbytes)` returns int, not ssize_t — capped at
  INT_MAX bytes per call.

## Cross-refs

- `knowledge/files/src/backend/storage/large_object/inv_api.c.md`
  (if exists) — implementation
- `knowledge/files/src/backend/utils/adt/lo.c.md` (if exists) —
  SQL wrappers
- A14 backup angle: a `pg_largeobject` row containing
  attacker-controlled bytes could feed into archive paths.
  [unverified]

## Issues

- ISSUE-TRUST: `lo_compat_privileges` is a GUC-controlled
  permission bypass. Already documented but worth flagging in
  Phase-D inventories. (Informational.)
