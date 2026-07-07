# contrib-pg_freespacemap (FSM inspector)

- **Source path:** `source/contrib/pg_freespacemap/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `pg_freespacemap.control`)
- **Trusted:** no (per-function REVOKE FROM PUBLIC; `pg_monitor`
  membership recommended)

## 1. Purpose

Surface the per-page **Free Space Map** (FSM) to SQL. The FSM
records the approximate amount of free space on each heap (or
GIN / GiST) page; the system uses it to pick a target page for
INSERT / UPDATE without scanning every page. pg_freespacemap is
the diagnostic probe for "why is INSERT picking the wrong
page?" and the verification tool after FSM corruption recovery.

The smallest contrib extension — a single 53-LOC file
[verified-by-code `wc -l source/contrib/pg_freespacemap/pg_freespacemap.c`].

## 2. SQL surface

```sql
SELECT pg_freespace('mytable', blkno);              -- one block
SELECT * FROM pg_freespace('mytable');              -- whole relation SRF
```

[verified-by-code `pg_freespacemap.c:25` registers `pg_freespace`]

Both variants return bytes-of-free-space-per-block. The
relation-level SRF emits `(blkno bigint, avail int2)` rows.

## 3. Mental model — FSM is approximate

The FSM is **not** the precise free-space accounting. It's a
**lossy upper estimate** updated by:

- INSERT / UPDATE — when a backend records that a page filled
  up below its previous estimate.
- VACUUM — when free-space recovery reconciles the actual
  free space with the FSM.
- HOT pruning — when prune frees space, the FSM gets updated
  if the new estimate is materially different.

The system's choice rule: "find a page with at least N bytes
free." pg_freespacemap surfaces what the FSM **claims**, not
what the page actually has. The actual page can have MORE free
space (and the FSM is just stale) or theoretically LESS (if
the FSM accounting hadn't caught a concurrent insert) — never
LESS by a wide margin without a serious bug.

## 4. The underlying primitive

[verified-by-code `pg_freespacemap.c:49`]

```c
freespace = GetRecordedFreeSpace(rel, blkno);
```

`GetRecordedFreeSpace()` reads the FSM-fork value for one
block. The FSM fork stores values quantized to a small range
(typically 0..255 representing 0..8KB in steps of ~32 bytes)
to keep the FSM compact.

## 5. The FSM tree structure (background)

The FSM is internally a **3-level tree** stored in its own
relation fork. Each leaf page records 4096 block-entries
(quantized to single bytes). Higher levels summarize maxima
over children. The lookup-by-size walks from root down,
making O(log n) page reads.

pg_freespacemap doesn't expose the tree structure — it only
exposes the per-leaf value. The full tree can be inspected via
`pageinspect`'s `fsm_page_contents(page bytea)`.

## 6. Production-use guidance

- **"Why is INSERT slow?"** — if `pg_freespacemap` shows many
  low-availability blocks, the relation is full and INSERTs
  must extend. Check `pg_class.reltuples` vs disk size.
- **"INSERT is picking pages it shouldn't"** — if the FSM is
  drift-stale (low-quality estimates), VACUUM the relation to
  rebuild the FSM accounting.
- **"FSM corrupted by crash"** — DELETE the `<relfilenode>_fsm`
  file from the relation's directory while the server is
  stopped; the next access reconstructs it. (Not via
  pg_freespacemap; this is offline recovery.)
- **Per-row cost** — `GetRecordedFreeSpace` is cheap (one FSM
  page read, no buffer pin held); whole-relation SRF is
  O(blocks-in-relation/4096).

## 7. The trio with VACUUM

VACUUM is the only path that fully recomputes the FSM. After:

- A large DELETE — the FSM should be VACUUMed to surface the
  newly-free space.
- A corruption-recovery event — VACUUM rebuilds from heap.
- A schema-bloat episode — VACUUM FULL rewrites the heap;
  the FSM is reset.

pg_freespacemap before/after VACUUM is the canonical "did
VACUUM recover what I expected?" probe.

## 8. Invariants

- **[INV-1]** FSM is approximate; reported free space is a
  lossy upper-estimate.
- **[INV-2]** `pg_freespace(rel, blkno)` returns
  `GetRecordedFreeSpace(rel, blkno)` directly; no
  interpretation.
- **[INV-3]** Only heap / GIN / GiST AMs have an FSM fork;
  others ERROR.
- **[INV-4]** VACUUM is the canonical FSM rebuild path.

## 9. Useful greps

- The single C-file:
  `cat source/contrib/pg_freespacemap/pg_freespacemap.c`
- FSM internals reference:
  `find source/src/backend/storage/freespace -type f`
- All FSM-update sites:
  `grep -RIn 'RecordPageWithFreeSpace\|RecordAndGetPageWithFreeSpace' source/src/backend`

## 10. Cross-references

- `knowledge/subsystems/access-heap.md` — heap AM; how
  INSERT consults the FSM to pick a target page.
- `knowledge/subsystems/contrib-pageinspect.md` — companion;
  `fsm_page_contents(bytea)` decodes the full FSM tree.
- `knowledge/subsystems/contrib-pgstattuple.md` — companion
  bloat audit; FSM accuracy is upstream of bloat diagnosis.
- `.claude/skills/debugging/SKILL.md` — `pg_freespacemap` is
  the first probe for "INSERT slow / picking wrong page."
- `source/src/backend/storage/freespace/freespace.c` — FSM
  implementation.
- `source/contrib/pg_freespacemap/pg_freespacemap.c` — the
  53-LOC SQL shim.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/pg_freespacemap/pg_freespacemap.c`](../files/contrib/pg_freespacemap/pg_freespacemap.c.md) |

<!-- /files-owned:auto -->
