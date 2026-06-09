# Issues — `src/include/executor`

Per-subsystem issue register for the **executor header layer** — SPI, parallel-executor support, async, hash join, instrumentation. 8 headers / ~11 entries surfaced 2026-06-09 by A15-3.

**Parent docs:** `knowledge/files/src/include/executor/*` (28 docs total).

## Headlines

1. **🚨 `spi.h` is THE canonical text-to-SQL injection sink in the corpus** — joins the A9/A10/A13 cluster (plpgsql EXECUTE + plperl/plpython/pltcl + tablefunc.connectby_text). Six functions take TEXT and execute SQL; six take prepared plan + Datum args. Header gives zero guidance steering callers to the safe family. Privilege/search_path inheritance under SECURITY DEFINER invisible at header layer.
2. **`execParallel.h` workers inherit leader's user identity, search_path, SecurityRestrictionContext, snapshot, PARAM_EXEC values** — whole security envelope rests on parallel-safe/restricted function labels being honest.
3. **`tqueue.h` text-fallback path runs type-output funcs in worker** — combined with mis-labeled parallel-safe types this leaks session state across worker/leader.
4. **`execAsync.h` is the FDW path most prone to connection-cache reuse mishaps** under role/UM changes (A11 echo).
5. **`hashjoin.h` spill files inherit `sharedtuplestore` posture** — column data on disk in clear (UID-cross-process readable).

## Entries

- [ISSUE-security: spi.h text-input family is classic SQL-injection surface inside SECURITY DEFINER C funcs (likely, A9/A10/A13 cluster headline)] — `spi.h:111-141, 174-185`
- [ISSUE-api-shape: spi.h `read_only=true` is a promise, not a check — mislabeled side-effect call silently mis-caches plan (maybe)] — `spi.h`
- [ISSUE-documentation: spi.h privilege/search_path inheritance invisible from header (maybe)] — `spi.h`
- [ISSUE-security: tqueue text-fallback runs type-output funcs in worker; mis-labeled parallel-safe types leak session state (maybe)] — `tqueue.h`
- [ISSUE-security: execAsync FDW path prone to connection-cache reuse mishaps under role/UM changes (maybe, A11 echo)] — `execAsync.h`
- [ISSUE-security: execParallel workers inherit leader user identity / search_path / SecurityRestrictionContext / snapshot / PARAM_EXEC; relies on parallel-safe labels being honest (likely)] — `execParallel.h`
- [ISSUE-documentation: execParallel.h gives no entry point to "what is sent to a worker" (maybe)] — `execParallel.h`
- [ISSUE-api-shape: hashjoin.h adding a PHJ barrier-phase requires touching all participant codepaths + rmgrdesc + explain (maybe)] — `hashjoin.h:279-307`
- [ISSUE-security: hashjoin spill files inherit sharedtuplestore posture — column data on disk in clear (maybe)] — `hashjoin.h:358-360`
- [ISSUE-api-shape: instrument_node.h adding instrumentation kind requires 4 coordinated touches (struct + Shared*Info + DSM TOC key + EXPLAIN formatter) (nit)] — `instrument_node.h`
- [ISSUE-nit: execdebug.h printf-based macros bypass elog/log-line-prefix (nit, defaults off)] — `execdebug.h:4-6`

## Cross-sweep references

- A9 plpgsql `exec_stmt_dynexecute` + A10 plperl/plpython/pltcl SPI + A13 tablefunc.connectby_text = **5-sweep text-to-SPI injection sinks cluster** with spi.h as the API host.
- A11 postgres_fdw cross-cluster trust + execAsync — connection-cache reuse pattern.
- A11/A12 sharedtuplestore + hashjoin spill files = parallel-spill-on-disk-clear-text cluster.
