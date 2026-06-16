# `src/include/postmaster/datachecksum_state.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~54
- **Source:** `source/src/include/postmaster/datachecksum_state.h`

API for the **DataChecksumsWorker** background-worker pair that
enables/disables page checksums online (PG18-era feature). One
launcher coordinates per-database worker dispatch; a per-database
worker walks every relation, rewriting pages with valid checksums (or
clearing the page-level flag in the disable direction). A
ProcSignalBarrier is used so every backend sees the cluster-wide
state change in lockstep. [from-comment] [inferred]

## API / declarations

### Enums
- `DataChecksumsWorkerOperation { ENABLE_DATACHECKSUMS,
  DISABLE_DATACHECKSUMS }` — direction the worker is processing. [verified-by-code]
- `DataChecksumsWorkerResult { DATACHECKSUMSWORKER_SUCCESSFUL = 0,
  DATACHECKSUMSWORKER_ABORTED, DATACHECKSUMSWORKER_FAILED,
  DATACHECKSUMSWORKER_DROPDB }` — outcome per database. Comment
  explicitly notes this is exported here so injection-point tests can
  reference it. [verified-by-code] [from-comment]

### Barrier API
- `AbsorbDataChecksumsBarrier(ProcSignalBarrierType barrier)` —
  invoked from a backend's barrier-absorption path when the postmaster
  raises a "data checksums state changed" barrier; returns true on
  success. [verified-by-code] [inferred]
- `EmitAndWaitDataChecksumsBarrier(uint32 state)` — issue a
  ProcSignalBarrier carrying the new global state, then wait for
  every backend to absorb. [verified-by-code]

### Background-worker lifecycle
- `StartDataChecksumsWorkerLauncher(DataChecksumsWorkerOperation op,
  int cost_delay, int cost_limit)` — invoked from SQL (`pg_enable_
  data_checksums` / `pg_disable_data_checksums` style functions) to
  spawn the launcher with vacuum-style throttling. [verified-by-code]
- `DataChecksumsWorkerLauncherMain(Datum arg)` — bgw_main_arg
  entrypoint for the launcher. [verified-by-code]
- `DataChecksumsWorkerMain(Datum arg)` — bgw_main_arg entrypoint for
  per-database workers. [verified-by-code]

## Notable invariants / details

- The barrier type implied by `EmitAndWaitDataChecksumsBarrier` carries
  the new `state` as a `uint32` — packed enough to encode both the
  on/off flag and an in-progress indicator (so a backend can correctly
  treat a "becoming enabled" cluster: it must compute checksums when
  writing but tolerate zero checksums when reading). The exact bit
  layout lives in the implementation, not this header. [inferred]
  [ISSUE-undocumented-invariant: `state` payload of
  `EmitAndWaitDataChecksumsBarrier` has implicit format known only to
  caller and callee (nit)]
- The worker is a vacuum-style throttled scanner — `cost_delay` and
  `cost_limit` mirror autovacuum's GUCs. Long-running on large
  databases is expected. [inferred]
- `DATACHECKSUMSWORKER_DROPDB` is a distinct outcome (not failure)
  because the per-database worker may legitimately race with `DROP
  DATABASE`. [inferred]
- The header lives under `postmaster/` because the launcher is a
  postmaster-managed bgworker, even though the actual page work
  happens in regular backend contexts. [inferred]

## Potential issues

- Lines 40-41. The barrier functions take/return raw `uint32` /
  `ProcSignalBarrierType`. There is no documented contract for what
  values of `state` are legal at `EmitAndWaitDataChecksumsBarrier`
  call sites. An out-of-range value would be silently propagated to
  every backend. [verified-by-code]
  [ISSUE-api-shape: `state` parameter is `uint32` with no enum;
  legal values are implicit (maybe)]
- Lines 46-48. `StartDataChecksumsWorkerLauncher` is publicly
  declared but has no documented privilege requirement at this layer.
  The actual SQL-callable wrapper presumably restricts to superuser;
  if a third caller (e.g. an extension) used this directly without
  the wrapper, the throttling-bypass + cluster-wide-rewrite combo
  would be a privilege-elevation footgun. [unverified]
  [ISSUE-security: `StartDataChecksumsWorkerLauncher` exposes a
  cluster-wide rewrite primitive; doc string should pin the
  caller-side privilege contract (maybe)]
- Lines 21-25. `DataChecksumsWorkerOperation` has only enable/disable
  with no "verify-only" option. A read-only verification mode would
  be useful (currently the only ways to verify are amcheck and a full
  base backup). [inferred]
  [ISSUE-question: should there be a `VERIFY_DATACHECKSUMS` operation
  for an online integrity scan without rewriting? (nit)]
- Lines 30-37. The result enum starts at 0 with
  `DATACHECKSUMSWORKER_SUCCESSFUL` and grows; the only ABI commitment
  in the comment is that injection-point tests reference it. The
  values are not stored on disk or in WAL, so reordering is safe, but
  if a future test serializes the value it becomes an implicit ABI.
  [verified-by-code]
  [ISSUE-undocumented-invariant: enum ordinals are not currently
  serialized but may become so if tests start logging them (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-postmaster`](../../../../issues/include-postmaster.md)
<!-- issues:auto:end -->
