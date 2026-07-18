# `src/backend/executor/nodeSeqscan.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~535
- **Source:** `source/src/backend/executor/nodeSeqscan.c`

The executor node for **SeqScan** — the most-used scan node in the
system. Despite that, the file is mostly delegation: real heap I/O
lives behind `table_beginscan` / `table_scan_getnextslot` /
`table_endscan` in the TableAM layer; this file is the
`PlanState`-glue, the qual/projection-variant dispatch, and the
parallel-scan + parallel-instrumentation plumbing. [verified-by-code]

PG18 introduces a noticeable restructuring: instead of one `ExecSeqScan`,
there are now FOUR specialized variants chosen at `ExecInitSeqScan`
time based on (qual present?) × (projection present?), plus a fifth
for EvalPlanQual (EPQ). Each variant has `Assert`/`pg_assume` proving
its branch conditions, letting the compiler eliminate the
NULL-checks inside `ExecScanExtended`. [verified-by-code §nodeSeqscan.c:108-213, 271-291]

## API / entry points

- `SeqScanState *ExecInitSeqScan(SeqScan *node, EState *estate, int eflags)` —
  opens the scan relation, creates the scan tuple slot with
  `table_slot_callbacks(rel)`, initialises qual / projection, and
  picks one of:
  - `ExecSeqScan` — no qual, no projection
  - `ExecSeqScanWithQual` — qual only
  - `ExecSeqScanWithProject` — projection only
  - `ExecSeqScanWithQualProject` — both
  - `ExecSeqScanEPQ` — EvalPlanQual in flight (no per-variant
    optimisation, calls plain `ExecScan`).
  [verified-by-code §nodeSeqscan.c:219-294]
- `void ExecEndSeqScan(SeqScanState *)` — `table_endscan` and, in
  parallel workers, drains I/O stats into shared instrumentation.
  [verified-by-code §nodeSeqscan.c:303-333]
- `void ExecReScanSeqScan(SeqScanState *)` — calls `table_rescan`
  (no new scan keys) then `ExecScanReScan`. [verified-by-code §nodeSeqscan.c:347-358]
- `void ExecSeqScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker`
  — the parallel-scan DSM TOC entries. Allocates a
  `ParallelTableScanDesc` of size `table_parallelscan_estimate(...)`
  in the parallel context's TOC, keyed by `plan_node_id`.
  [verified-by-code §nodeSeqscan.c:372-452]
- `void ExecSeqScanInstrument{Estimate,InitDSM,InitWorker}` plus
  `ExecSeqScanRetrieveInstrumentation` — separate DSM key
  `plan_node_id + PARALLEL_KEY_SCAN_INSTRUMENT_OFFSET` for shared I/O
  stats per worker; only allocated if `INSTRUMENT_IO` and
  `pcxt->nworkers > 0`. [verified-by-code §nodeSeqscan.c:457-534]
- Static helpers:
  - `SeqNext` — calls `table_beginscan` lazily on first call (since
    parallel and serial both end up here), then
    `table_scan_getnextslot`. Marked `pg_attribute_always_inline` —
    intended to be inlined into the per-variant callers.
    [verified-by-code §nodeSeqscan.c:51-93]
  - `SeqRecheck` — always returns true; SeqScan doesn't store scan
    keys to recheck (the comment frankly admits "this is very bad").
    [verified-by-code §nodeSeqscan.c:96-106]

## Notable invariants / details

- **No locking happens here.** AccessShareLock on the relation was
  taken much earlier (at parser/planner time, when the RangeTblEntry
  was set up) and `ExecOpenScanRelation` just `relation_open`s with
  `NoLock` to acquire the relcache entry. The buffer access is
  internal to the TableAM's scan implementation.
  [verified-by-code §nodeSeqscan.c:248-251 — note `ExecOpenScanRelation` does the lookup with the already-held lock]
- **Lazy scan-descriptor creation.** `SeqNext` opens
  `table_beginscan` on first call, NOT in `ExecInitSeqScan`. This is
  important for parallel: when the leader's plan was originally
  parallel but ends up running serially, we still want to open the
  scan here rather than upfront. The comment is explicit: "We reach
  here if the scan is not parallel, or if we're serially executing a
  scan that was planned to be parallel." [from-comment §nodeSeqscan.c:77-80]
- **SeqScan has no children** — both `outerPlan` and `innerPlan` are
  Asserted NULL in `ExecInitSeqScan`. The comment notes "Once upon a
  time it was possible to have an outerPlan of a SeqScan, but not
  any more." [verified-by-code §nodeSeqscan.c:225-229]
- **Flag set per scan**: `SO_HINT_REL_READ_ONLY` if the rel is
  `ScanRelIsReadOnly` (no concurrent writers expected — set for
  finalised parallel BTREE-build readers and a few others), and
  `SO_SCAN_INSTRUMENT` if `INSTRUMENT_IO` is on. Both DSM init
  paths re-compute these per worker. [verified-by-code §nodeSeqscan.c:68-75, 396-403, 441-447]
- **EPQ uses a separate variant** even though it could share with
  the WithQualProject path. The comment says "EPQ doesn't seem as
  exciting a case to optimize for" — i.e. plain `ExecScan` is fine
  there. [from-comment §nodeSeqscan.c:201-203]
- **Per-worker I/O stats accumulation** in `ExecEndSeqScan`: the
  worker reads `scanDesc->rs_instrument->io` and accumulates into
  `sinstrument->sinstrument[ParallelWorkerNumber]`. Leader picks
  them up via `ExecSeqScanRetrieveInstrumentation`.
  [verified-by-code §nodeSeqscan.c:315-326, 520-534]

## Potential issues

- **File-line `nodeSeqscan.c:101-104`.** `SeqRecheck` comment: "Note
  that unlike IndexScan, SeqScan never use keys in heap_beginscan
  (and this is very bad) - so, here we do not check are keys ok or
  not." This comment dates from 2008 (commit 9bacdf9f); the practical
  impact is that EvalPlanQual on a SeqScan re-emits ALL surviving
  tuples regardless of qual, then re-applies the qual in
  `ExecScan`. Not exactly a bug, but a long-acknowledged smell.
  [ISSUE-stale-todo: SeqRecheck always-true acknowledged "very bad" (nit)]
- **File-line `nodeSeqscan.c:51, 98`.** `pg_attribute_always_inline`
  on `SeqNext` / `SeqRecheck` — the inlining only happens through
  the indirect function pointer cast `(ExecScanAccessMtd) SeqNext`
  passed to `ExecScanExtended`. If `ExecScanExtended` itself isn't
  inlined into the variant's body (it's in `executor/execScan.c`),
  the always-inline doesn't actually help and the calls stay
  indirect. Worth checking that the build actually picks up the
  intended specialisation via LTO / per-file inline-pickup.
  [ISSUE-question: does pg_attribute_always_inline actually fire through fn-ptr cast? (maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `executor`](../../../../issues/executor.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
