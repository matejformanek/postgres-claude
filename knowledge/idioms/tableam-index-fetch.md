# Table AM index-fetch — TID → tuple resolution

After an index-scan returns a TID (block + offset), the
**table AM's `index_fetch_tuple` callback** is responsible for
fetching the actual tuple, traversing HOT chains, applying
visibility, and returning a slot. Distinct from
`tuple_fetch_row_version` (single-tuple lookup), this callback
preserves cross-call state for **HOT chain follow** — a single
index TID can resolve to multiple live tuple versions.

Anchors:
- `source/src/include/access/tableam.h:1243-1310` —
  index_fetch_tuple commentary [verified-by-code]
- `source/src/include/access/tableam.h:509-518` —
  tuple_fetch_row_version (the simpler sibling)
  [verified-by-code]
- `source/src/backend/access/heap/heapam_handler.c:2695` —
  heapam's tuple_fetch_row_version assignment
  [verified-by-code]
- `knowledge/idioms/bitmap-heap-scan-flow.md` — companion
- `knowledge/idioms/heaptuple-update-chain.md` — companion
  (HOT-chain semantics)
- `.claude/skills/access-method-apis/SKILL.md` — companion

## The two callbacks

[verified-by-code `tableam.h:509-518, 1243-1310`]

```c
/* simple: fetch one specific version */
bool (*tuple_fetch_row_version) (Relation rel,
                                 ItemPointer tid,
                                 Snapshot snapshot,
                                 TupleTableSlot *slot);

/* HOT-aware: walk a chain returning multiple versions */
bool (*index_fetch_tuple) (IndexFetchTableData *scan,
                           ItemPointer tid,
                           Snapshot snapshot,
                           TupleTableSlot *slot,
                           bool *call_again,
                           bool *all_dead);
```

The difference: `index_fetch_tuple` maintains state across
calls (in `IndexFetchTableData`) so it can return the next
HOT-chain member on each call without re-traversing from the
TID. The executor signals "fetch next" via `*call_again = true`.

## The HOT-chain follow contract

[from-comment `tableam.h:1287-1300`]

> *call_again needs to be false on the first call to
> table_index_fetch_tuple(...) on a particular TID, and
> will be set to true, signaling that table_index_fetch_tuple()
> should be called again to fetch additional tuples from the
> same TID...

For a HOT-chain root TID:
1. First call: `*call_again = false`. Return the live version
   (if any).
2. If the chain has more HOT-updated versions and the caller's
   snapshot might see them, set `*call_again = true`.
3. Caller invokes again with same TID; AM returns next version.
4. Eventually `*call_again = false`; chain exhausted.

Heap AM uses this for **index-only scan in MVCC contexts** where
multiple HOT-chain versions are simultaneously visible to
different snapshots.

## *all_dead — the index-cleanup hint

```c
bool *all_dead;
```

Set to `true` if the entire HOT chain is now dead (no snapshot
can see any version). The index AM can use this to physically
remove the index pointer to this TID (it's pointing at dead
data).

False or NULL means "at least one version is potentially live";
the index pointer must stay until VACUUM proves it dead.

## IndexFetchTableData — the per-scan state

```c
typedef struct IndexFetchTableData
{
    Relation rel;
} IndexFetchTableData;
```

Base struct (heap AM extends it with `IndexFetchHeapData` adding
buffer pin + last-block info). Created by
`table_index_fetch_begin`, populated through the scan, freed by
`table_index_fetch_end`.

