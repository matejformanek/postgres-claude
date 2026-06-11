# Issues — `executor`

Per-subsystem issue register for `src/backend/executor/` plan-node
executors and shared scan / projection infrastructure.

**Parent subsystem docs:**
- `knowledge/subsystems/executor.md`
- `knowledge/files/src/backend/executor/*.c.md`

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | executor/nodeSeqscan.c:101-104 | stale-todo | nit | `SeqRecheck` comment: "Note that unlike IndexScan, SeqScan never use keys in heap_beginscan (and this is very bad)". From 2008 (commit 9bacdf9f); EPQ on SeqScan re-emits all surviving tuples regardless of qual, re-applies qual in ExecScan | open | knowledge/files/src/backend/executor/nodeSeqscan.c.md §Potential issues |
| 2026-06-11 | executor/nodeSeqscan.c:51,98 | question | maybe | `pg_attribute_always_inline` on `SeqNext`/`SeqRecheck` — only matters if `ExecScanExtended` itself inlines into the variant's body across TU boundary. Worth checking the build actually picks up the intended specialisation | open | knowledge/files/src/backend/executor/nodeSeqscan.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- PG18 reshapes `nodeSeqscan` with four `ExecSeqScan*` variants
  selected at init time by `(qual?) × (projection?)`, plus an EPQ
  variant. The `pg_attribute_always_inline` on `SeqNext`/`SeqRecheck`
  is the lever that's supposed to make this specialisation actually
  fire — but `ExecScanExtended` lives in `execScan.c` so cross-TU
  inlining matters.
- This file is also notable for being one of the few executor nodes
  with full parallel-instrumentation plumbing (separate DSM key,
  per-worker accumulation in `ExecEndSeqScan`, leader retrieval in
  `ExecSeqScanRetrieveInstrumentation`). The pattern was generalised
  in PG17 but SeqScan is the canonical example.
