# `src/backend/commands/repack_worker.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~536
- **Source:** `source/src/backend/commands/repack_worker.c`

PG18+ (or unmerged feature-branch) addition: the background worker
side of `REPACK CONCURRENTLY`. Logical-decoding worker that runs in
parallel with the table copy, capturing concurrent INSERT/UPDATE/DELETE
on the table being repacked to a file-backed buffer the leader replays
onto the new heap. Distantly analogous to `pg_repack` extension's
trigger-based capture but uses logical decoding directly. [verified-by-code]

## API / entry points

- `RepackWorkerMain(main_arg)` — background-worker entry. Takes a
  `dsm_handle` in `main_arg`. Joins the lock group of the launching
  backend so heavyweight-lock conflicts don't deadlock, attaches to
  the leader's shared file set, creates a temporary logical
  replication slot named `pg_repack_<pid>`, exports the initial
  snapshot, then loops decoding WAL until told to stop. [verified-by-code]
- `AmRepackWorker(void)` — predicate used by callers (in main
  backend code) to short-circuit unrelated logic when running as a
  REPACK worker. [verified-by-code]
- `change_useless_for_repack(buf)` — called from logical-decoding
  hot path; returns true if a WAL record's block 0 RelFileLocator
  doesn't match either the repacked rel or its TOAST. Skips
  unrelated changes cheaply. [verified-by-code]

## Static helpers

- `RepackWorkerShutdown(code, arg)` — `before_shmem_exit` callback.
  Sends `PROCSIG_REPACK_MESSAGE` to the leader and detaches the DSM.
  [from-comment]
- `repack_setup_logical_decoding(relid)` — creates the slot
  (`RS_TEMPORARY`, so cleaned up on ERROR), calls
  `EnsureLogicalDecodingEnabled`, opens target rel + its TOAST to
  cache RelFileLocators for filtering, and builds a
  `LogicalDecodingContext` with `pgrepack` output plugin. Uses
  blocking `read_local_xlog_page` for the start-point search, then
  switches to non-blocking `read_local_xlog_page_no_wait` afterward.
  [from-comment]
- `repack_cleanup_logical_decoding(ctx)` — drops the slot
  (`ReplicationSlotDropAcquired(true)`) and frees the context.
- `export_initial_snapshot(snapshot, shared)` — serializes the
  snapshot to a fileset file, bumps `shared->last_exported`,
  signals the leader's CV.
- `decode_concurrent_changes(ctx, shared)` — main loop. Reads
  records, runs `LogicalDecodingProcessRecord`, on WAL-segment
  boundary calls `LogicalIncreaseRestartDecodingForSlot` +
  `LogicalConfirmReceivedLocation` so old WAL can recycle.
  Polls `shared->lsn_upto` for the stop point; if no record and no
  bound, blocks via `WaitForLSN(WAIT_LSN_TYPE_PRIMARY_FLUSH, ...)`
  with timeout to stay interruptible.

## Notable invariants / details

- Worker is REPEATABLE READ + read-only (lines 138-140). Comment
  notes "There doesn't seem to a nice API to set these". [from-comment]
- WAL retention: usual replication-slot careful LSN tracking is
  *disabled* — on crash the entire REPACK restarts from scratch, so
  it's safe to advance restart_decoding/confirmed_lsn aggressively
  on segment boundaries (lines 374-403). xmin is NOT advanced
  (would be bogus). [from-comment]
- File handoff: each decode round opens a `BufFile` on the leader's
  fileset, named via `DecodingWorkerFileName(fname, relid,
  last_exported + 1)`. After close, `last_exported` is incremented
  under the spinlock, CV signaled. The leader reads files in order.
- Filtering: `repacked_rel_locator` / `repacked_rel_toast_locator`
  are file-scope statics, set in `repack_setup_logical_decoding`.
  `change_useless_for_repack` early-returns false if not set
  (non-REPACK backends never filter). Uses block 0's tag as a
  proxy for INSERT/UPDATE/DELETE detection. [from-comment]
- `BackgroundWorkerInitializeConnectionByOid(..., BGWORKER_BYPASS_
  ROLELOGINCHECK)` (line 105-106) lets the worker connect as a
  no-LOGIN role.
- DSM `before_shmem_exit` shutdown handler runs `SendProcSignal`
  *before* the implicit detach inside the same callback (line 174-178),
  so the leader sees the signal while the DSM is still mapped.
- Spinlock-protected fields in `DecodingWorkerShared`: `lsn_upto`,
  `done`, `last_exported`, `initialized`. Lifecycle handshake uses
  the same `cv`. [verified-by-code]

## Potential issues

- Lines 117-123. "Not sure the spinlock is needed here" — comment
  acknowledges uncertainty about whether holding the mutex is
  needed before serializing the snapshot. [ISSUE-undocumented-invariant:
  snapshot-serialize ordering vs leader (maybe)]
- Lines 138-140. "There doesn't seem to a nice API to set these"
  for `XactIsoLevel`/`XactReadOnly` direct writes. Tech-debt smell.
  [ISSUE-style: API gap for xact-mode setup (nit)]
- Line 84 `before_shmem_exit(RepackWorkerShutdown, PointerGetDatum(
  shared))` — the callback's `arg` is a pointer into a DSM segment
  that the callback itself detaches. The ordering is `SendProcSignal`
  *then* `dsm_detach`, so `shared->backend_pid` is read before the
  unmap; correct but subtle. [ISSUE-correctness: DSM-shutdown
  ordering (maybe)]
- Line 90-91 `BecomeLockGroupMember` returns without cleanup if
  leader is gone. The CV and `last_exported` aren't reset; OK
  because the DSM goes away with the leader.
- `repack_current_segment` is a file-scope static. Initialized in
  setup; reset implicitly by process exit. Fine for the
  one-REPACK-per-backend rule.

## Synthesized by
<!-- backlinks:auto -->
