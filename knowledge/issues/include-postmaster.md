# Issues — `include-postmaster`

Per-subsystem issue register for `src/include/postmaster/*` headers — the
postmaster-owned background-worker entrypoints, fork wrappers, and the PG18
DataChecksumsWorker control surface.

See `knowledge/issues/README.md` for the tag convention, severity scale, and
workflow.

**Parent subsystem doc:** none synthesized yet; per-file docs live under
`knowledge/files/src/include/postmaster/*.h.md`.

**Sibling registers:** `knowledge/issues/include-storage.md` (storage-core
headers including the data-checksum *barrier* and `subsystemlist` machinery
this subsystem hooks into).

## Headlines

1. **`datachecksum_state.h` is the PG18 online checksum-rewrite control
   surface** — implicit `uint32` state payload on the
   `EmitAndWaitDataChecksumsBarrier`, no privilege contract documented at
   the header layer, and no read-only "verify" mode (today's verification
   is amcheck + base-backup only).
2. **`fork_process.h` is a one-liner** with no documented guidance on when
   it's the right entry point vs `internal_forkexec` vs the bgworker
   machinery — a frequent question for new contributors.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | `src/include/postmaster/datachecksum_state.h:40-41` | undocumented-invariant | nit | `state` payload of `EmitAndWaitDataChecksumsBarrier` is `uint32` with implicit format known only to caller and callee | open | `files/src/include/postmaster/datachecksum_state.h.md` §Potential issues |
| 2026-06-11 | `src/include/postmaster/datachecksum_state.h:40-41` | api-shape | maybe | `state` parameter is a raw `uint32` with no enum; legal values are implicit, out-of-range value would propagate silently | open | same |
| 2026-06-11 | `src/include/postmaster/datachecksum_state.h:46-48` | security | maybe | `StartDataChecksumsWorkerLauncher` exposes a cluster-wide rewrite primitive at the header layer with no documented privilege contract | open | same |
| 2026-06-11 | `src/include/postmaster/datachecksum_state.h:21-25` | question | nit | should there be a `VERIFY_DATACHECKSUMS` operation for an online integrity scan without rewriting? | open | same |
| 2026-06-11 | `src/include/postmaster/datachecksum_state.h:30-37` | undocumented-invariant | nit | result enum ordinals are not currently serialized but may become so if injection-point tests start logging them | open | same |
| 2026-06-11 | `src/include/postmaster/fork_process.h:15` | api-shape | nit | lack of `PGDLLIMPORT` is intentional but undocumented; extensions on Windows hit a confusing link error | open | `files/src/include/postmaster/fork_process.h.md` §Potential issues |
| 2026-06-11 | `src/include/postmaster/fork_process.h` | doc-drift | nit | header lacks any guidance on when `fork_process` is the correct entry point vs `internal_forkexec` vs bgworker machinery | open | same |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|

## Notes

The data-checksum subsystem straddles three header layers — the **request-time
SQL interface** (a postmaster bgworker control plane, this file), the
**barrier dispatch** (`storage/procsignal.h`), and the **per-page checksum
algorithm** (`storage/checksum_impl.h`, `storage/checksum_block_internal.h`).
The header-level issues clustered here all stem from the inter-layer
contract being documented only at the implementation in
`src/backend/postmaster/datachecksumsworker.c` and
`src/backend/access/transam/xlog.c` — i.e. you have to read three .c files
to discover what `state` legally is.

The `fork_process.h` issues are documentation-only — the wrapper itself
predates the modern bgworker infrastructure and persists as an internal
helper for the postmaster's own child spawning.
