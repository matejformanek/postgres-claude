---
path: src/backend/access/rmgrdesc/heapdesc.c
anchor_sha: 4b0bf0788b0
loc: 475
depth: deep
---

# heapdesc.c

- **Source path:** `source/src/backend/access/rmgrdesc/heapdesc.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 475

## Purpose

rmgr descriptor routines for the two heap resource managers
(`RM_HEAP_ID` / `RM_HEAP2_ID`, `access/heap/heapam.c`): render
insert/delete/update/lock/truncate/inplace and the heap2
prune+freeze / multi-insert / lock-updated / new-cid records. Also the
**canonical home of `heap_xlog_deserialize_prune_and_freeze`** — the
shared deserializer for the packed arrays inside an
`XLOG_HEAP2_PRUNE_*` record, used by both `heap2_redo` and
`heap2_desc` (and thus `pg_waldump`). [from-comment, heapdesc.c:1-21, 97-104]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `heap_xlog_deserialize_prune_and_freeze(cursor, flags, …)` | `heapdesc.c:105` | split a prune/freeze record's block data into freeze-plans + redirected/dead/unused offset arrays |
| `heap_desc(buf, record)` | `heapdesc.c:184` | render an `RM_HEAP_ID` record |
| `heap2_desc(buf, record)` | `heapdesc.c:264` | render an `RM_HEAP2_ID` record |
| `heap_identify(info)` / `heap2_identify(info)` | `heapdesc.c:396,441` | opcode → name |

## Internal landmarks

- **`heap_xlog_deserialize_prune_and_freeze` (heapdesc.c:105)** is the
  load-bearing function. A prune/freeze record's block-0 data is a
  flag-gated concatenation: `xlhp_freeze_plans` (if
  `XLHP_HAS_FREEZE_PLANS`), then `xlhp_prune_items` for redirections
  (`XLHP_HAS_REDIRECTIONS`), dead items (`XLHP_HAS_DEAD_ITEMS`), and
  now-unused items (`XLHP_HAS_NOW_UNUSED_ITEMS`), with the freeze
  offsets trailing. Each present section asserts `> 0`. The cursor math
  here is the definitive spec of that record's layout.
- **`infobits_desc` (heapdesc.c:26)** decodes the `XLHL_*` xmax info
  bits (IS_MULTI / LOCK_ONLY / EXCL_LOCK / KEYSHR_LOCK / KEYS_UPDATED)
  — the heap-tuple locking flags that show up in delete/update/lock
  records.
- **`plan_elem_desc` (heapdesc.c:76)** prints one freeze plan
  (`xmax`, infomask/infomask2, ntuples) and walks the parallel
  `frz_offsets` array via the `data` back-channel of `array_desc`.

## Invariants & gotchas

- **Prune records come in three flavors that share one decoder**:
  `XLOG_HEAP2_PRUNE_ON_ACCESS` (opportunistic, on SELECT),
  `_PRUNE_VACUUM_SCAN`, `_PRUNE_VACUUM_CLEANUP` (heapdesc.c:271-273).
  The `XLHP_HAS_CONFLICT_HORIZON` flag adds a trailing
  `snapshotConflictHorizon` xid used for standby conflict resolution
  (heapdesc.c:277-285).
- **`XLHP_IS_CATALOG_REL`** in a prune record (heapdesc.c:287) is the
  hot-standby catalog-conflict signal — catalog vs non-catalog matters
  for when a standby must cancel queries.
- **VM bits are reconstructed, not stored verbatim** — a prune that set
  all-visible (`XLHP_VM_ALL_VISIBLE`) re-derives the
  `VISIBILITYMAP_ALL_VISIBLE [| ALL_FROZEN]` byte for display
  (heapdesc.c:290-297); same in multi-insert with
  `XLH_INSERT_ALL_FROZEN_SET` (heapdesc.c:360-363).
- **`heap_identify` keys on opcode *combined with* `XLOG_HEAP_INIT_PAGE`**
  (heapdesc.c:406, 415, 421) — INSERT vs INSERT+INIT are distinct
  identities because the init-page variant overwrites rather than
  appends; don't mask off the init bit before identifying.
- **`heap2_desc` reads block data only `if XLogRecHasBlockData(...,0)`**
  (heapdesc.c:299, 365) — a prune/multi-insert whose page was a full
  FPI carries no separate block data, so the arrays are absent; the
  decoder must not be called unconditionally.

## Cross-refs

- Record structs + `XLHP_*` / `XLHL_*` / `XLH_*` flags:
  `src/include/access/heapam_xlog.h`,
  `src/include/access/visibilitymapdefs.h`.
- Backend redo: `heapam.c::heap_redo` / `heap2_redo` (shares the
  deserializer).
- Array printer: `rmgrdesc_utils.c.md`.
- Heap subsystem: `knowledge/subsystems/access-heap.md`;
  tuple layout `knowledge/data-structures/heap-tuple-layout.md`.

## Tally

`[verified-by-code]=6 [from-comment]=2 [inferred]=0`
