# Issues — `storage-aio`

Per-subsystem issue register for the PG18 AIO subsystem
(`src/backend/storage/aio/` + `src/include/storage/aio*.h`). See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem doc:** `knowledge/subsystems/storage-aio.md` (planned —
this directory is the top subsystem-synthesis candidate per
`progress/STATE.md`).

Seeded 2026-06-08 by the cloud/pg-file-backfiller `src/backend/storage/aio`
sweep (14 per-file docs). Most findings are author-acknowledged design
trade-offs (`XXX`/comment-flagged) rather than bugs — the subsystem is
new and unusually well-commented, so this register skews to
`question`/`undocumented-invariant`/`stale-todo` over `correctness`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-08 | src/backend/storage/aio/aio_funcs.c:197,211,218 | info-disclosure | maybe | `pg_aios` SRF exposes any backend's IO target description + file offsets cluster-wide; protecting ACL is on the view, not enforced here — relevant to the data-leak threat model (who can `SELECT pg_aios`) | open | knowledge/files/src/backend/storage/aio/aio_funcs.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/aio.c:316-317,156-159 | undocumented-invariant | maybe | `report_return` (`PgAioReturn *`) must outlive `CurrentResourceOwner`; on resowner cleanup the pointer is nulled and IO result is silently not reported | open | knowledge/files/src/backend/storage/aio/aio.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/aio.c:822-824 | question | nit | `pgaio_io_wait_for_free` blocks on the *specific* oldest in-flight IO when *any* completion would do (author `XXX`); can over-wait under io_uring | open | knowledge/files/src/backend/storage/aio/aio.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/aio_callback.c:39-49 | undocumented-invariant | nit | completion correctness relies on every backend compiling the `aio_handle_cbs[]` ID→pointer table identically (callback IDs travel in shared mem, table is process-local static) | open | knowledge/files/src/backend/storage/aio/aio_callback.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/method_worker.c:84-88 | question | maybe | single global submission queue + one `AioWorkerSubmissionQueueLock` is an acknowledged scaling ceiling (comment: contention "would surely get too high" beyond `MAX_IO_WORKERS`); worker is the default method | open | knowledge/files/src/backend/storage/aio/method_worker.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/method_worker.c:498-533 | question | nit | full-queue / lock-contended fallback runs the remaining IO batch synchronously in the latency-sensitive issuer — a tail-latency cliff precisely under load | open | knowledge/files/src/backend/storage/aio/method_worker.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/method_io_uring.c:449-472 | question | maybe | `io_uring_submit` EAGAIN (kernel memory pressure) → `elog(PANIC)` rather than retry; defensible (caller may hold locks) but turns a transient kernel condition into a cluster crash-restart | open | knowledge/files/src/backend/storage/aio/method_io_uring.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/method_io_uring.c:330-345 | stale-todo | nit | `XXX`: PG "probably should adjust the soft RLIMIT_NOFILE" for one ring FD per backend; today high `max_connections` + io_uring can hit EMFILE at startup, only a hint tells the DBA | open | knowledge/files/src/backend/storage/aio/method_io_uring.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/read_stream.c:828-836 | undocumented-invariant | nit | `int16` queue geometry silently caps a stream at ~32k pinned buffers (`PG_INT16_MAX - queue_overflow - 1`); a hard ceiling large `io_combine_limit`×`effective_io_concurrency`×`shared_buffers` tuning could hit | open | knowledge/files/src/backend/storage/aio/read_stream.c.md §Potential issues |
| 2026-06-08 | src/backend/storage/aio/read_stream.c:472-484 | question | nit | adaptive distance growth/decay schedule is hand-tuned; reducing `combine_distance` on hits has "no clear performance argument" beyond making fast-path entry work — future regressions here would be subtle throughput, not correctness | open | knowledge/files/src/backend/storage/aio/read_stream.c.md §Potential issues |
| 2026-06-08 | src/include/storage/aio_internal.h:373-376 | stale-todo | nit | `PGAIO_VERBOSE` defaults on even in non-assert builds; `XXX` says it should eventually be off, comment notes even elided logging "causes a measurable slowdown" (args still evaluated) | open | knowledge/files/src/include/storage/aio_internal.h.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **The AIO subsystem is structurally safe-by-design against the
  classic AIO deadlock**: it requires that completions are either
  processable by any backend (io_uring drain under `completion_lock`)
  or guaranteed to run even when the issuer blocks (worker offload).
  See README "Deadlock and Starvation Dangers due to AIO". None of the
  findings above contradict that property.
- **Completion-in-critical-section is a hard, pervasive constraint**:
  `pgaio_io_process_completion` asserts `CritSectionCount > 0` and the
  shared/local completion drivers wrap themselves in
  `START_CRIT_SECTION()`. Any future callback that wants to ereport
  from completion is fighting the architecture — the `PgAioResult` /
  `pgaio_result_report` deferral exists precisely so it doesn't have to.
- **Worker is the default `io_method`, not io_uring** — io_uring is
  Linux-only, opt-in, and `EXEC_BACKEND`-incompatible. Threat-model and
  perf discussions should assume worker mode unless told otherwise.
- Several findings are the same shape as findings elsewhere in the
  corpus: the `pg_aios` info-disclosure echoes the `pg_stat_*`
  view-ACL pattern; the `int16` cap echoes other "artificial limit,
  widen the types later" comments. Cross-link when the storage-aio
  subsystem doc is written.
