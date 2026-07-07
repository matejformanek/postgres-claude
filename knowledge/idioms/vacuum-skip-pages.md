# VACUUM page-skipping — VM-bit-guided heap scan

VACUUM scans a heap relation page-by-page, BUT it can **skip**
pages whose visibility-map (VM) bit advertises "all-visible"
or "all-frozen" — because there's nothing there for VACUUM to
do. This is the key reason VACUUM on a well-maintained table
finishes quickly even on multi-TB heaps. The skip-decision
machinery has several modes (normal, aggressive, eager) with
different page-skipping policies, plus the readahead
optimization that makes ALL of this work.

Anchors:
- `source/src/backend/access/heap/vacuumlazy.c:40-115` —
  design comment [verified-by-code]
- `source/src/backend/access/heap/vacuumlazy.c:lazy_scan_heap`
  + `heap_vac_scan_next_block` [verified-by-code]
- `knowledge/subsystems/contrib-pg_visibility.md` — companion
  diagnostic; reads the VM
- `knowledge/idioms/visibility-map-update.md` — companion;
  writes the VM bits

## The three vacuum kinds

[from-comment `vacuumlazy.c:44-91`]

| Kind | Page-skip policy | Trigger |
|---|---|---|
| Normal | Skip all-visible/all-frozen pages above `SKIP_PAGES_THRESHOLD` | Routine autovacuum / explicit VACUUM |
| Aggressive | Scan EVERY page including all-frozen | `vacuum_freeze_table_age` / wraparound danger |
| Eager (within normal) | Selectively scan all-visible-but-not-all-frozen pages | Reduce backlog for next aggressive |

The **aggressive** kind is what advances `relfrozenxid` — only
by scanning every page can VACUUM be sure no tuple has an old
xmin that wraparound could affect.

The **normal** kind skips for performance — most pages aren't
worth visiting.

The **eager** behavior (PG 17+) is a heuristic inside normal
VACUUM: pre-emptively freeze some pages to reduce the work
the next aggressive vacuum has to do.

## SKIP_PAGES_THRESHOLD — the readahead trick

[from-comment `vacuumlazy.c:49-58`]

> When page skipping is not disabled, a normal vacuum may scan
> pages that are marked all-visible (and even all-frozen) in
> the visibility map if the range of skippable pages is below
> SKIP_PAGES_THRESHOLD. This is primarily for the benefit of
> kernel readahead.

Why scan pages you don't need to? Because sequential reads are
**faster than random reads** at the kernel level. If you'd skip
20 blocks, then read 1, then skip 30, then read 1, the kernel
sees random access. If you'd read all the blocks contiguously
(even the skippable ones), the kernel issues big sequential
reads. The cost of inspecting the extra pages is dwarfed by
the IO savings.

`SKIP_PAGES_THRESHOLD` (default 32 blocks = 256KB) is the
trade-off: gaps smaller than this are filled in (scan all
pages); gaps larger trigger the actual skip.

## The eager-freeze cap

[from-comment `vacuumlazy.c:64-87`]

Eager freezing has two caps:

1. **Global success cap** (`MAX_EAGER_FREEZE_SUCCESS_RATE` —
   default 0.2) — once 20% of all-visible-but-not-all-frozen
   pages have been eagerly frozen, eager scanning is disabled
   for the rest of the vacuum.
2. **Per-region failure cap** (`vacuum_max_eager_freeze_failure_rate`
   — default 0.03) — within each `EAGER_SCAN_REGION_SIZE`
   block range, allow at most 3% failed eager-freeze attempts
   before suspending eager scanning for the region.

The global cap prevents pathological cases where eager
freezing dominates a single VACUUM run. The per-region cap
adapts to data heterogeneity — old data clusters
get eager-frozen; young data clusters don't waste effort.

## The cleanup-lock case

[from-comment `vacuumlazy.c:92-97`]

> A non-aggressive vacuum may choose to skip pruning and
> freezing if it cannot acquire a cleanup lock on the buffer
> right away.

When VACUUM needs to **prune** a page (remove dead tuples),
it needs a **cleanup lock** — an exclusive content lock plus
the guarantee that no other backend has the buffer pinned.
Cleanup locks can block on backend pinners.

