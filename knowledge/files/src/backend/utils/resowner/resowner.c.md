# `src/backend/utils/resowner/resowner.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1110
- **Source:** `source/src/backend/utils/resowner/resowner.c`

## Purpose

Query/transaction-lifespan resource bookkeeping. Each `ResourceOwner` records
pinned buffers, held locks, open relations, snapshots, AIO handles, etc., so
that on commit/abort everything gets released in the right phase + priority
order. [from-comment] (`resowner.c:1-9`)

## Mental model

- Two-tier storage per owner: a fixed array of `RESOWNER_ARRAY_SIZE = 32`
  most-recently-remembered items, plus a hash table for spillover.
  [from-comment] (`resowner.c:11-23`, `:73`)
- Locks bypass that storage entirely — each owner has its own `locks[]`
  cache of `MAX_RESOWNER_LOCKS = 15` `LOCALLOCK*` entries. If exceeded, the
  owner overflows and falls back on lockmgr's own table for bulk release.
  [from-comment] (`resowner.c:28-34`, `:97-107`)
- Three release phases run in order: `RESOURCE_RELEASE_BEFORE_LOCKS`,
  `RESOURCE_RELEASE_LOCKS`, `RESOURCE_RELEASE_AFTER_LOCKS`. Within a phase,
  items are sorted by `release_priority` and released from highest to
  lowest (qsort with reverse-order comparator). [verified-by-code]
  (`resowner.c:262-278`, `:725-797`)
- After `ResourceOwnerRelease` starts, `releasing=true` and no further
  `Remember`/`Forget` allowed; callbacks must be self-contained.
  [from-comment] (`resowner.c:689-696`)

## Spine

- `ResourceOwnerCreate` (`resowner.c:418`) — allocates in `TopMemoryContext`,
  links into parent's child list.
- `ResourceOwnerEnlarge` (`resowner.c:449`) — pre-reserves space. **Must be
  called before acquiring** the resource so the subsequent `Remember` can't
  OOM with a leaked external resource.
- `ResourceOwnerRemember` (`resowner.c:521`) / `ResourceOwnerForget`
  (`resowner.c:561`) — adds to array; on overflow array→hash migration via
  open-addressing.
- `ResourceOwnerRelease` → `...Internal` (`resowner.c:655`, `:675`) — recurses
  into children first, sorts on first invocation, then per-phase walks
  sorted array from end (since sort is reverse-priority).
- `ResourceOwnerSort` (`resowner.c:289`) — compacts hash, then qsorts. After
  sort the structures are no longer hash-shaped (linear scan only).
- `ResourceOwnerReleaseAllOfKind` (`resowner.c:815`) — targeted bulk release
  without sorting (sets `releasing` temporarily; cannot be re-entered).
- `ResourceOwnerNewParent` (`resowner.c:911`) — reparent (used by subxact
  commit to transfer ownership upward).
- `ResourceOwnerDelete` (`resowner.c:868`) — free the empty owner.

## Lock fast-path

- `ResourceOwnerRememberLock` (`resowner.c:1059`) appends to `locks[]` if
  `nlocks < MAX_RESOWNER_LOCKS`, else sets `nlocks = MAX+1` as overflow flag.
- `ResourceOwnerForgetLock` (`resowner.c:1079`) does linear scan; if
  overflowed, no-op (lockmgr's table is authoritative).
- During `RESOURCE_RELEASE_LOCKS` for a subtransaction: if not overflowed,
  pass `locks[]`/`nlocks` to `LockReassignCurrentOwner`/`LockReleaseCurrentOwner`
  for O(nlocks) handoff; if overflowed, the lockmgr walks its own table.
  [verified-by-code] (`resowner.c:774-788`)
- For top-level xact: bypass per-owner walk entirely, just call
  `ProcReleaseLocks` + `ReleasePredicateLocks` once at the top of recursion.
  (`resowner.c:752-755`)

## Release ordering invariant

- The qsort is **reverse-priority within phase**: comparator returns
  `pg_cmp_u32(rb->priority, ra->priority)` so highest priority sorts to the
  end; the release loop pops from end forward. [verified-by-code]
  (`resowner.c:272-273`, `:375-396`)
- This means resources with **larger** `release_priority` numbers get
  released **first**. `ResourceOwnerDesc.release_priority` is set per kind
  (e.g. `RELEASE_PRIO_BUFFER_PINS`, `RELEASE_PRIO_RELCACHE_REFS`) in their
  defining modules.
- During recursion, children release before parents — so subxact resources
  drain first. [verified-by-code] (`resowner.c:686-687`)
- The AIO handle dlist is drained separately inside
  `RESOURCE_RELEASE_BEFORE_LOCKS` after the generic array/hash walk.
  (`resowner.c:736-741`)

## Hash table mechanics

- Open-addressing, capacity = power of two, fill factor ≤ 0.75.
  Initial capacity `RESOWNER_HASH_INIT_SIZE = 64`. (`resowner.c:79-89`)
- Hash function `hash_resource_elem` (Datum value, kind pointer) →
  `hash_bytes_extended`.
- `RESOWNER_HASH_MAX_ITEMS(capacity) = Min(capacity - 32, capacity*3/4)` —
  the `- 32` ensures Sort can always migrate the entire array into the hash
  in one step. [from-comment] (`resowner.c:81-92`)

## Tag tally

`[verified-by-code]` 3 / `[from-comment]` 8

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
