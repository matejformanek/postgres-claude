# Issues — `test-modules`

Per-subsystem issue register for `src/test/modules/` (the in-tree test
extensions / sample modules: injection_points, worker_spi, test_shm_mq,
test_slru, test_dsa, dummy_index_am, test_oat_hooks, …). See
`knowledge/issues/README.md` for the tag convention, severity scale, and
workflow.

**Parent docs:** per-file docs under `knowledge/files/src/test/modules/`.

These are test/sample modules, not production backend code, so the bar
for "issue" here is mostly: a misleading comment a copy-paster would
inherit, an undocumented invariant a new test author would trip on, or a
sample that models a slightly-off pattern. Severities skew `nit`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-15 | injection_points/injection_points.c:513 | leak | nit | detach builds throwaway makeString in TopMemoryContext; deleted list node / pstrdup'd attach string not explicitly freed — slow leak under repeated attach/detach in a long-lived backend | open | knowledge/files/src/test/modules/injection_points/injection_points.c.md §Potential issues |
| 2026-06-15 | injection_points/injection_points.c:174 | doc-drift | nit | injection_points_cleanup detaches local points at before_shmem_exit but never clears inj_list_local / injection_point_local, leaving stale list state | open | knowledge/files/src/test/modules/injection_points/injection_points.c.md §Potential issues |
| 2026-06-15 | test_shm_mq/setup.c:192 | doc-drift | nit | comment says allocate in CurTransactionContext (and switches to it), but the MemoryContextAlloc explicitly uses TopTransactionContext; the switch governs no load-bearing allocation | open | knowledge/files/src/test/modules/test_shm_mq/setup.c.md §Potential issues |
| 2026-06-15 | test_shm_mq/worker.c:99 | undocumented-invariant | nit | workers_total read outside hdr->mutex while adjacent counter accesses are mutex-protected; safe only because workers_total is write-once before workers start | open | knowledge/files/src/test/modules/test_shm_mq/worker.c.md §Potential issues |
| 2026-06-15 | dummy_index_am/dummy_index_am.c:25 | undocumented-invariant | nit | di_relopt_tab sized [8] but only 7 entries filled; dioptions passes lengthof()=8 to build_reloptions, leaving a zero-init slack slot with NULL optname | open | knowledge/files/src/test/modules/dummy_index_am/dummy_index_am.c.md §Potential issues |
| 2026-06-15 | test_oat_hooks/test_oat_hooks.c:289 | question | nit | deny path runs in POST_* hooks after the catalog mutation, relying on rollback — documented limitation of POST hooks as an enforcement point | open | knowledge/files/src/test/modules/test_oat_hooks/test_oat_hooks.c.md §Potential issues |
| 2026-06-15 | test_oat_hooks/test_oat_hooks.c:237 | question | nit | audit emission gated on !IsParallelWorker() only (for deterministic output); worker-side accesses go un-audited by design | open | knowledge/files/src/test/modules/test_oat_hooks/test_oat_hooks.c.md §Potential issues |
| 2026-06-15 | worker_spi/worker_spi.c:182 | leak | nit | quote_identifier results leaked (explicitly acknowledged in-code) | open | knowledge/files/src/test/modules/worker_spi/worker_spi.c.md §Potential issues |
| 2026-06-15 | worker_spi/worker_spi.c:83 | stale-todo | nit | "XXX could we use CREATE SCHEMA IF NOT EXISTS?" open question | open | knowledge/files/src/test/modules/worker_spi/worker_spi.c.md §Potential issues |
| 2026-06-15 | test_dsa/test_dsa.c:79 | correctness | nit | dsa_pointer p[10000] (~80KB) on-stack array in test_dsa_resowners | open | knowledge/files/src/test/modules/test_dsa/test_dsa.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

All rows above are `nit`-grade and concern test/sample modules. The two
`question` rows on `test_oat_hooks.c` (POST-hook deny timing, parallel-worker
audit gap) are documented behaviors of the OAT framework, surfaced here only
because `test_oat_hooks` is a Phase-D (data-leak hardening) trust-boundary
reference. The `test_dsa.c:79` ~80KB on-stack array is in a test routine that
controls its own recursion/stack budget, so it is `correctness/nit` not a real
overflow risk — flagged because a copy-paster into production code would
inherit an unbounded stack allocation.
