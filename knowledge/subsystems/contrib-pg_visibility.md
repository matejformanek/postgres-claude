# contrib-pg_visibility (visibility-map inspector + corruption check)

- **Source path:** `source/contrib/pg_visibility/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `pg_visibility.control`)
- **Trusted:** no (superuser install + per-function grants)

## 1. Purpose

Expose the per-relation **visibility map (VM) fork** to SQL and
provide two correctness probes — `pg_check_frozen` and
`pg_check_visible` — that scan the heap and report TIDs whose
visibility / freeze state contradicts what the VM advertises.
Designed for `VACUUM` debugging, post-incident audit, and
corruption hunts (the `pg_check_*` family is the canonical first
probe when "VACUUM ran but a row still looks live" symptoms
appear).

## 2. Mental model

- **The VM has 2 bits per page.** `VISIBILITYMAP_ALL_VISIBLE` and
  `VISIBILITYMAP_ALL_FROZEN`. The extension surfaces them per-block
  via `visibilitymap_get_status()`
  [verified-by-code `pg_visibility.c:107`].
- **Three lookup granularities.**
  - **One block**: `pg_visibility_map(rel, blkno)` (+ optional
    page-PD bits via `pg_visibility(rel, blkno)`)
    [verified-by-code `pg_visibility.c:83-116`].
  - **Whole relation SRF**: `pg_visibility_map(rel)` /
    `pg_visibility(rel)` — walks every block.
  - **Aggregate summary**: `pg_visibility_map_summary(rel)` —
    counts of all-visible / all-frozen blocks.
- **Corruption checks compare VM to heap.** `pg_check_frozen` scans
  pages the VM claims are all-frozen and reports any tuple whose
  xmin / xmax states say otherwise. `pg_check_visible` does the
  analogous job for all-visible.

## 3. The corruption-check flow

`collect_corrupt_items()` is the workhorse
[verified-by-code via `pg_visibility.c:69-73`]:

1. Open the heap with `AccessShareLock`.
2. Get an `OldestXmin` snapshot via `GetOldestNonRemovableTransactionId`
   (the same horizon that VACUUM uses for freeze decisions).
3. For each block the VM claims all-visible (or all-frozen),
   stream the heap page (`read_stream_*` API, the
   `collect_corrupt_items_read_stream_private` state in
   `pg_visibility.c:48-56`).
4. For each tuple on the page, call `tuple_all_visible()` /
   freeze-checks; if the tuple's actual state contradicts the VM
   bit, record the TID via `record_corrupt_item()`.
5. Return a set of `tid` rows. Empty result = VM and heap agree.

The use of `read_stream_*` (rather than direct `ReadBuffer` loops)
means the scan benefits from prefetching but is also subject to
the same lock-acquire semantics as a regular seq scan
[verified-by-code `pg_visibility.c:24`].

## 4. SQL surface

| Function | Behavior |
|---|---|
| `pg_visibility_map(rel, blkno)` | VM bits for one block (all_visible, all_frozen) |
| `pg_visibility(rel, blkno)` | VM bits + PD_ALL_VISIBLE flag on the page |
| `pg_visibility_map(rel)` | SRF: VM bits per block |
| `pg_visibility(rel)` | SRF: VM bits + PD flag per block |
| `pg_visibility_map_summary(rel)` | One row: counts of all-visible / all-frozen blocks |
| `pg_check_frozen(rel)` | SRF of TIDs that violate the all-frozen bit |
| `pg_check_visible(rel)` | SRF of TIDs that violate the all-visible bit |
| `pg_truncate_visibility_map(rel)` | Truncates VM fork to length 0 (recovery from corrupt VM) |

All registered in `pg_visibility.c:58-65`.

## 5. Caution: `pg_truncate_visibility_map`

This function unlinks the VM fork's smgr extent and emits a
`SMGR_TRUNCATE` xlog record. **It does NOT scrub the heap** — the
next `VACUUM` will reconstruct the VM, but until then queries that
rely on index-only scans backed by VM lookups will see degraded
performance (every visited tuple must re-check live status against
the snapshot).

The intended use: a `pg_check_frozen` run reported violations, you
suspect VM-fork corruption (not heap corruption), you truncate and
let `VACUUM` rebuild. If the heap is what's corrupted, truncating
the VM is futile; rebuild the table.

## 6. Relkind gating

`check_relation_relkind()` [verified-by-code `pg_visibility.c:74`]
rejects views, sequences, foreign tables, and other relkinds that
don't have a VM fork. Only `r` (table), `m` (matview), and `t`
(toast) are accepted. Index relations have a VM fork *space* but
the extension still rejects them — index VMs are managed
differently.

## 7. Snapshot semantics

`pg_check_frozen` / `pg_check_visible` use **`OldestXmin`-relative
visibility**, not the caller's transaction snapshot. The aim is to
catch tuples that look invisible to the global oldest snapshot but
are advertised as visible/frozen in the VM. Running these in a
serializable transaction does not change the answer; the snapshot
used internally is global, not the caller's MVCC snapshot.

## 8. Production-use guidance

- **Acceptable on running systems** — `AccessShareLock` on the heap
  + read-only on the VM fork; concurrent VACUUM is fine.
- **Cost is O(visible-blocks)** for `pg_check_visible` — on a
  freshly-vacuumed multi-TB table that's a full scan. Schedule
  during low load.
- **`pg_check_*` returns 0 rows** when the table is healthy. Non-empty
  results are a corruption indicator — investigate before re-VACUUM.
- **Don't combine with concurrent `VACUUM FREEZE`** — the answer
  may include tuples that VACUUM is about to fix. Run after VACUUM,
  not during.

## 9. Invariants

- **[INV-1]** `pg_visibility_map(rel, MaxBlockNumber+1)` returns
  ERROR; pages past the VM extent return zeros silently
  [from-comment `pg_visibility.c:78-82`].
- **[INV-2]** Only `r`, `m`, `t` relkinds are accepted; others
  ERROR.
- **[INV-3]** `pg_check_frozen` snapshot is `OldestXmin`-global,
  not the caller's MVCC snapshot.
- **[INV-4]** `pg_truncate_visibility_map` requires the relation
  to be writable (otherwise SMGR rejects); does NOT modify heap.

## 10. Useful greps

- All entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/pg_visibility/pg_visibility.c`
- Read-stream usage:
  `grep -n 'read_stream' source/contrib/pg_visibility/pg_visibility.c`
- Corruption check:
  `grep -n 'collect_corrupt_items\|tuple_all_visible' source/contrib/pg_visibility/pg_visibility.c`

## 11. Cross-references

- `knowledge/subsystems/access-heap.md` — the heap AM, freeze
  semantics, and `HeapTupleSatisfiesVacuum`.
- `knowledge/idioms/visibility-map-update.md` — the write side of
  the VM bits this extension reads.
- `.claude/skills/debugging/SKILL.md` — `pg_check_frozen` /
  `pg_check_visible` are documented as the first probes for "VACUUM
  ran but a tuple looks live" symptoms.
- `source/src/backend/access/heap/visibilitymap.c` — the VM
  implementation. `visibilitymap_get_status` is the read primitive
  this extension wraps.
- `source/contrib/pg_visibility/pg_visibility.c` — implementation.
