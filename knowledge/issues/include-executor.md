# Issues — `src/include/executor`

Per-subsystem issue register for the **executor header layer** — SPI, parallel-executor support, async, hash join, instrumentation, + all 33 `nodeXxx.h` plan-node decl headers. 41 headers / ~22 entries surfaced 2026-06-09 by A15-3 + A17-4.

**Parent docs:** `knowledge/files/src/include/executor/*` (61 docs total — full coverage after A17).

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

## Entries — A17-4 (`nodeXxx.h` plan-node decl headers, 33 files)

The 33 `nodeXxx.h` headers are mostly thin 3-decl files (`Exec<Node>`, `ExecInit<Node>`, `ExecEnd<Node>`). Phase D content concentrates in the extension-surface + parallel-aware + privileged-data-handling nodes.

- [ISSUE-security: Custom-scan extension surface is unsandboxed function-pointer dispatch — `CustomExecMethods` vtable runs with full backend privilege (likely)] — `nodeCustom.h:21` — third-party scan providers (Citus, Timescale, Hydra, pg_strom); supply-chain compromise yields backend RCE.
- [ISSUE-security: ForeignScan async path mixes credential-bearing remote connections with executor reentrancy; connection cache may reuse prior role's session (likely, A11 echo)] — `nodeForeignscan.h:34`
- [ISSUE-security: Gather/GatherMerge inherit leader's auth context into workers via ParallelContext serialization (maybe, A15 echo)] — `nodeGather.h:19`
- [ISSUE-resource: GatherMerge leader holds tuples from every worker queue — back-pressure asymmetry under high max_parallel_workers_per_gather (nit)] — `nodeGatherMerge.h:19`
- [ISSUE-resource: Memoize result-cache is simplehash keyed on parameter values — adversarial keys hash-flood into O(n) lookups (maybe, A11 echo)] — `nodeMemoize.h:20`
- [ISSUE-security: TableFuncScan drives XMLTABLE through libxml2 on user input — XXE / DTD-bomb / billion-laughs surface (likely, A7 echo)] — `nodeTableFuncscan.h:19`
- [ISSUE-security: SampleScan dispatches into TsmRoutine vtable from any installed TSM method (maybe, A14 echo)] — `nodeSamplescan.h:19`
- [ISSUE-correctness: LockRows holds tuple locks that pin catalog_xmin via FOR KEY SHARE (nit, A8 echo)] — `nodeLockRows.h:19`
- [ISSUE-security: FunctionScan invokes any user-callable SRF via FROM-clause (nit, A14 tablefunc echo)] — `nodeFunctionscan.h:19`
- [ISSUE-api-shape: BitmapHeapScan / SeqScan / IndexOnlyScan / TidRangeScan share a dual-track DSM-init pattern inconsistently applied across other parallel-aware nodes (nit, architectural)] — `nodeBitmapHeapscan.h:31`
- [ISSUE-api-shape: NamedTuplestoreScan, ValuesScan, WorkTableScan lack ExecEnd* decls (nit)] — `nodeNamedtuplestorescan.h:19`

### Honest note

The remaining 22 `nodeXxx.h` headers (BitmapAnd, BitmapOr, BitmapIndexscan, Ctescan, Group, IncrementalSort, IndexonlyScan, Limit, Material, MergeAppend, Nestloop, ProjectSet, Recursiveunion, Result, Seqscan, SetOp, Subqueryscan, TidRangeScan, Tidscan, Unique, Valuesscan, Worktablescan) are zero-issue mechanical 3-decl files. Documented for completeness; no Phase-D surface flagged.
