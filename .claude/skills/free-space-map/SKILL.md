---
name: free-space-map
description: PostgreSQL's Free Space Map (FSM) — the tree-of-pages that tracks per-heap-page free space so `INSERT` / `COPY` / `heap_multi_insert` can find a page with room without scanning the whole relation. Covers `src/backend/storage/freespace/` (`freespace.c` + `fsmpage.c` + `indexfsm.c`), the tree layout (leaf-page nodes + 2 upper levels), category encoding (bucketed free-byte counts), the FSM lock discipline, VACUUM's post-scan `FreeSpaceMapVacuum`, and index FSM's simpler use case. Skip when the ask is about visibility map (VM — sibling but different subsystem) or about `pg_freespacemap` contrib module (that's the SQL introspection wrapper).
when_to_load: Understand or debug FSM behavior; investigate why INSERT is not reusing free space; touch VACUUM's FSM update path; extend the FSM category encoding; work with index FSM (btree page-recycling); add a new FSM consumer.
companion_skills:
  - vacuum-autovacuum
  - locking
---

# free-space-map — where INSERT finds room

The Free Space Map tracks approximate free space per page in a relation, so INSERT and other appenders can find a target page without scanning. It's a **fork** of the relation (like the visibility map — a separate file at `<relfilenumber>_fsm`), organized as a tree over the heap's page numbers.

The design tradeoff: exact byte-level accounting would require WAL-logging every space change and dominate write traffic. Instead, FSM stores a small **category** per heap page (5 bits, 32 buckets) and updates it lazily — not WAL-logged in the hot path — with periodic reconciliation by VACUUM.

## The file map

| File | Lines | Role |
|---|---:|---|
| `freespace.c` | ~870 | Main API: `RecordAndGetPageWithFreeSpace`, `GetPageWithFreeSpace`, `RecordPageWithFreeSpace`, `FreeSpaceMapVacuum{Range}`. Tree traversal + descent. |
| `fsmpage.c` | ~430 | Per-FSM-page operations. Each FSM page is a binary tree; `fsm_search_avail`, `fsm_set_and_search`, path navigation within a page. |
| `indexfsm.c` | ~55 | The 2-function shim for indexes. Indexes reuse the FSM machinery but only for "is this page reusable?" — the category is 0/nonzero. |

The README in `src/backend/storage/freespace/` has an ASCII diagram of the tree layout — read it before touching FSM code. It's the shortest path to understanding the layout.

## The 3-level tree

FSM's `<relfilenumber>_fsm` file contains FSM PAGES (not heap pages). Each FSM page holds a **binary tree of 4096 slots**, packed. Slots at the bottom level correspond to heap pages (one FSM slot ~ one heap page). Slots higher up hold **maximums of their children**.

Traversal to find a heap page with N bytes free:

1. Start at the FSM tree root.
2. At each level: read the root slot's value (which is the max in its subtree). If < N, this subtree can't help.
3. Otherwise descend into the left or right child (whichever has the max).
4. Eventually reach a leaf slot → return the heap block number.

Insert of new free-space info:

1. Update the leaf slot for the heap page.
2. If the leaf slot changed, propagate up: parent's slot = max(children).
3. If parent changed, keep propagating.
4. Stop when a parent's value doesn't change.

## The category encoding

Free space is bucketed into **32 categories** (5 bits per slot). Category 0 = 0 bytes free. Category 31 = at least 31 × (BLCKSZ / 32) = ~256 bytes buckets. See `MaxFSMRequestSize` in `freespace.h`.

Consequence: FSM tells you "at least category N free" but the actual number could be higher. Callers that need EXACT free must double-check the page after locking it. `RecordAndGetPageWithFreeSpace` also encapsulates the "get + record actual" round-trip.

## The lock discipline

FSM pages have **their own lock protocol**, DIFFERENT from heap pages:

- `RelationExtensionLock` (heavyweight lock) — held only while extending a relation (adding a new page). NOT during FSM navigation.
- **FSM page pin + share/exclusive** — normal buffer lock semantics, but FSM concurrent readers/writers are very tolerant of stale data because the encoded value is approximate anyway.
- **No WAL logging in the hot path** — `RecordPageWithFreeSpace` is a hint. It's OK if a crash loses the FSM update; VACUUM will reconcile.
- **VACUUM's FSM pass IS logged** — `FreeSpaceMapVacuum` after a heap scan writes canonical values that are WAL'd.

This asymmetry is by design: hot-path INSERTs don't slow down for FSM updates; recovery re-derives from the vacuum-produced records.

## The public API surface (freespace.c)

- `GetPageWithFreeSpace(rel, min_space)` — read-only: find a page with at least `min_space` bytes free. Returns block# or `InvalidBlockNumber`.
- `RecordAndGetPageWithFreeSpace(rel, oldPage, oldFreeSpace, min_space)` — combined: record that `oldPage` has `oldFreeSpace` bytes free, AND find a new candidate. Common pattern: after failing to fit a tuple, tell FSM the actual remaining free space + get another candidate.
- `RecordPageWithFreeSpace(rel, page, spaceAvail)` — pure record; no lookup.
- `XLogRecordPageWithFreeSpace(reln, page, spaceAvail)` — write a WAL record about a page's free space (used by heap_multi_insert for post-COPY reconciliation).
- `FreeSpaceMapVacuumRange(rel, start, end)` — canonical reconciliation over a page range. Called by VACUUM.
- `FreeSpaceMapVacuum(rel)` — same for the whole relation.

