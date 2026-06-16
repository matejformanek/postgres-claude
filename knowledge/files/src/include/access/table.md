# `access/table.h` — `table_open` / `table_close` front-door

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/table.h`)

## Role
Tiny header exposing the five front-door functions every backend uses to
acquire and release a `Relation` handle for a table. The actual lock-and-
relcache work lives in `src/backend/access/table/table.c`; this header is
the include point.

## Public API
- `table_open(Oid relationId, LOCKMODE lockmode)` (`table.h:21`) —
  open by OID, error if not found, error if it's an index/composite type.
- `table_openrv(const RangeVar *relation, LOCKMODE lockmode)` (`table.h:22`).
- `table_openrv_extended(rv, lockmode, missing_ok)` (`table.h:23`-`24`) —
  return InvalidRelation if `missing_ok` and not found.
- `try_table_open(Oid, LOCKMODE)` (`table.h:25`) — return NULL on missing.
- `table_close(Relation, LOCKMODE)` (`table.h:26`) — release the lock
  acquired by `table_open` (if `NoLock` was used to open, must use NoLock
  to close).

## Invariants
- Every `table_open` must be paired with a `table_close`. `[from-comment]`
  (verified in `src/backend/access/table/table.c`).
- The lock acquired by `table_open` is automatically released at transaction
  end **only if** the caller never calls `table_close`. The convention is
  to pair them explicitly for non-trivial paths. `[inferred]`.
- Errors out if the relation is not a table (index, composite type, etc.)
  — index lookups must use `index_open` from `genam.h`. `[from-comment]`.

## Notable internals
- The header includes `nodes/primnodes.h` (for `RangeVar`),
  `storage/lockdefs.h` (for `LOCKMODE`), and `utils/relcache.h` (for
  `Relation`).
- Only 5 functions; the rest of the table-AM interface lives in `tableam.h`.

## Trust-boundary / Phase D surface

This is the canonical entry point for opening a table; lock acquisition and
the access-permission check (`aclcheck`) happen at *callers* of these
functions, not inside. The headers don't enforce a permission contract.

**[ISSUE-audit-gap: `table_open` does no permission check (informational)]** —
Callers are expected to have already done `pg_class_aclcheck` /
`RangeVarGetRelidExtended` permission validation. Any caller that opens a
relation by raw OID without prior permission validation creates a confused-
deputy hole. Common in contrib (pageinspect, pgstattuple, pg_freespacemap)
where the SQL-level entry point is the only gate (A6/A12 finding pattern).
`table.h:21`-`26`.

## Cross-refs
- `knowledge/files/src/include/access/tableam.h` — once opened, the relation's
  `rd_tableam` is the dispatch table.
- `knowledge/files/src/include/access/genam.h` — `index_open` / `index_close`
  for indexes.
- A6/A12 contrib audit findings: pageinspect functions take raw OID;
  perm check happens at SQL grant level only.

<!-- issues:auto:begin -->
- [Issue register — `include-access`](../../../../issues/include-access.md)
<!-- issues:auto:end -->

## Issues
1. **[ISSUE-audit-gap: no permission check in table_open (informational)]**
   — `table.h:21`-`26`. Caller's responsibility, contract not enforced
   at the API boundary.
