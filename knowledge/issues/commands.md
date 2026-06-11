# Issues — `commands`

Per-subsystem issue register for files under `src/backend/commands/`.
See `knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem doc:** none yet (commands is too broad; per-file docs only).

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | commands/explain_format.c:711-714 | doc-drift | nit | `escape_yaml()` just calls `escape_json()` despite the long comment about YAML quoting being "ridiculously complicated"; comment is correct but body is one line, easy to miss the intent. | open | knowledge/files/src/backend/commands/explain_format.c.md §Potential issues |
| 2026-06-11 | commands/repack_worker.c:117-123 | undocumented-invariant | maybe | Comment "Not sure the spinlock is needed here" acknowledges uncertainty about a synchronization invariant; should be tightened or removed before this code is durable. | open | knowledge/files/src/backend/commands/repack_worker.c.md §Potential issues |
| 2026-06-11 | commands/repack_worker.c:138-140 | style | nit | Comment "There doesn't seem to a nice API to set these" — grammar nit and signals tech-debt around setting `XactIsoLevel`/`XactReadOnly` directly. | open | knowledge/files/src/backend/commands/repack_worker.c.md §Potential issues |
| 2026-06-11 | commands/repack_worker.c:84,170-179 | correctness | maybe | `before_shmem_exit(RepackWorkerShutdown,...)` uses `PointerGetDatum(shared)` but `shared` is a pointer into the DSM segment that this same callback `dsm_detach`s; touching `shared->backend_pid` inside the callback is fine only because `SendProcSignal` runs before `dsm_detach`. Order is critical, worth a comment. | open | knowledge/files/src/backend/commands/repack_worker.c.md §Potential issues |
| 2026-06-11 | commands/proclang.c:134-139 | dead-path | nit | `#ifdef NOT_USED` ownership check block; comment says "currently pointless, since we already checked superuser". Either delete or convert to a non-superuser path. | open | knowledge/files/src/backend/commands/proclang.c.md §Potential issues |
| 2026-06-11 | commands/createas.c:541-546 | undocumented-invariant | maybe | RLS check rejects `RLS_ENABLED` but accepts anything else; comment says "We don't actually support that currently" — invariant about RLS-on-matview lifecycle should be tracked. | open | knowledge/files/src/backend/commands/createas.c.md §Potential issues |
| 2026-06-11 | commands/createas.c:575-576 | undocumented-invariant | nit | Assert `RelationGetTargetBlock(intoRelationDesc) == InvalidBlockNumber` with comment "This may be harmless, but this function hasn't planned for it." Speculative defensive Assert worth tagging. | open | knowledge/files/src/backend/commands/createas.c.md §Potential issues |
| 2026-06-11 | commands/sequence_xlog.c:50,68 | style | nit | `palloc`+`pfree` of local page per redo is fine but adds palloc churn on every sequence WAL record; a static buffer would suffice since redo is single-threaded per startup process. | open | knowledge/files/src/backend/commands/sequence_xlog.c.md §Potential issues |
| 2026-06-11 | commands/propgraphcmds.c:302-305 | undocumented-invariant | maybe | After second-pass vertex lookup, four `Assert`s claim srcvertexid/destvertexid/srcrelid/destrelid all non-zero. Relies on the same alias-match loop succeeding; would deserve a comment ("guaranteed by first-pass validation above"). | open | knowledge/files/src/backend/commands/propgraphcmds.c.md §Potential issues |
| 2026-06-11 | commands/vacuumparallel.c:117-123 | doc-drift | nit | Comment "Not sure the spinlock is needed here" applies to the autovacuum-cost-delay generation counter; modern atomics docs would resolve this. (NB: distinct from the same string in repack_worker.) | open | knowledge/files/src/backend/commands/vacuumparallel.c.md §Potential issues |
| 2026-06-11 | commands/explain_state.c:182-185 | undocumented-invariant | nit | Defaulting `timing` and `buffers` to `analyze` (when unset) silently makes EXPLAIN ANALYZE more expensive; users hitting buffer-tracking overhead may not realize buffers defaulted on. Documented in user docs but the contract is non-obvious from the source alone. | open | knowledge/files/src/backend/commands/explain_state.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

- `repack_worker.c` is a PG18+ addition for REPACK CONCURRENTLY (ad-hoc
  logical decoding). The "Not sure the spinlock is needed" and "There
  doesn't seem to a nice API" comments are tells that the patch
  landed with rough edges still in place.
- `explain_dr.c`, `explain_format.c`, `explain_state.c` are the post-18
  EXPLAIN split (formerly all in explain.c). The split is clean; few
  issues. `explain_state.c` is the registration surface for extension
  options.
- `propgraphcmds.c` (SQL/PGQ CREATE/ALTER PROPERTY GRAPH) is 1882 LOC,
  the largest in this sweep. Heavy use of `ArrayType *` for attnum and
  opclass lists; element_info struct passes a lot of state.
- `sequence_xlog.c` is the WAL-redo split out of sequence.c.
- `vacuumparallel.c` introduces autovacuum parallel index vacuum (PG18
  addition: `PVSharedCostParams` with generation counter for hot-reload
  of cost-delay).
- `constraint.c` (unique_key_recheck) is the historic deferred-unique
  AFTER trigger; unchanged for many releases.
- `proclang.c` is tiny and untouched for years. `#ifdef NOT_USED` block
  has been there since superuser-only enforcement was added.
