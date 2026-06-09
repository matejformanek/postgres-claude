# `pg_prewarm/pg_prewarm.c` — synchronous block-range prewarmer

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_prewarm/pg_prewarm.c`)

## Role

Single SQL function `pg_prewarm` that, given a relation, fork, and block
range, either (a) `posix_fadvise`-prefetches, (b) `smgrread`s into a
private buffer, or (c) `ReadBuffer`s into `shared_buffers` via the read
stream API. Useful for warming caches after a restart. Companion piece
to `autoprewarm.c` (auto-dump/load bgworker).

## Public API

- `pg_prewarm(regclass, mode text, fork text, first_block int8, last_block int8) -> int8` — `source/contrib/pg_prewarm/pg_prewarm.c:60`

## Invariants

- Args 0, 1, 2 (relation, type, fork) must be non-NULL; nulls 3/4
  default to 0 and `nblocks-1` [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:80-110, 168-191`).
- Prewarm mode is one of `prefetch`, `read`, `buffer`; anything else
  errors out [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:91-104`).
- For an index, the parent table is locked **before** the index to
  match the standard lock order, and then re-verified via
  `IndexGetRelation` to catch a drop+reuse race [from-comment]
  (`source/contrib/pg_prewarm/pg_prewarm.c:117-148`).
- `ACL_SELECT` on the parent (for indexes) or the relation itself is
  required [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:149-151`).
- Relation must have storage [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:154-159`).
- Block numbers validated against `nblocks` of the requested fork
  [verified-by-code] (`source/contrib/pg_prewarm/pg_prewarm.c:175-191`).
- `CHECK_FOR_INTERRUPTS()` per block in all three modes [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:210, 229, 265`).
- Prefetch mode errors out if `USE_PREFETCH` is undefined [verified-by-code]
  (`source/contrib/pg_prewarm/pg_prewarm.c:214-218`).

## Notable internals

- Read mode dumps into a static thread-local `PGIOAlignedBlock blockbuffer`
  (`source/contrib/pg_prewarm/pg_prewarm.c:45`) — safe because the
  function is not re-entrant and never yields a Datum that points into
  it.
- Buffer mode uses the read-stream API with `READ_STREAM_MAINTENANCE |
  READ_STREAM_FULL | READ_STREAM_USE_BATCHING` and `block_range_read_stream_cb`
  (`source/contrib/pg_prewarm/pg_prewarm.c:251-272`). Batch-mode safe
  because the callback takes no locks.
- For an index, `LockRelationOid(parent, AccessShareLock)` then
  `IndexGetRelation` is called *twice* — once to compute privOid pre-open,
  once post-open to detect a drop+reuse race that could change the parent
  table OID under us [from-comment lines 132-148].

## Trust-boundary / Phase D surface

1. **Permission check is at table level, not at fork.** Once `ACL_SELECT`
   on the parent passes, the caller can prewarm ANY fork (`MAIN_FORKNUM`,
   `INIT_FORKNUM`, `VISIBILITYMAP_FORKNUM`, `FSM_FORKNUM`). This is
   probably fine because fork contents are dependent on the table, but
   note that VM/FSM forks can be I/O-amplified independently this way.
   [ISSUE-defense-in-depth: pg_prewarm lets any SELECT-privileged user
   issue large prefetch/read I/O on all forks of a table including
   VM/FSM/INIT (nit)] (`source/contrib/pg_prewarm/pg_prewarm.c:149-167`).
2. **No rate limit on block range.** A user with SELECT on a multi-TB
   table can `pg_prewarm(..., 'read', 'main', 0, nblocks-1)` and drive
   the I/O subsystem hard. `read` mode bypasses shared_buffers but still
   issues `nblocks` smgrread calls. [ISSUE-resource: pg_prewarm has no
   rate limit; any SELECT-privileged user can force a full-relation
   synchronous read (maybe)]
   (`source/contrib/pg_prewarm/pg_prewarm.c:220-233`).
3. **`read` mode reads into a static `blockbuffer`.** Marked
   `PGIOAlignedBlock blockbuffer` at file scope. If pg_prewarm were
   ever to become re-entrant (e.g., a SECURITY DEFINER call from inside
   another), this would race. Not currently exploitable.
   [ISSUE-nit: static blockbuffer is not strictly per-call; works
   today because pg_prewarm is synchronous and non-yielding but
   fragile (nit)] (`source/contrib/pg_prewarm/pg_prewarm.c:45,230`).
4. The drop+reuse-race comment at lines 132-148 explicitly says "the
   worst case scenario … is that we'll check privileges on the index
   instead of its parent table, which isn't too terrible." [from-comment
   line 138]. [ISSUE-correctness: the documented edge case where
   privOid swap happens between get_rel_relkind and relation_open lets
   us check ACL_SELECT on a now-incorrect parent for one window — the
   re-check at line 141 catches it but it depends on IndexGetRelation
   being idempotent under the AccessShareLock taken at line 125 (maybe)]
   (`source/contrib/pg_prewarm/pg_prewarm.c:131-148`).

## Cross-refs

- `knowledge/files/contrib/pg_prewarm/autoprewarm.c.md` — the bgworker companion
- `knowledge/subsystems/storage-buffer.md` — read-stream / prefetch APIs
- `knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md` — counterpart that evicts

## Issues

1. [ISSUE-defense-in-depth: ACL_SELECT covers all forks (VM/FSM/INIT), not just MAIN (nit)] — `source/contrib/pg_prewarm/pg_prewarm.c:149-167`
2. [ISSUE-resource: no rate limit on block range; any SELECT user can force full-relation reads (maybe)] — `source/contrib/pg_prewarm/pg_prewarm.c:220-233`
3. [ISSUE-nit: static file-scope blockbuffer fragile if function ever becomes re-entrant (nit)] — `source/contrib/pg_prewarm/pg_prewarm.c:45,230`
4. [ISSUE-correctness: documented privOid swap race relies on IndexGetRelation being idempotent under AccessShareLock (maybe)] — `source/contrib/pg_prewarm/pg_prewarm.c:131-148`
