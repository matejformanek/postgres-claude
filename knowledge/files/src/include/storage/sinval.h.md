# `storage/sinval.h`

- **Source:** `source/src/include/storage/sinval.h` (167 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Defines the **shared-cache invalidation message format** and the
producer/consumer interface (`SendSharedInvalidMessages`,
`ReceiveSharedInvalidMessages`).

## Message taxonomy

A `SharedInvalidationMessage` is a union; `id` (the first int8)
discriminates:

- **`id >= 0`** — `SharedInvalCatcacheMsg`: invalidate a specific
  tuple in catcache `id`. Carries `dbId` + `hashValue`.
- **`SHAREDINVALCATALOG_ID = -1`** — `SharedInvalCatalogMsg`:
  invalidate *all* catcache entries for a given catalog (`catId`).
- **`SHAREDINVALRELCACHE_ID = -2`** — `SharedInvalRelcacheMsg`:
  invalidate a relcache entry (`relId=0` ⇒ whole relcache).
- **`SHAREDINVALSMGR_ID = -3`** — `SharedInvalSmgrMsg`: smgr
  invalidation for a specific physical relfilelocator. Carries
  optional backend ID (for temp relations).
- **`SHAREDINVALRELMAP_ID = -4`** — relation-mapping update for a
  database (refresh `pg_filenode.map`).
- **`SHAREDINVALSNAPSHOT_ID = -5`** — invalidate any saved snapshot
  for a specific relation.
- **`SHAREDINVALRELSYNC_ID = -6`** — invalidate a RelationSyncCache
  entry (logical-replication relation tracking).

## Transactional vs immediate

Header comment (`:50-58`):

> "Catcache, relcache, relsynccache, and snapshot invalidations are
> transactional, and so are sent to other backends upon commit.
> Internally to the generating backend, they are also processed at
> CommandCounterIncrement so that later commands in the same
> transaction see the new state."
>
> "smgr and relation mapping invalidations are non-transactional:
> they are sent immediately when the underlying file change is made."

This split matters: a backend that *creates* a relation issues an smgr
inval immediately so other backends can open the same file, but the
relcache entry is committed later.

## Hash collision risk

> "Since we transmit only a hash key, there is a small risk of
> unnecessary invalidations due to chance matches of hash keys."
> `:39-43`.

Extra invals are correctness-safe but performance-costly. The
hashValue collision rate is empirically near-zero for typical
workloads.

## `catchupInterruptPending` global

`volatile sig_atomic_t` — set by signal handler, polled by main loop
(in `ProcessClientReadInterrupt` and similar). Cleared after
processing.

## Functions

- `SendSharedInvalidMessages(msgs, n)` — push into shared queue.
- `ReceiveSharedInvalidMessages(invalFunc, resetFunc)` — pull + dispatch.
- `HandleCatchupInterrupt` — signal-handler-safe flag set.
- `ProcessCatchupInterrupt` — late processing.
- `xactGetCommittedInvalidationMessages` / `inplaceGetInvalidationMessages`
  — read messages from a finishing transaction (called by xact.c).
- `ProcessCommittedInvalidationMessages` — apply a batch from
  the WAL (recovery / inplace updates).
- `LocalExecuteInvalidationMessage` — single-message dispatch (used
  inside `inval.c`).

## Synthesized by
<!-- backlinks:auto -->
- [idioms/syscache-invalidation-flow.md](../../../../idioms/syscache-invalidation-flow.md)
