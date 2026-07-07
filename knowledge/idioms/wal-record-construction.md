# WAL record construction — the XLogInsert pattern

Every persistent change to PostgreSQL data — heap insert, btree
split, sequence increment, anything that survives a crash — is
preceded by a WAL record describing it. The construction
pattern is rigid: begin → register buffers → register payload →
insert. Every backend that modifies storage uses this same
4-call sequence. Deviation invents subtle bugs that surface
only under specific crash-recovery scenarios.

Anchors:
- `source/src/include/access/xloginsert.h` — public API
  [verified-by-code]
- `source/src/backend/access/transam/xloginsert.c` —
  implementation
- `source/src/backend/access/heap/heapam.c` — canonical
  user (heap_insert, heap_update, heap_delete)
- `knowledge/subsystems/access-transam.md` — the xlog
  subsystem
- `.claude/skills/wal-and-xlog/SKILL.md` — companion skill

## The 4-call construction sequence

```c
XLogBeginInsert();
XLogRegisterBuffer(0, buffer, REGBUF_STANDARD);
XLogRegisterData((const void *) &xlrec, SizeOfHeapInsert);
recptr = XLogInsert(RM_HEAP_ID, info);
PageSetLSN(page, recptr);
```

[canonical pattern, verified-by-code `heapam.c:2141-2162`]

- **`XLogBeginInsert()`** — open a new "record-under-construction"
  in per-backend scratch space. Each backend owns one such
  workspace; concurrent records are forbidden (use a stack of
  saved-state if needed).
- **`XLogRegisterBuffer(block_id, buf, flags)`** — declare a
  modified buffer. Up to 32 per record. The `block_id`
  (0..31) names the buffer slot in the record for redo to
  re-find.
- **`XLogRegisterData(data, len)`** — append non-buffer-tied
  payload (the per-record header struct, indexed tuple data
  for an INSERT, etc.).
- **`XLogInsert(rmid, info)`** — finalize, write into the WAL
  buffers, return the LSN of the record's *start*.
- **`PageSetLSN(page, recptr)`** — stamp the modified page's
  PD_LSN with the new record's LSN. This is what guarantees
  the WAL-before-data invariant on checkpoint.

## The REGBUF flag set

[verified-by-code `xloginsert.h:31-42`]

| Flag | Value | Meaning |
|---|---|---|
| `REGBUF_FORCE_IMAGE` | 0x01 | Force a full-page image even if not strictly needed |
| `REGBUF_NO_IMAGE` | 0x02 | Skip the full-page image |
| `REGBUF_WILL_INIT` | 0x06 | Page will be re-initialized; replay starts from blank |
| `REGBUF_STANDARD` | 0x08 | Standard layout (PageHeader-aware) |
| `REGBUF_KEEP_DATA` | 0x10 | Include `RegisterBufData` even if FPI taken |
| `REGBUF_NO_CHANGE` | 0x20 | Page locked but not modified (LSN unchanged) |

The flag combinations encode replay semantics:

- **Plain `REGBUF_STANDARD`** — backend modified the page; if a
  checkpoint hadn't observed this LSN yet, a full-page image
  is included automatically.
- **`REGBUF_STANDARD | REGBUF_WILL_INIT`** — replay can skip the
  full-page-image entirely. The redo function will call
  `XLogInitBufferForRedo` to fabricate the page from scratch.
- **`REGBUF_STANDARD | REGBUF_KEEP_DATA`** — needed when the
  per-buffer-data carries information not reconstructible from
  the FPI (e.g. visibility-map update bits that aren't in the
  heap page).

[verified-by-code `heapam.c:2114, 2134, 2152, 2564, 2572, 2576`]

## The two data registration calls

- `XLogRegisterData(data, len)` — global to the record (one
  per record).
- `XLogRegisterBufData(block_id, data, len)` — tied to a
  specific buffer (one per `XLogRegisterBuffer` call, ordered
  with the registration).

The distinction matters for full-page-image handling. Data
tied to a buffer via `XLogRegisterBufData` is **omitted** when
a full-page image is included (unless `REGBUF_KEEP_DATA`),
because the FPI already contains the bytes. Data registered via
`XLogRegisterData` is always included.

