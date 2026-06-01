# gistxlog.c

- **Source path:** `source/src/backend/access/gist/gistxlog.c` (672 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/gistxlog.h` (record formats), `gist.c` (emitter for inserts/splits), `gistvacuum.c` (emitter for `XLOG_GIST_PAGE_DELETE`).

## Purpose

WAL redo (`gist_redo`), masking (`gist_mask`), and the AM-private replay context `opCtx`. Also hosts the WAL-emit helpers `gistXLogSplit`, `gistXLogPageDelete`, etc. (in the second half of the file, lines 490+). [from-comment, gistxlog.c:1-13]

## Record-to-handler table

| Info | Handler | Notes |
|---|---|---|
| `XLOG_GIST_PAGE_UPDATE` (0x00) | `gistRedoPageUpdateRecord` (69) | The workhorse: `(ntodelete, ntoinsert)` + offset array + tuples. Special-case `(1,1)` uses `PageIndexTupleOverwrite` for consistency with primary's `gistplacetopage`. Optionally clears `F_FOLLOW_RIGHT` on child (block 1) when this update completes a split |
| `XLOG_GIST_DELETE` (0x10) | `gistRedoDeleteRecord` (169) | The opportunistic LP_DEAD cleanup. **Generates recovery conflict** via `ResolveRecoveryConflictWithSnapshot(snapshotConflictHorizon, isCatalogRel)` BEFORE touching the buffer. Comment at lines 182-188: vacuum doesn't emit its own conflict — `XLOG_HEAP2_PRUNE_VACUUM_SCAN` already covered it for the heap |
| `XLOG_GIST_PAGE_REUSE` (0x20) | `gistRedoPageReuse` (373) | The recycle-conflict gate. Carries `snapshotConflictHorizon` = the page's previous `deleteXid`. Resolution via `ResolveRecoveryConflictWithSnapshotFullXid`. **Does not touch the buffer** — the page will be (re)initialized by the next split record |
| `XLOG_GIST_PAGE_SPLIT` (0x30) | `gistRedoPageSplitRecord` (244) | Initialize N new pages from scratch (`XLogInitBufferForRedo`). Hold lock on first-listed page throughout; other pages can be unlocked as soon as written, because no concurrent reader can reach them without visiting the first |
| `XLOG_GIST_PAGE_DELETE` (0x60) | `gistRedoPageDelete` (339) | VACUUM unlink: stamp `GistPageSetDeleted(deleteXid)` on the target leaf, delete the downlink in the parent |

(`XLOG_GIST_INSERT_COMPLETE` 0x40, `XLOG_GIST_CREATE_INDEX` 0x50, `XLOG_GIST_ASSIGN_LSN` 0x70 are reserved-but-unused.)

## Recovery-correctness notes [HIGH-RISK]

### `gistRedoClearFollowRight` (line 39)

Helper invoked from both `PAGE_UPDATE` and `PAGE_SPLIT`. **Updates the page even if the buffer was `BLK_RESTORED` from a full-page image** (line 52: handles `BLK_NEEDS_REDO || BLK_RESTORED`). The comment at 47-50 explains: "the updated NSN is not included in the image." That is, an FPI captures the *content* but not the page's NSN field — which lives in the GIST opaque area as a special LSN-like value. The redo here stamps the new NSN explicitly. **This is a GIST-specific replay subtlety**: most AMs trust FPI completely. [from-comment, gistxlog.c:47-50]

### Split replay (`gistRedoPageSplitRecord`)

Lock order: **first-listed page locked throughout; subsequent pages locked, written, unlocked sequentially**. Lines 256-260 give the rationale: "We must hold lock on the first-listed page throughout the action, including while updating the left child page (if any). We can unlock remaining pages in the list as soon as they've been written, because there is no path for concurrent queries to reach those pages without first visiting the first-listed page."

Per-page steps:
- `XLogInitBufferForRedo` (so no FPI possible).
- Initialize page with `F_LEAF` if leaf split (and not root).
- `gistfillbuffer` to add tuples.
- Set rightlink: chain to next page in the WAL record's list, except the last page uses `origrlink` from the record header.
- Stamp NSN = `xldata->orignsn` (which was the parent-insert LSN, not the split LSN — the same value the primary stamped).
- Set or clear `F_FOLLOW_RIGHT` based on `xldata->markfollowright` and whether this is the rightmost split-result.

For root splits: rightlink = `InvalidBlockNumber`, no F_FOLLOW_RIGHT.

After the per-page loop, `gistRedoClearFollowRight` clears `F_FOLLOW_RIGHT` on the *prior* left child (block 0) — completing any earlier in-progress split this record is finishing. [verified-by-code, gistxlog.c:244-336]

### Delete replay (`gistRedoDeleteRecord`)

`InHotStandby` block (lines 189-198): the conflict is resolved BEFORE any buffer modification. The comment at 182-188 is the authoritative explanation for why **VACUUM records do NOT also emit conflicts** — `XLOG_HEAP2_PRUNE_VACUUM_SCAN` already published the cutoff XID for the heap, and GIST's vacuum cleanup can't produce a horizon stricter than that.

### Page-reuse conflict (`gistRedoPageReuse`)

Identical pattern to nbtree's `XLOG_BTREE_REUSE_PAGE` and BRIN's analogous use of safexid: the conflict is published at *recycle* time, not at *delete* time. The `deleteXid` flows through as `snapshotConflictHorizon`. Comment at 378-386 is the canonical reference. [from-comment, gistxlog.c:378-391]

### `gist_redo` notes

The top-level redo dispatcher's comment (lines 400-404) says: "GiST indexes do not require any conflict processing." This is *almost* true — the per-record handlers `gistRedoDeleteRecord` and `gistRedoPageReuse` do emit conflicts individually. The comment refers to the *dispatcher* not needing global conflict handling, contrast with e.g. some AMs that hoist conflict resolution up. [verified-by-code; comment is mildly misleading]

## Masking (`gist_mask`)

- LSN/checksum + hint bits + unused space masked as standard.
- **NSN is masked** (set to `MASK_MARKER`): the NSN is a special-purpose LSN that diverges between primary and standby in benign ways. [from-comment, gistxlog.c:464-467]
- **F_FOLLOW_RIGHT flag is masked** (`GistMarkFollowRight(page)`): primary writes the flag *after* WAL emission in some paths, so the flag's value can race with replay. [from-comment, gistxlog.c:469-472]
- For leaf pages, additionally clears the `F_TUPLES_DELETED` and `F_HAS_GARBAGE` flags (per source after the snippet shown).

## Helper emitters (lines 490+)

`gistXLogSplit`, `gistXLogPageDelete`, `gistXLogPageReuse`, `gistXLogUpdate`, `gistXLogDelete` — called from the emitter sites in `gist.c`/`gistvacuum.c` to build WAL records.

## Cross-references

- **Dispatched from:** `access/transam/rmgr.c` via `RM_GIST_ID`.
- **Calls into:** `xlogutils.c` (`XLogReadBufferForRedo`/`XLogInitBufferForRedo`), `standby.c` (`ResolveRecoveryConflictWithSnapshot[FullXid]`), `gistutil.c` (page utils).

## Open questions

- The "first page held lock throughout" rule (line 256) appears to NOT match nbtree's split-replay pattern (which unlocks each block as it's written). The justification is that GIST's split atomically registers all new pages in a single record, so unlocking first would let a concurrent standby query reach a half-written sibling. **Whether this differs from nbtree because of WAL-record granularity, or because of a fundamental search-path difference, is not documented in code.** [unverified]
- `gistRedoClearFollowRight` only updates F_FOLLOW_RIGHT on the *child* indicated in block 1 of an update or block 0 of a split — i.e. exactly the page whose split is being finished. The standby never sees a stray F_FOLLOW_RIGHT outside the replay path, because if the standby crashes mid-replay, the recovery restart will re-apply this update. [inferred]