For non-aggressive vacuum, if cleanup-lock acquisition would
block, VACUUM just skips pruning on this page and moves on.
The dead tuples remain; next VACUUM gets another chance.

For aggressive vacuum, the cleanup lock is taken with a wait
— blocking pinners until they release. Aggressive must scan
everything.

## After the scan: VM bits update

[from-comment `vacuumlazy.c:99-100`]

> After pruning and freezing, pages that are newly all-visible
> and all-frozen are marked as such in the visibility map.

The VM bits are the OUTPUT of the heap scan as much as the
INPUT. A page that wasn't all-visible at scan start may be
after VACUUM cleans it up; the VM bit gets set so future
VACUUMs skip it.

This is the feedback loop: VACUUM uses VM bits to skip, and
maintains VM bits to enable future skipping. Without it, every
VACUUM would do a full scan.

## The dead-TID storage problem

[from-comment `vacuumlazy.c:104-114`]

> The major space usage for vacuuming is storage for the dead
> tuple IDs that are to be removed from indexes. We want to
> ensure we can vacuum even the very largest relations with
> finite memory space usage.

VACUUM accumulates dead TIDs during the heap scan and uses them
later to clean indexes (one entry per index, per dead TID).
The TID store can grow large; the design caps it at
`maintenance_work_mem` (or `autovacuum_work_mem` for
autovacuum).

When the cap is reached, VACUUM does an "intermediate index
cleanup" — flushes the dead-TID store to indexes, frees the
memory, and continues the heap scan. So very-large relations
may go through multiple index-cleanup passes per VACUUM.

## Production-use guidance

- **Don't disable page-skipping** unless debugging. The
  `DISABLE_PAGE_SKIPPING` option forces aggressive-like
  behavior; useful for "I think a VM bit is wrong, recheck
  everything" but expensive.
- **Aggressive vacuum is unavoidable** when XID wraparound
  approaches. Set `vacuum_freeze_table_age` to control when
  it kicks in; don't try to avoid it entirely.
- **The eager-freeze caps are tunable per-table.** A heavily-
  updated table can lower `vacuum_max_eager_freeze_failure_rate`
  to avoid wasted work.

## Invariants

- **[INV-1]** All-frozen pages are skippable by normal VACUUM;
  aggressive must scan them.
- **[INV-2]** Page-skipping respects `SKIP_PAGES_THRESHOLD`
  for kernel readahead optimization.
- **[INV-3]** Eager freeze is capped globally + per-region;
  bounds wasted work.
- **[INV-4]** Non-aggressive VACUUM skips pruning if cleanup
  lock would block; aggressive waits.
- **[INV-5]** VM bits are both consumed by the skip-decision
  and produced by the cleanup step.

## Useful greps

- The vacuum flavors:
  `grep -n 'aggressive\|vacrel->aggressive' source/src/backend/access/heap/vacuumlazy.c | head -20`
- The skip-threshold logic:
  `grep -n 'SKIP_PAGES_THRESHOLD\|heap_vac_scan_next_block' source/src/backend/access/heap/vacuumlazy.c`
- The eager-freeze caps:
  `grep -n 'EAGER_SCAN_REGION_SIZE\|MAX_EAGER_FREEZE_SUCCESS_RATE' source/src/backend/access/heap/vacuumlazy.c`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | 40 | design comment |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | — | primary implementation |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/visibility-map-update.md` — the VM bits
  this scan consumes + produces.
- `knowledge/idioms/xmin-horizon-management.md` — VACUUM
  consumes the horizon to decide which tuples are removable.
- `knowledge/idioms/heaptuple-update-chain.md` — chain
  semantics that VACUUM's prune walks.
- `knowledge/subsystems/contrib-pg_visibility.md` — diagnostic
  for "what does the VM actually claim?"
- `knowledge/subsystems/contrib-pgstattuple.md` — VM-aware
  sample estimator; uses the same skip logic.
- `.claude/skills/debugging/SKILL.md` — "VACUUM ran but
  nothing was cleaned" diagnostic.
- `source/src/backend/access/heap/vacuumlazy.c` — primary
  implementation.
