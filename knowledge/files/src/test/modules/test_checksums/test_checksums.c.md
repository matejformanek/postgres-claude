---
path: src/test/modules/test_checksums/test_checksums.c
anchor_sha: e18b0cb7344
loc: 105
depth: read
---

# src/test/modules/test_checksums/test_checksums.c

## Purpose

Test scaffolding for the **online data-checksum enable/disable** machinery
(`src/backend/postmaster/datachecksumsworker.c` and friends). It does NOT test
the CRC32C math directly — instead it injects timing perturbations into the
checksum-state-transition path via the `USE_INJECTION_POINTS` framework so TAP
tests can race the worker against concurrent backends, signal handlers, and
procsignal barriers. The single hook (`dc_delay_barrier`) sleeps 3 s on a latch,
holding up whichever phase of the checksum worker is wired to it.
`[from-comment]` `test_checksums.c:3-4,26-28`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void dc_delay_barrier(name, private_data, arg)` | `:30` | Injection-point callback; `WaitLatch(WL_TIMEOUT | WL_EXIT_ON_PM_DEATH, 3000 ms, WAIT_EVENT_PG_SLEEP)`. Exported `PGDLLEXPORT` so the injection-point loader can dlsym it |
| `dcw_inject_delay_barrier(bool attach)` | `:43` | Attach/detach `dc_delay_barrier` to injection point `"datachecksums-enable-checksums-delay"` |
| `dcw_inject_launcher_delay(bool attach)` | `:65` | Attach/detach to `"datachecksumsworker-launcher-delay"` |
| `dcw_inject_startup_delay(bool attach)` | `:87` | Attach/detach to `"datachecksumsworker-startup-delay"` |

No `_PG_init`; no GUCs; no static state. The injection-point framework owns
the registration table.

## Internal landmarks

- The three SQL functions are near-identical copies differing only in the
  injection-point name string — the three correspond to three distinct phases
  of the checksum-enable state machine (procsignal-barrier emission, launcher
  startup, per-database worker startup) `[verified-by-code]` `:49,71,93`.
- Each function is `#ifdef USE_INJECTION_POINTS`-gated and `elog(ERROR, ...)`s
  if the build omitted injection-point support (`:57-58`) — fail-loud, not
  silent skip.
- Latch wait flags include `WL_EXIT_ON_PM_DEATH` (`:36`) so a postmaster crash
  during the artificial delay still tears the backend down cleanly.

## Invariants & gotchas

- **TEST MODULE — never load in production.** The whole point is to stall
  critical worker transitions for seconds at a time.
- Requires `./configure --enable-injection-points` (and `shared_preload_libraries`
  if the TAP harness expects the callback resolvable at process start). Without
  it, every SQL entry point ERRORs.
- The callback signature `(name, private_data, arg)` is the injection-point ABI
  in `utils/injection_point.h` — changing it here without changing the framework
  breaks loadability silently at dlsym time.
- Tests catch races in the data-checksum enable path: procsignal-barrier
  acknowledgement, worker-launcher start, per-DB worker startup. Failure modes
  caught are "transition completes before backend acks barrier" and
  "worker exits before launcher records its pid".

## Cross-refs

- `knowledge/files/src/include/postmaster/datachecksum_state.h.md` — the state
  machine being exercised.
- `knowledge/files/src/backend/postmaster/datachecksumsworker.c.md` — the
  production worker harboring the three injection points.
- `knowledge/files/src/include/utils/injection_point.h.md` — the
  `InjectionPointAttach / InjectionPointDetach` API.
- `knowledge/subsystems/wal-and-xlog.md` — the broader checksum subsystem
  (page-level CRC32C) lives here even though this module exercises only the
  transition orchestration.
