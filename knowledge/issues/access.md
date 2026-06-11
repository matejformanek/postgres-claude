# Issues — `access`

Per-subsystem issue register for `src/backend/access/` files surfaced
during the file-by-file deep-corpus phase. See `knowledge/issues/README.md`
for the tag convention, severity scale, and workflow.

**Parent subsystem docs:**
- `knowledge/subsystems/access-heap.md` (heap AM)
- `knowledge/files/src/backend/access/gin/README.md` (GIN)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | access/gin/ginarrayproc.c:62 | stale-todo | nit | `ginarrayextract_2args` comment says "should go away eventually" — 15-year-old compatibility shim for pre-9.1 contrib/intarray opclass reloads, still present | open | knowledge/files/src/backend/access/gin/ginarrayproc.c.md §Potential issues |
| 2026-06-11 | access/gin/ginarrayproc.c:305 | doc-drift | nit | `default` branch in `ginarraytriconsistent` errors with copy-pasted string `"ginarrayconsistent"` (wrong function name) | open | knowledge/files/src/backend/access/gin/ginarrayproc.c.md §Potential issues |
| 2026-06-11 | access/gin/ginbulk.c:41 | doc-drift | nit | "posting list is too long" errhint advises `Reduce "maintenance_work_mem"` but the real cause is one extremely common key, not memory pressure | open | knowledge/files/src/backend/access/gin/ginbulk.c.md §Potential issues |
| 2026-06-11 | access/heap/heapam_indexscan.c:112 | undocumented-invariant | nit | Long-standing `XXX: we should assert that a snapshot is pushed or registered` — the `RecentXmin` assertion is a weak proxy, real invariant unchecked | open | knowledge/files/src/backend/access/heap/heapam_indexscan.c.md §Potential issues |
| 2026-06-11 | access/heap/heapam_indexscan.c:199 | undocumented-invariant | maybe | "Note: if you change the criterion here for what is 'dead', fix the planner's `get_actual_variable_range()` function to match" — cross-module invariant only enforced by a comment | open | knowledge/files/src/backend/access/heap/heapam_indexscan.c.md §Potential issues |
| 2026-06-11 | access/heap/heaptoast.c:213 | stale-todo | nit | `XXX maybe the threshold should be less than maxDataLen?` — open design question in toast compression pass 1, immediate-externalise threshold | open | knowledge/files/src/backend/access/heap/heaptoast.c.md §Potential issues |
| 2026-06-11 | access/heap/heaptoast.c:401 | doc-drift | nit | `toast_flatten_tuple` copies HEAP_XACT_MASK / HEAP2_XACT_MASK visibility bits "in case anybody looks at those fields in a syscache entry" — no concrete description of what would break otherwise | open | knowledge/files/src/backend/access/heap/heaptoast.c.md §Potential issues |
| 2026-06-11 | access/nbtree/nbtreadpage.c | question | maybe | Should the array-keys state machine (~half of the file, ~1500 lines) be split into its own TU separate from the page-read hot path? Pre-PG18 it lived in nbtutils.c | open | knowledge/files/src/backend/access/nbtree/nbtreadpage.c.md §Potential issues |
| 2026-06-11 | access/nbtree/nbtreadpage.c:134-535 | style | nit | `_bt_readpage` is one ~400-line function interleaving parallel + SAOP forward + non-SAOP forward + backward paths — high cognitive load | open | knowledge/files/src/backend/access/nbtree/nbtreadpage.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- The GIN per-AM files are mostly thin support-function shims;
  potential-issues are dominated by stale TODOs and cosmetic
  copy-paste glitches. None are correctness bugs.
- Heap toast (`heaptoast.c`) is dense and load-bearing — the four-pass
  compression-then-externalise loop has one open XXX (line 213) that's
  worth eventually answering with a benchmark. The cross-module
  comment at heapam_indexscan.c:199 (dead-tuple criterion shared with
  `optimizer/plan/analyzejoins.c get_actual_variable_range`) is the
  kind of fragile cross-file invariant Phase A is supposed to surface.
- All ginarrayproc cosmetic issues (lines 62, 220, 305, 307) are
  invariant under a single ~10-line cleanup commit if anyone ever cares.
