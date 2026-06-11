# Issues — `replication`

Per-subsystem issue register for `src/backend/replication/`. See
`knowledge/issues/README.md` for the tag convention, severity scale,
and workflow.

**Parent subsystem docs:**
- `knowledge/subsystems/replication.md` (if/when authored)
- `knowledge/files/src/backend/replication/` (per-file)
- `knowledge/issues/include-replication.md` (header-side findings)

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | replication/libpqwalreceiver/libpqwalreceiver.c:152 | style | nit | Fixed-size `keys[6]/vals[6]` libpq param array sized just right for current call sites; future addition silently overflows if array isn't grown | open | knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md §Potential issues |
| 2026-06-11 | replication/libpqwalreceiver/libpqwalreceiver.c:256 | undocumented-invariant | maybe | `ALWAYS_SECURE_SEARCH_PATH_SQL` runs only for non-replication or logical connections; a future feature running SQL on a physical replication conn would inherit unsafe search path | open | knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md §Potential issues |
| 2026-06-11 | replication/libpqwalreceiver/libpqwalreceiver.c:239 | question | nit | `must_use_password` check runs after `CONNECTION_OK`; tiny window where conn is open before disconnect; harmless in practice but worth noting for cert/peer auth contexts | open | knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md §Potential issues |
| 2026-06-11 | replication/libpqwalreceiver/libpqwalreceiver.c:197 | undocumented-invariant | nit | Logical-replication forced options (`datestyle=ISO -c intervalstyle=postgres -c extra_float_digits=3`) are concatenated AFTER user-supplied `options` so forced trio overrides any user setting; intentional but not commented inline | open | knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md §Potential issues |
| 2026-06-11 | replication/libpqwalreceiver/libpqwalreceiver.c:40 | question | maybe | `PG_MODULE_MAGIC_EXT(.name, .version)` is a PG18 macro; binary compat with module loaders rebuilding against older PG sources is worth verifying | open | knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md §Potential issues |
| 2026-06-11 | replication/pgrepack/pgrepack.c:176 | undocumented-invariant | maybe | TRUNCATE-vs-REPACK protection relies entirely on a comment-only `AccessExclusiveLock` assumption; if TRUNCATE's lock level were ever relaxed, `Assert(false)` fires in cassert builds and silently misses the change otherwise | open | knowledge/files/src/backend/replication/pgrepack/pgrepack.c.md §Potential issues |
| 2026-06-11 | replication/pgrepack/pgrepack.c:64 | question | nit | `dstate->change_cxt` cleanup path crosses into `commands/repack.c`; no matching `MemoryContextDelete` visible in this file | open | knowledge/files/src/backend/replication/pgrepack/pgrepack.c.md §Potential issues |
| 2026-06-11 | replication/pgrepack/pgrepack.c | question | maybe | REPACK's data-snapshot pinning is NOT in this file; lives in `commands/repack.c` + `replication/snapbuild.c`. Worth cross-checking when reviewing the PG18 REPACK commit | open | knowledge/files/src/backend/replication/pgrepack/pgrepack.c.md §Potential issues |

## Wontfix / Submitted / Landed

| Date | File:line | Type | Summary | Status | Resolution |
|---|---|---|---|---|---|
| | | | | | |

## Notes

- **libpqwalreceiver.c** is the auth surface for every replication
  connection plus logical-replication subscriptions plus slot sync.
  The `must_use_password` + `ALWAYS_SECURE_SEARCH_PATH_SQL`
  combination is the primary defence against subscription-owner
  privilege escalation; both have known limitations
  (must_use_password only catches the no-password-prompted-at-all
  case, search-path lockdown skips physical conns).
- **pgrepack.c** is small (~305 lines) but load-bearing for PG18
  REPACK CONCURRENTLY correctness. The plugin itself does only
  the spill-format work; the snapshot management and final
  rewrite happen in `commands/repack.c` via the
  `RepackDecodingState` shared with the worker. A
  cross-file invariant doc for REPACK would be valuable.
- Open architectural question across the subsystem: there's
  conceptual overlap between
  `replication/walreceiver.c` (physical), the
  logical-replication apply worker, and the new slot-sync worker
  — all three go through `libpqwalreceiver.c` for their libpq
  conn but each layers different invariants on top. The lack of a
  unifying subsystem doc means new contributors keep reinventing
  the connection-setup invariants.
