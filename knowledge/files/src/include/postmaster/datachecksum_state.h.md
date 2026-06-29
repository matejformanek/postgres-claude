# `src/include/postmaster/datachecksum_state.h`

- **Last verified commit:** `4abf411e2328`
- **Lines:** ~28
- **Source:** `source/src/include/postmaster/datachecksum_state.h`

> **AUDIT 2026-06-29 (MAJOR drift).** The `datachecksum_state.[ch]`
> cleanup cluster (`a4f02cab4b97` + `c48e7b2c8bd0` + `c008b7ea10a5` +
> `0edbf72f7683`, Heikki Linnakangas, in the `419ce13b7019..4abf411e2328`
> window) **gutted this header from ~54 to 28 lines.** Both enums
> (`DataChecksumsWorkerOperation`, `DataChecksumsWorkerResult`) and
> `StartDataChecksumsWorkerLauncher` are no longer declared here — they
> moved INTO `datachecksum_state.c` (the enums at `:280`/`:286`,
> `StartDataChecksumsWorkerLauncher` is now a `static` function at
> `:603`). The header now exposes only the four prototypes below.

API for the **DataChecksumsWorker** background-worker pair that
enables/disables page checksums online (PG18-era feature). One
launcher coordinates per-database worker dispatch; a per-database
worker walks every relation, rewriting pages with valid checksums (or
clearing the page-level flag in the disable direction). A
ProcSignalBarrier is used so every backend sees the cluster-wide
state change in lockstep. [from-comment] [inferred]

## API / declarations

The header `#include`s `storage/procsignal.h` (for
`ProcSignalBarrierType`) and declares exactly four prototypes.

### Barrier API
- `bool AbsorbDataChecksumsBarrier(ProcSignalBarrierType barrier)` —
  invoked from a backend's barrier-absorption path when the postmaster
  raises a "data checksums state changed" barrier; returns true on
  success. [verified-by-code] [inferred]
- `void EmitAndWaitDataChecksumsBarrier(uint32 state)` — issue a
  ProcSignalBarrier carrying the new global state, then wait for
  every backend to absorb. [verified-by-code]

### Background-worker lifecycle
- `void DataChecksumsWorkerLauncherMain(Datum arg)` — bgw_main_arg
  entrypoint for the launcher. [verified-by-code]
- `void DataChecksumsWorkerMain(Datum arg)` — bgw_main_arg entrypoint
  for per-database workers. [verified-by-code]

### No longer in this header (moved to `datachecksum_state.c`)
- The two enums `DataChecksumsWorkerOperation` (`{ ENABLE_DATACHECKSUMS,
  DISABLE_DATACHECKSUMS }`) and `DataChecksumsWorkerResult`
  (`{ DATACHECKSUMSWORKER_SUCCESSFUL = 0, ..._ABORTED, ..._FAILED,
  ..._DROPDB }`) are now defined privately in `datachecksum_state.c`
  (`:280` / `:286`). The cleanup cluster removed the "exported here so
  injection-point tests can reference it" comment along with the
  declarations. [verified-by-code]
- `StartDataChecksumsWorkerLauncher(op, cost_delay, cost_limit)` is now
  a `static` function in `datachecksum_state.c` (`:603`), called only
  by the in-file SQL wrappers `enable_data_checksums` /
  `disable_data_checksums`. It is no longer part of the public API.
  [verified-by-code]

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

- **`EmitAndWaitDataChecksumsBarrier(uint32 state)`.** The barrier
  functions take/return raw `uint32` / `ProcSignalBarrierType`. There
  is no documented contract for what values of `state` are legal at
  call sites; an out-of-range value would be silently propagated to
  every backend. (The legal transitions are enforced in
  `datachecksum_state.c`'s `checksum_barriers[9]` table, not here.)
  [verified-by-code]
  [ISSUE-api-shape: `state` parameter is `uint32` with no enum;
  legal values are implicit (maybe)]
- **`StartDataChecksumsWorkerLauncher` is no longer header-exposed.**
  The 2026-06-29 audit confirms the cleanup cluster made it `static`
  in `datachecksum_state.c`, so the prior privilege-elevation-footgun
  concern (a third caller bypassing the SQL wrapper) is now moot at the
  ABI level: only the in-file `enable/disable_data_checksums` wrappers
  reach it. [verified-by-code]
  [ISSUE-resolved: launcher entry no longer publicly callable]
- **`DataChecksumsWorkerOperation` (now in `.c`)** has only
  enable/disable with no "verify-only" option. A read-only verification
  mode would be useful (currently the only ways to verify are amcheck
  and a full base backup). [inferred]
  [ISSUE-question: should there be a `VERIFY_DATACHECKSUMS` operation
  for an online integrity scan without rewriting? (nit)]
- **`DataChecksumsWorkerResult` ABI (now in `.c`).** The result enum
  starts at 0 with `DATACHECKSUMSWORKER_SUCCESSFUL` and grows; values
  are not stored on disk or in WAL, so reordering is safe. With the
  enum no longer exported from the header, the prior "injection-point
  tests reference it" ABI note no longer applies at this layer.
  [verified-by-code]
  [ISSUE-undocumented-invariant: enum ordinals are not serialized (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-postmaster`](../../../../issues/include-postmaster.md)
<!-- issues:auto:end -->