## When FSM lies (and how)

The category-encoded value can drift below reality:

- INSERTS that don't fit: caller records the ACTUAL remaining space, so this converges.
- DELETEs that don't record: FSM stays stale (says "less free" than reality). VACUUM fixes.
- VACUUM's post-scan pass writes canonical values.

The category-encoded value can also drift ABOVE reality:

- Concurrent INSERT into the "found" page fills it before you write. Caller must re-check after buffer lock.

**This is why `RelationGetBufferForTuple` (in `access/heap/hio.c`) has a retry loop** — it may consult FSM 2-3 times before either committing to a page or extending the relation.

## Index FSM

Indexes track "empty pages that can be recycled" — a bit for each page. Uses the same FSM machinery but only cares about category 0 (fully-empty) vs nonzero. Consumed by btree page-splits (which drop-and-recycle) and by btree page-deletes.

Files: `indexfsm.c` (the shim), plus per-index-AM users:
- `access/nbtree/nbtxlog.c` + `nbtree.c` — records + reads pages.
- `access/hash/hashovfl.c` — hash overflow page recycling (uses its own bitmap for MUCH tighter tracking, not FSM).

## Common patch shapes

### Add a new FSM consumer

- Call `GetPageWithFreeSpace` in the search phase.
- After committing space use, call `RecordPageWithFreeSpace` with the remaining.
- Add a WAL log via `XLogRecordPageWithFreeSpace` if reliability matters for the recovery-side FSM state.
- Test with `pg_freespacemap` (contrib) to verify the FSM state after your workload.

### Debug "INSERT is extending the relation instead of reusing space"

- `pg_freespacemap.pg_freespace(rel::regclass, blkno)` — see the encoded category.
- If category=0 for pages that clearly have space: VACUUM hasn't reconciled since the last delete. Run VACUUM.
- If categories look right but INSERT still extends: your row's `min_space` request may be larger than any single-page category can encode. Check `MaxFSMRequestSize`.

### Change the category encoding (rare, dangerous)

Would touch `fsm_get_max_avail`, `fsm_free_bits_to_avail`, all callers relying on bucket size, plus on-disk file format (bump `FSM_PAGE_MAGIC`). Almost certainly requires hackers-list discussion.

## Pitfalls

- **FSM is NOT crash-safe by default** — hot-path updates are unlogged. This is intentional; recovery uses VACUUM's post-scan pass. Don't add "just log it" without hackers discussion.
- **FSM can point at now-full pages** — the "found" page may be full by the time you lock it. Every consumer must re-check under buffer lock.
- **Concurrent extensions can race with FSM traversal** — a new page appears; FSM tree may not know about it yet. `RelationGetBufferForTuple` handles this with retry.
- **VACUUM's FSM pass is expensive on huge tables** — it walks the whole tree. In PG 17+ it's incremental; in older releases it always did the whole relation.
- **`MaxFSMRequestSize`** — you can only ask for up to this much space; larger requests always miss FSM and extend the relation. Something like ~BLCKSZ/4.
- **Small relations skip FSM** — if the relation is under `HEAP_FSM_CREATION_THRESHOLD` pages, no FSM fork is created (small tables just do sequential-fit). This means the first ~10 pages don't get FSM tracking.
- **Index FSM has different semantics** — category 0 vs nonzero, no bucket ladder. Don't code as if index FSM is heap FSM.
- **FSM lives per-fork per-relation** — main fork FSM (for INSERT). Toast tables have their own FSM. Indexes have their own FSM. Don't cross-reference.

## Related corpus

- **Idiom**: no direct FSM idiom (candidate for future authoring). The FSM interacts with `heap-tuple-freeze` (VACUUM's post-heap-scan FSM pass) and `vacuum-two-pass-heap` (the orchestration).
- **File docs**: `knowledge/files/src/backend/storage/freespace/freespace.c.md`, `fsmpage.c.md`, `indexfsm.c.md`.
- **Subsystems**: `storage-buffer` (FSM pages are buffered), `access-heap` (`hio.c` is the primary consumer via `RelationGetBufferForTuple`), `vacuum-autovacuum` (the reconciliation driver).
- **README**: `source/src/backend/storage/freespace/README` — the definitive design doc; shorter than this skill and worth reading before deep work.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/storage/freespace/freespace.c
python3 scripts/corpus-chain.py --file src/backend/access/heap/hio.c
```

Second one shows the primary consumer — RelationGetBufferForTuple + its retry loop.

## Boundary

**Use this skill** for `src/backend/storage/freespace/` + FSM consumers.

**Don't use** for:
- **Visibility Map** — sibling machinery in `storage/freespace/`? NO — VM is in `access/heap/visibilitymap.c`. Different subsystem, different design.
- **`pg_freespacemap` contrib** — SQL introspection wrapper over FSM; small contrib module, use its own docs if the ask is about the SQL interface.
- **Btree page-deletion tracking** — uses index FSM but the recycling logic is in `access/nbtree/`; skill lives there.
- **Hash overflow-page management** — uses its own bitmap, NOT FSM. See `contrib-hash` or the hash-am subsystem.
