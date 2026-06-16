# `src/backend/utils/activity/pgstat_shmem.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1191
- **Source:** `source/src/backend/utils/activity/pgstat_shmem.c`

The heart of the pgstat shared-memory storage layer (introduced in
PG15 to replace the old stats-collector file). Backed by a DSA area
(small bootstrap region in main shmem, then DSM segments as needed)
hosting a `dshash` keyed by `(kind, dboid, objid)`. Each backend
keeps a local `simplehash` of references to shared entries with a
refcount + generation protocol so dropped entries can be safely
freed only when the last referrer releases. [verified-by-code]
[from-comment]

## Shared-memory layout

- `PgStat_ShmemControl` (defined in `pgstat_internal.h`) at the head
  of the allocation, followed by 256 KiB raw DSA bootstrap, followed
  by per-kind fixed-amount blobs for custom stats kinds (line 142-154).
  [verified-by-code]
- `pgstat_dsa_init_size()` hardcodes 256 KiB (line 126). Comment:
  "256kB seems works well and is not disproportional compared to
  other constant sized shared memory allocations." Anything beyond
  this is allocated from DSM segments (or `min_dynamic_shared_memory`
  if configured). [from-comment]
- The dshash table is created **with the DSA size limited to the
  initial 256 KiB** so its initial buckets land in plain shmem
  rather than DSM. Then the size limit is lifted. Comment notes the
  XXX wish for `dshash_create_in_place()` (line 204-206). [verified-by-code]
  [from-comment] [ISSUE-stale-todo: XXX wishes for
  dshash_create_in_place (nit)]

## Per-entry state

- `PgStatShared_HashEntry { key; dsa_pointer body; pg_atomic_uint32
  refcount; pg_atomic_uint32 generation; bool dropped; }` (in header).
  `magic = 0xdeadbeef` written to the body, asserted on every access.
  [verified-by-code]
- **Refcount discipline:** Entry born with refcount=1 (the "not
  dropped" mark, line 327). Each backend acquiring a reference does
  `fetch_add_u32(refcount, 1)`. Dropping flips `dropped=true` and
  `sub_fetch_u32(refcount, 1)` — when this returns 0, the entry is
  safe to free. [verified-by-code]
- **Generation:** incremented on re-init (line 370). Backends with
  stale local refs detect the change in `pgstat_gc_entry_refs` and
  release their refs. [verified-by-code]

## API / entry points (selected)

- `StatsShmemRequest` / `StatsShmemInit` — postmaster-side
  bootstrap hooks. Init creates the DSA and dshash, pins both, then
  detaches (postmaster never accesses them again). [verified-by-code]
- `pgstat_attach_shmem(void)` / `pgstat_detach_shmem(void)` —
  per-backend init/cleanup. Attach pins the DSA mapping; detach
  releases all entry refs and detaches DSA. Note: line 290-295's
  comment about `dsa_release_in_place` after `dsa_detach` —
  `dsa_detach` on an in-place DSA doesn't decrement the refcount
  (no segment context was provided), so we must call it manually.
  [verified-by-code] [from-comment]
- `pgstat_init_entry(kind, shhashent)` — allocate the entry body
  from DSA (`DSA_ALLOC_NO_OOM`); returns NULL on allocation failure
  so caller can clean up the dshash entry. Initialises the body
  lock and bumps the per-kind atomic entry count if the kind
  enables `track_entry_count`. [verified-by-code]
- `pgstat_reinit_entry(kind, shhashent)` — re-use a previously
  dropped entry (refcount went to 0 and dropped=true, but freer
  raced with a new creator). Increments refcount + generation,
  flips dropped=false, zeros body. [verified-by-code] [from-comment]
- `pgstat_get_entry_ref(kind, dboid, objid, create, *created_entry)`
  — central lookup. Goes through the local cache first, then
  `dshash_find` (shared lock), then `dshash_find_or_insert` if
  `create`. Handles the race where another backend creates between
  find and insert (line 528-535). [verified-by-code]
- `pgstat_release_entry_ref(key, ref, discard_pending)` — release
  a local cache entry. On refcount→0, re-acquire the shared entry
  exclusively, double-check generation hasn't changed (a re-init
  could have happened), and call `pgstat_free_entry`. [verified-by-code]
- `pgstat_lock_entry(ref, nowait)` / `pgstat_lock_entry_shared(...)`
  / `pgstat_unlock_entry(ref)` — wrappers around the per-entry
  LWLock embedded in `PgStatShared_Common`. [verified-by-code]
- `pgstat_get_entry_ref_locked(...)` — find + lock; returns NULL on
  nowait failure. [verified-by-code]
- `pgstat_request_entry_refs_gc(void)` — bump
  `gc_request_count`. Each backend compares this to its local
  `pgStatSharedRefAge` periodically. [verified-by-code]
- `pgstat_gc_entry_refs(void)` — iterate local cache, release refs
  whose shared entries are dropped or whose generation no longer
  matches. Skips entries with `pending` data (can't gc while pending
  flush). [verified-by-code]
- `pgstat_drop_entry(kind, dboid, objid)` — flip `dropped=true` on
  the shared entry and try to free immediately; if other refs hold
  it, the freeing is deferred to whoever ends up at refcount 0.
  Special case: dropping a DATABASE entry drops all entries with
  that dboid. [verified-by-code]
- `pgstat_drop_database_and_contents(dboid)` — release this backend's
  refs to dboid entries first (avoids self-blocking), then iterate
  the dshash exclusively, marking matching entries dropped. Counts
  not-yet-freed entries and requests GC if any remain. [verified-by-code]
- `pgstat_drop_matching_entries(do_drop, match_data)` /
  `pgstat_drop_all_entries(void)` — bulk drop with optional
  predicate. [verified-by-code]
