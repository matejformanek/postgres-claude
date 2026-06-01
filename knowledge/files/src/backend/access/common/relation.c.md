# relation.c

- **Source path:** `source/src/backend/access/common/relation.c`
- **Lines:** 217
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `relation.h`, `table.c` (`table_open` wrappers), `index.c` / `indexam.c` (`index_open`), `relcache.c`.

## Purpose

The lowest-level "open any relation by OID" helpers, shared by tables, indexes, sequences, foreign tables, partitioned tables — anything with a `pg_class` entry. Centralises the lock-then-relcache-lookup order and the bookkeeping for temporary-namespace access. Callers that want type-specific guards (e.g. "must be a table, not an index") use `table_open` / `index_open` / `sequence_open` which wrap these. [from-comment, relation.c:13-17]

## Top-of-file comment

> "This file contains relation_ routines that implement access to relations (tables, indexes, etc). Support that's specific to subtypes of relations should go into their respective files, not here." [from-comment, relation.c:13-17]

## Public surface

- `relation_open` (47) — Lock then `RelationIdGetRelation`. Asserts that some lock is held when `lockmode == NoLock` (except in bootstrap mode). Marks `XACT_FLAGS_ACCESSEDTEMPNAMESPACE` if the relation uses local buffers (i.e. is a temp table or a session-local mapping). [verified-by-code]
- `try_relation_open` (88) — Same, but lock-first-then-existence-check (via `SearchSysCacheExists1(RELOID, ...)`); on miss it releases the useless lock and returns NULL. [verified-by-code]
- `relation_openrv` (137), `relation_openrv_extended` (172) — Resolve a `RangeVar` through namespace search (`RangeVarGetRelid`) and then call `relation_open`. Call `AcceptInvalidationMessages()` first when locking, because GRANT/REVOKE update ACLs without taking a relation lock. [from-comment, relation.c:142-152]
- `relation_close` (205) — `RelationClose` (decrement relcache pin) then optionally release the heavyweight lock.

## Key invariants and locking

- **Lock is acquired BEFORE the relcache lookup.** This is essential: between determining the OID and opening the relcache entry, a concurrent DROP could otherwise complete and we'd see a phantom relation. [verified-by-code, relation.c:54-59]
- `lockmode == NoLock` is only safe when the caller already holds a sufficient lock; this is Assert-checked via `CheckRelationLockedByMe(r, AccessShareLock, true)`. Bootstrap mode skips the assert. [verified-by-code, relation.c:65-70]
- `relation_close` does NOT release locks acquired with `NoLock`. It is common and intentional to hold a relation lock past `relation_close` — the lock will be released at xact end. [from-comment, relation.c:200-203]
- `relation_openrv` calls `AcceptInvalidationMessages()` before name resolution, because some catalog DDL (GRANT/REVOKE) issues invalidations without a relation lock. Skipped for `NoLock` callers. [from-comment, relation.c:142-152]

## Cross-references

- Wrappers in `table.c`, `sequence.c`, `index.c`/`indexam.c` add relkind validation on top.
- Calls into: `storage/lmgr/lmgr.c` (`LockRelationOid` / `UnlockRelationOid` / `UnlockRelationId`), `utils/cache/relcache.c` (`RelationIdGetRelation` / `RelationClose`), `catalog/namespace.c` (`RangeVarGetRelid`), `utils/cache/inval.c` (`AcceptInvalidationMessages`).

## Open questions

- The TODO-flavoured comment in `relation_openrv` ("XXX this all could stand to be redesigned") refers to the fact that NoLock callers can race with concurrent GRANT. Not chased. [unverified]

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