Forgetting `REGBUF_KEEP_DATA` on `RegisterBufData` that's NOT
reconstructible from the FPI = "redo applied stale state"
bugs.

## The two rmgr-id namespace

`XLogInsert(rmid, info)` — `rmid` selects the resource manager
that owns the redo function. `info` is record-type within that
rmid.

The rmid is set at build time (in `rmgrlist.h`). The 8-bit
`info` byte is split: lower 4 bits = record-type discriminator,
upper 4 bits = rmgr-private flags. Heap2 (`RM_HEAP2_ID`) is a
spillover rmgr for additional heap record types when
`RM_HEAP_ID` ran out of info-byte slots.

## Common review-time concerns

- **Always `PageSetLSN` after `XLogInsert`.** Without it, the
  checkpoint can flush the modified page before the WAL
  reaches disk, breaking the WAL-before-data invariant. PG
  asserts this in dev builds.
- **`REGBUF_WILL_INIT` requires `REGBUF_NO_IMAGE`.** The flag
  value `0x06` includes both [verified-by-code
  `xloginsert.h:34`]. Set `REGBUF_WILL_INIT` alone and the
  page will get a redundant FPI.
- **Stack-allocated payload** registered via
  `XLogRegisterData` is safe — the data is copied into the
  WAL buffer inside `XLogInsert`. Pointer-into-page is
  fine too if the page is still locked at `XLogInsert` time.
- **Critical sections** — most WAL emission happens inside a
  critical section (`START_CRIT_SECTION`...`END_CRIT_SECTION`)
  so that any ERROR between modifying the page and emitting
  the WAL becomes a `PANIC`. Skipping the critical section is
  a recipe for permanent on-disk inconsistency.

## Performance considerations

- The XLogInsert path is performance-critical. Modifications
  to it have measurable impact on TPS for write-heavy
  workloads.
- `wal_level=minimal` disables full-page images for certain
  operations; `wal_level=replica` (default) emits them at the
  first modification after a checkpoint.
- `full_page_writes=off` disables FPIs cluster-wide (rare;
  storage-stack-guaranteed atomic writes only).

## Invariants

- **[INV-1]** Begin → Register* → Insert sequence. No
  reordering, no skipping.
- **[INV-2]** `PageSetLSN(page, recptr)` MUST follow
  `XLogInsert` while the page is still locked.
- **[INV-3]** `REGBUF_KEEP_DATA` is required when
  `RegisterBufData` isn't reconstructible from the FPI.
- **[INV-4]** WAL emission happens inside a critical section;
  errors become PANICs by design.
- **[INV-5]** Each backend has ONE in-progress WAL record at
  a time; nesting is forbidden.

## Useful greps

- All XLogInsert call sites:
  `grep -RIn 'XLogInsert(' source/src/backend | wc -l`
- REGBUF flag usage:
  `grep -RIn 'REGBUF_' source/src/backend/access | head -30`
- The critical-section wrappers around WAL emission:
  `grep -B1 -A3 'XLogInsert' source/src/backend/access/heap/heapam.c | head -30`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | — | canonical user (heap_insert, heap_update, heap_delete) |
| [`src/backend/access/transam/xloginsert.c`](../files/src/backend/access/transam/xloginsert.c.md) | — | implementation |
| [`src/include/access/xloginsert.h`](../files/src/include/access/xloginsert.h.md) | — | public API + REGBUF flags |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md)
- [`add-new-index-am`](../scenarios/add-new-index-am.md)
- [`add-new-wal-record`](../scenarios/add-new-wal-record.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/xlog-region-replay.md` — companion: the
  redo side of this same record.
- `knowledge/subsystems/access-transam.md` — the xlog
  subsystem.
- `.claude/skills/wal-and-xlog/SKILL.md` — the skill covering
  WAL record design.
- `knowledge/data-structures/xlogreaderstate.md` — the redo
  consumer side (`XLogReaderState` is what redo reads).
- `source/src/include/access/xloginsert.h` — public API +
  REGBUF flags.
- `source/src/backend/access/transam/xloginsert.c` —
  implementation.
- `source/src/backend/access/heap/heapam.c` — canonical
  caller patterns.