- `pgstat_reset_entry(kind, dboid, objid, ts)` /
  `pgstat_reset_matching_entries(do_reset, data, ts)` /
  `pgstat_reset_entries_of_kind(kind, ts)` — zero entry contents
  under exclusive entry-lock and call the kind's
  `reset_timestamp_cb` hook. [verified-by-code]

## Notable invariants / details

- **`magic = 0xdeadbeef`** sentinel on every `PgStatShared_Common` —
  asserted at refcount inc, release, locking. Cheap UAF guard.
  [verified-by-code]
- **Local cache (`pgStatEntryRefHash`)** uses simplehash with
  PGSTAT_ENTRY_REF_HASH_SIZE=128. Lives in two separate memory
  contexts (the hashtable, the ref entries) so memory accounting
  is split. [verified-by-code]
- **`pgstat_get_entry_ref_cached`** inserts a placeholder cache
  entry **before** taking the shared-stats refcount — comment
  (line 423-427) explains this avoids OOM-after-refcount-increment.
  [from-comment]
- **Drop-and-recreate race (replication slots):** comment (line
  583-590) explicitly calls out that replication-slot OIDs reuse
  is the canonical case requiring `pgstat_reinit_entry`. Tagged as
  "oid wraparound" being the other case. [from-comment]
- **`dropped` + refcount race:** when `pgstat_release_entry_ref`
  drops refcount to 0, it re-acquires the dshash exclusively and
  rechecks generation (line 661-667). If a concurrent re-init bumped
  generation, we abandon the free (the entry has live users again).
  [verified-by-code]
- **No leak on init failure:** `pgstat_init_entry` returning NULL
  triggers caller's `dshash_delete_entry` cleanup (line 545), then
  ERROR with OOM. [verified-by-code]
- **`pgstat_drop_database_and_contents` does the local-refs release
  outside the dshash partition lock** (comment line 962-965)
  intentionally — taking the partition lock around the local-cache
  iteration could deadlock. [from-comment]
- **`pgstat_drop_all_entries`** is invoked by stats-reset utilities;
  iterates with exclusive dshash lock. [verified-by-code]
- **`shared_stat_reset_contents` zeros entry data then calls
  per-kind `reset_timestamp_cb`** — entry kinds like database stats
  want their `stat_reset_timestamp` field NOT zeroed but bumped.
  [verified-by-code]
- **`pgstat_setup_memcxt`** lazily creates `pgStatSharedRefContext`
  and `pgStatEntryRefHashContext` under `TopMemoryContext`. Both
  use `ALLOCSET_SMALL_SIZES`. [verified-by-code]
- **`pgstat_drop_entry` on PGSTAT_KIND_DATABASE cascades** — the
  database entry's drop pulls all per-relation, per-function, etc.
  stats with the same dboid. Comment self-flags "XXX: Perhaps this
  should be done in a slightly more principled way?" (line 1039-1041).
  [from-comment] [ISSUE-stale-todo: ad-hoc DB-drop cascade (nit)]

## Potential issues

- File-line: pgstat_shmem.c:204-206. `XXX: It'd be nice if there
  were dshash_create_in_place()` — long-standing TODO. [ISSUE-stale-todo:
  dshash_create_in_place wish (nit)]
- File-line: pgstat_shmem.c:1039-1041. `XXX: Perhaps this should be
  done in a slightly more principled way?` — DB-drop cascade. [ISSUE-stale-todo:
  ad-hoc cascade (nit)]
- File-line: pgstat_shmem.c:625. `elog(ERROR, "releasing ref with
  pending data")` — if a code path tries to release a ref while
  still holding unflushed pending stats, we throw. Means the order
  of operations in the calling code is load-bearing. [ISSUE-undocumented-invariant:
  release-vs-pending ordering contract (maybe)]
- File-line: pgstat_shmem.c:680-685. `pgstat_entry_ref_hash_delete`
  is called AFTER the refcount decrement and possible free of the
  shared entry. If the simplehash delete fails (`elog(ERROR, ...)`),
  we've already mutated the shared refcount but failed to clean up
  the local hash — partial state. In practice the delete should
  never fail given the entry was just looked up. [ISSUE-correctness:
  partial-failure path on cache-delete (nit)]
- File-line: pgstat_shmem.c:921-927. The "trying to drop already
  dropped" elog dumps full key + refcount + generation — useful
  for debug but exposes that internal kinds/dboids/objids to logs.
  Non-issue (server log is owner-only). [ISSUE-style: detailed elog
  for forensic debug (nit)]
- File-line: pgstat_shmem.c:548-552. `errdetail` includes `kind`,
  `dboid`, `objid` in plain text — fine, but the OOM here would
  imply DSA exhaustion under heavy concurrent stats-entry creation
  (e.g. cron-scheduled per-relation operations on millions of
  relations). [ISSUE-undocumented-invariant: DSA OOM under
  high-cardinality stats kinds (maybe)]
- File-line: pgstat_shmem.c:1124. `pgstat_reset_entry` silently
  returns on `!entry_ref || dropped` — a user calling pg_stat_reset_*
  on a vanished stat gets no error. Probably intentional (idempotent
  reset) but undocumented in this file. [ISSUE-undocumented-invariant:
  silent no-op on missing entry (nit)]
- File-line: pgstat_shmem.c:1156-1163. `pgstat_reset_matching_entries`
  iterates with **shared** dshash lock (line 1144) but takes
  **exclusive** body lock on each match. Safe: the dshash shared
  lock only protects the index, the body lock protects content.
  [verified-by-code]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new `pg_stat_*` view](../../../../../scenarios/add-new-pg-stat-view.md)

<!-- scenarios:auto:end -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->
