# snapshot.h

- **Source path:** `source/src/include/utils/snapshot.h`
- **Lines:** 212
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `utils/snapmgr.h`, `backend/utils/time/snapmgr.c`, `backend/access/heap/heapam_visibility.c`

## Purpose

Canonical definition of `SnapshotData` and the `SnapshotType` enum that drives the visibility dispatcher (`HeapTupleSatisfiesVisibility` in heapam_visibility.c:1732). The 7 snapshot types (`MVCC`, `SELF`, `ANY`, `TOAST`, `DIRTY`, `HISTORIC_MVCC`, `NON_VACUUMABLE`) capture every visibility regime PG knows about. [from-comment, snapshot.h:19-30]

## Top-of-file comment (verbatim)

> "We use SnapshotData structures to represent both 'regular' (MVCC) snapshots and 'special' snapshots that have non-MVCC semantics. The specific semantics of a snapshot are encoded by its type. ... The reason the snapshot type rather than a callback as it used to be is that that allows to use the same snapshot for different table AMs without having one callback per AM." [from-comment, snapshot.h:20-30]

## Snapshot types (the enum, with semantics from header comments)

- `SNAPSHOT_MVCC` (0): visible iff valid for given MVCC snapshot — committed-at-snapshot-time + own previous commands, excluding own current command and concurrent xacts. [from-comment, snapshot.h:33-46]
- `SNAPSHOT_SELF`: all committed xacts as of *now* + own previous commands + own current command; excludes concurrent in-progress. [from-comment, snapshot.h:48-61]
- `SNAPSHOT_ANY`: always visible. Used by bootstrap/REINDEX/etc. [from-comment, snapshot.h:62-65]
- `SNAPSHOT_TOAST`: visible iff valid as a TOAST row. [from-comment, snapshot.h:67-70]
- `SNAPSHOT_DIRTY`: like SELF but also includes in-progress xacts; the struct is used as an *output* arg to return concurrent xact info (`xmin`, `xmax`, `speculativeToken`). Use `InitDirtySnapshot()` macro. [from-comment, snapshot.h:72-96]
- `SNAPSHOT_HISTORIC_MVCC`: MVCC rules but used during logical decoding to see catalog state at a particular xid. [from-comment, snapshot.h:101-104]
- `SNAPSHOT_NON_VACUUMABLE`: visible iff *some* xact might still see it (i.e. not vacuumable). Requires `vistest` set via `InitNonVacuumableSnapshot(snap, vistestp)`. [from-comment, snapshot.h:107-114]

## SnapshotData fields (the layout)

- `snapshot_type` — discriminator.
- `xmin`, `xmax` — `xid < xmin` visible; `xid >= xmax` invisible.
- `xip[xcnt]` — in-progress top-level xids for normal MVCC (or *committed* xids between xmin/xmax for HISTORIC_MVCC — semantics inverted!).
- `subxip[subxcnt]`, `suboverflowed` — subxact xids; on overflow set the bool and use `SubTransGetTopmostTransaction` to walk to a top-level xid for membership tests.
- `takenDuringRecovery` — true if snapshot built in hot-standby; affects xip/subxip layout (all xids in subxip, xip empty).
- `copied` — true if palloc'd (not one of the static templates).
- `curcid` — own-xact: cmin < curcid visible.
- `speculativeToken` — DIRTY-only output.
- `vistest` — `GlobalVisState *` for NON_VACUUMABLE.
- `active_count`, `regd_count`, `ph_node` — refcount + pairing-heap node managed by snapmgr.c.
- `snapXactCompletionCount` — completion-count check that lets `GetSnapshotData` reuse a static snapshot if no xacts completed since last build. [from-comment, snapshot.h:204-209]

## Key invariants

- **All `xip[]` ids satisfy `xmin <= xip[i] < xmax`.** [from-comment, snapshot.h:162]
- **All `subxip[]` ids are `>= xmin`, but may be `>= xmax`.** [from-comment, snapshot.h:173-174]
- **For HISTORIC_MVCC the `xip` semantics are INVERTED** — it contains *committed* xacts between xmin and xmax. [from-comment, snapshot.h:158-161]
- **For recovery snapshots, ALL xids are in `subxip`; `xip` is empty.** Visibility code must branch on `takenDuringRecovery` accordingly (see XidInMVCCSnapshot at snapmgr.c:1888-1925). [from-comment, snapshot.h:168-171]
- **`copied = false` snapshot must not be registered or pushed**; snapmgr.c's `Push*` and `Register*` detect this and call `CopySnapshot` first.

## Open questions

- The `TODO` at lines 133-136 admits the struct overloads multiple roles and suggests a NodeTag split. Status: not done as of this commit. [from-comment]

## Confidence tag tally

`[verified-by-code]=1 [from-comment]=10 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/snapshot-lifecycle.md](../../../../data-structures/snapshot-lifecycle.md)