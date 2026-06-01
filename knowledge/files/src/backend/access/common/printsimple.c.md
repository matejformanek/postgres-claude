# printsimple.c

- **Source path:** `source/src/backend/access/common/printsimple.c`
- **Lines:** 144
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `printsimple.h`, `replication/walsender.c` (primary consumer).

## Purpose

A no-catalog-access DestReceiver. Used by walsender / WAL receivers that aren't bound to any database and therefore can't call out to per-type `typoutput`/`typsend` lookups. Supports a hard-coded subset of builtin types (`TEXT`, `INT4`, `INT8`, `OID`) and only protocol version 3.0. [from-comment, printsimple.c:1-17]

## Top-of-file comment

> "Routines to print out tuples containing only a limited range of builtin types without catalog access. This is intended for backends that don't have catalog access because they are not bound to a specific database, such as some walsender processes." [from-comment, printsimple.c:3-10]

## Public surface

- `printsimple_startup` (32) — emits a `RowDescription` message but with `table oid = 0`, `attnum = 0`, format code 0 for every column (no catalog access needed; reads attlen/atttypid/atttypmod straight off the TupleDesc).
- `printsimple` (60) — emits a `DataRow` message, switching on `attr->atttypid` to render: `TEXT` via `pq_sendcountedtext(VARDATA_ANY)`, `INT4` via `pg_ltoa`, `INT8` via `pg_lltoa`, `OID` via `pg_ultoa_n`. Any other type triggers `elog(ERROR, "unsupported type OID: %u", ...)`. [verified-by-code]

## Key invariants

- This receiver is text-only; the per-column format codes are always 0 in the RowDescription. [verified-by-code, printsimple.c:50]
- Adding a new supported type means editing the switch in `printsimple` AND ensuring callers don't try to send anything else. [verified-by-code, printsimple.c:91-138]

## Cross-references

- Used by `walsender.c` (SHOW commands, IDENTIFY_SYSTEM, TIMELINE_HISTORY, etc.) to return small replication-protocol result sets.

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
