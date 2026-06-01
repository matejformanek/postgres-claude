# publicationcmds.c

- **Source path:** `source/src/backend/commands/publicationcmds.c`
- **Lines:** 2314
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Publication manipulation." [from-comment, publicationcmds.c:3-4] CREATE / ALTER / DROP PUBLICATION — the publisher side of logical replication. Subscribers live in `subscriptioncmds.c`. Runtime publication-filtering during logical decoding is in `replication/logical/`.

## Public surface

- `CreatePublication`, `AlterPublication`, `RemovePublicationById`, `RemovePublicationRelById`, `RemovePublicationSchemaById` — pg_publication / pg_publication_rel / pg_publication_namespace DDL.
- Helpers: validate row filters (must be IMMUTABLE in their column refs to ensure deterministic per-row decisions), validate column lists, recurse into partitioned tables.
- `OpenTableList`, `CloseTableList`, `PublicationAddTables`, `PublicationDropTables`, `PublicationAddSchemas`, `PublicationDropSchemas` — split-out helpers for `ALTER PUBLICATION ... ADD/DROP/SET ...`.

## Row filters & column lists (PG 15+)

`CREATE PUBLICATION p FOR TABLE t (id, data) WHERE (data IS NOT NULL)` — the row filter must reference only columns in the replica-identity index (publisher's REPLICA IDENTITY); else UPDATE/DELETE cannot be replicated because the subscriber wouldn't be able to apply the filter on the old tuple. This file enforces that check.

## MAX_RELCACHE_INVAL_MSGS

`publicationcmds.h` defines this as 4096 — the cap on how many invalidation messages an ALTER PUBLICATION can emit before falling back to "invalidate ALL relations". Same as MAXNUMMESSAGES in sinvaladt.c.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