Holds:
- The buffer pin for the page containing the TID (so the page
  doesn't change mid-chain).
- Last block scanned (for prefetch heuristics).
- HOT-chain position (in heap-AM's extended struct).

## Distinguishing from tuple_fetch_row_version

[from-comment `tableam.h:1297-1300`]

> The difference between this function and
> table_tuple_fetch_row_version() is that this function
> follows update chains stored at the same table block of the
> index entry (like heap's HOT).

When to use which:
- **`tuple_fetch_row_version`** — single TID lookup, no chain
  follow. Used by RI checks, EvalPlanQual, foreign-key
  enforcement.
- **`index_fetch_tuple`** — index-scan path; HOT-aware.

## Visibility, locking, and the buffer pin

The fetch holds a buffer pin (not a lock) on the page while
inspecting the chain. Concurrent updates can still pin / lock /
modify other items on the page. The pin only guarantees the
page isn't moved (e.g., reorganized by VACUUM).

After visibility test:
- If visible: return slot, possibly with `*call_again = true`.
- If dead: continue to next HOT chain member.
- If RECENTLY_DEAD per snapshot's xmin horizon: not visible to
  THIS snapshot, but other snapshots might see it; chain
  continues.

## Custom table AMs

[per `tableam-vtable-lifecycle`]

A custom table AM (columnar, in-memory, FDW-wrapping) typically
implements:
- A trivial `index_fetch_tuple` that doesn't HOT-chain (single
  call, then `*call_again = false`).
- The state struct is just `IndexFetchTableData` (no extension).

HOT semantics are heap-specific. Columnar AMs may have
equivalent "version chain" concepts but expose them differently.

## The Index AM ↔ Table AM handshake

```
IndexAM amgettuple → TID
                          ↓
table_index_fetch_tuple(scan, TID, snap, slot, &again, &dead)
                          ↓
TupleTableSlot ← (filled with tuple from heap/columnar/...)
```

This call is the bridge between the two AMs. The IndexAM doesn't
know how the tuple is stored; the TableAM doesn't know what
index gave it the TID. The contract is the TID + snapshot.

## Common review-time concerns

- **call_again semantics matter** — single-call AMs MUST set it
  false; multi-call AMs MUST honor it.
- **Buffer pin held across calls** — release in
  `table_index_fetch_reset` / `_end`.
- **all_dead is a hint** for index VACUUM; setting false is
  always safe.
- **Snapshot is the visibility input** — don't ignore it.
- **HOT-chain follow is heap-only** — custom AMs don't have to
  implement it.
- **IndexOnlyScan uses VM** — bypasses `index_fetch_tuple`
  when all-visible.

## Invariants

- **[INV-1]** `*call_again = false` on first call; AM may set
  true to request more.
- **[INV-2]** `*all_dead = true` only when the entire chain is
  unreachable.
- **[INV-3]** Buffer pin held across multi-call HOT walk.
- **[INV-4]** Snapshot is the visibility decider.
- **[INV-5]** Custom AMs may implement as trivial single-call;
  HOT semantics are heap-specific.

## Useful greps

- The callback definition:
  `grep -n 'index_fetch_tuple\|tuple_fetch_row_version' source/src/include/access/tableam.h | head -10`
- Heap AM impl:
  `grep -n 'heapam_index_fetch_tuple\|heap_hot_search' source/src/backend/access/heap/heapam_handler.c | head -10`
- Executor callers:
  `grep -RIn 'table_index_fetch_tuple' source/src/backend/executor | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam_handler.c`](../files/src/backend/access/heap/heapam_handler.c.md) | 2695 | heapam's tuple_fetch_row_version assignment |
| [`src/include/access/tableam.h`](../files/src/include/access/tableam.md) | 509 | tuple_fetch_row_version (the simpler sibling) |
| [`src/include/access/tableam.h`](../files/src/include/access/tableam.md) | 1243 | index_fetch_tuple commentary |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-table-am`](../scenarios/add-new-table-am.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/bitmap-heap-scan-flow.md` — bitmap scan
  uses `table_scan_bitmap_next_tuple` (a different AM hook).
- `knowledge/idioms/heaptuple-update-chain.md` — HOT-chain
  semantics this function follows.
- `knowledge/idioms/index-only-scan-vm-check.md` —
  IndexOnlyScan bypasses this via VM.
- `knowledge/idioms/tableam-vtable-lifecycle.md` —
  IndexFetchTableData lifecycle.
- `knowledge/data-structures/tupletableslot.md` — output
  slot.
- `knowledge/subsystems/access-heap.md` — heap AM impl.
- `.claude/skills/access-method-apis/SKILL.md` — companion.
- `source/src/include/access/tableam.h:1243` — full
  contract.
- `source/src/backend/access/heap/heapam_handler.c:2695` —
  heap AM assignment.
