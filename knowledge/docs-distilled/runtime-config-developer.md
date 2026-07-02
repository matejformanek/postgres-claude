---
source_url: https://www.postgresql.org/docs/current/runtime-config-developer.html
fetched_at: 2026-07-02T20:47:00Z
anchor_sha: b542d5566705
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Developer Options (§20.17)

The single most hacker-relevant GUC page: the debugging / corruption-recovery /
cassert-only knobs a backend developer reaches for. Companion skills:
`debugging`, `wal-and-xlog`, `locking`, `gucs-config`.

## WAL-redo bug hunting: `wal_consistency_checking`

- **`wal_consistency_checking` (string, default `''`, SUSET)** adds full-page
  images to WAL records and, on replay, verifies the modified buffers match the
  stored images — a **fatal error** on any unexpected difference (hint-bit-style
  acceptable variations are masked out). This is *the* tool for catching bugs in
  redo routines. Supported rmgrs: `heap, heap2, btree, hash, gin, gist,
  sequence, spgist, brin, generic` (or `all`). Production-safe to enable but
  bloats WAL and slows replay. [from-docs]

## Corruption-recovery last resorts (all trade correctness for availability)

- **`ignore_checksum_failure` (bool, default `off`, SUSET)** — with checksums
  on (`initdb -k`), a checksum failure normally aborts the current transaction;
  this downgrades it to a WARNING and reads on. **Header corruption still aborts
  regardless.** May crash / propagate / hide corruption. [from-docs]
- **`zero_damaged_pages` (bool, default `off`, SUSET)** — a detected-invalid
  page header normally errors and aborts; this zeroes the page **in memory**
  (destroying every row on it) and continues. Zeroed pages are NOT forced to
  disk, so recreate the table/index afterward. Irreversible data loss by
  design. [from-docs]
- **`ignore_invalid_pages` (bool, default `off`, POSTMASTER/restart)** — during
  recovery/standby, a WAL record referencing an invalid page normally PANICs;
  this logs a warning and skips it, letting recovery complete. May crash / lose
  data / hide corruption. [from-docs]
- **`ignore_system_indexes` (bool, off, cannot change after session start)** —
  reads of system catalogs bypass their indexes (updates still maintain them),
  so you can limp along with a damaged system index before `REINDEX SYSTEM`.
  [from-docs]

## Pinpointing an error's origin: `backtrace_functions`

- **`backtrace_functions` (string, default `''`, SUSET)** — comma-separated C
  function names; if an error/log message is raised **in** one of them, a
  backtrace is written to the server log. The go-to for "which call site emits
  this ereport?" without a debugger. Backtrace quality is
  platform/compilation-dependent. [from-docs]

## The cassert-only node/cache testing knobs

These require a build flag that `--enable-cassert` turns on; on a production
build they are forced to their default and attempting to change them errors.

- **`debug_discard_caches` (int, default `0`)** — the modern name for
  CLOBBER_CACHE_ALWAYS. `1` invalidates every catalog cache entry at the first
  opportunity; higher values recurse. Runs at glacial speed; exposes bugs where
  code holds a cache pointer across a possible invalidation. Requires
  `DISCARD_CACHES_ENABLED` (auto with cassert). [from-docs]
- **`debug_copy_parse_plan_trees`** — forces every parse/plan tree through
  `copyObject()` to catch missing copy support for a node field. [from-docs]
- **`debug_write_read_parse_plan_trees`** — round-trips every tree through
  `outfuncs.c` → `readfuncs.c` to catch missing out/read support. [from-docs]
- **`debug_raw_expression_coverage_test`** — walks every DML raw parse tree via
  `raw_expression_tree_walker()` to catch a walker missing a node case. All
  three require `DEBUG_NODE_TESTS_ENABLED` (auto with cassert). These are
  exactly the gates a `parser-and-nodes` change must survive. [from-docs]

## Regression-test / parallel-forcing knobs

- **`debug_parallel_query` (enum, default `off`)** — `on` forces a `Gather`
  atop every query that could run parallel (even with no benefit), exercising
  the parallel-context restrictions; `regress` additionally suppresses
  context-line and `Gather` output so plans match the expected files. Functions
  that misbehave under it are mismarked `PARALLEL {UNSAFE,RESTRICTED}`. This is
  the knob the regress suite flips to shake out parallel-safety bugs.
  [from-docs]
- **`debug_logical_replication_streaming` (enum, default `buffered`, SUSET)** —
  `immediate` streams each change per WAL record instead of waiting for
  `logical_decoding_work_mem`; on the subscriber with `streaming=parallel`,
  `immediate` serializes to files. Test knob for large-txn logical decoding.
  [from-docs]

## Lock-tracing (require `LOCK_DEBUG` compile flag)

- **`trace_locks` / `trace_lwlocks` / `trace_userlocks` (bool, off)** — dump
  heavyweight / LWLock / advisory-lock state transitions (`LockAcquire`,
  `GrantLock`, `UnGrantLock`, `CleanUpLock`). Extremely verbose. [from-docs]
- **`trace_lock_oidmin` (int)** — skip tracing for OIDs below this (mute system
  tables); **`trace_lock_table` (int)** — unconditionally trace one relation's
  OID. **`debug_deadlocks` (bool)** — on deadlock timeout dump all lock state.
  These are the `locking`-skill debug surface. [from-docs]

## Debugger-attach windows + crash cores

- **`pre_auth_delay` / `post_auth_delay` (int seconds, 0)** — sleep a forked
  backend before / after authentication so you can `gdb -p` it. `pre_auth_delay`
  is config-file/command-line only; both un-`SET`-able mid-session. The clean
  answer to the per-connection fork-model attach problem the `debugging` skill
  documents. [from-docs]
- **`send_abort_for_crash` / `send_abort_for_kill` (bool, off, POSTMASTER)** —
  make the postmaster signal `SIGABRT` (instead of `SIGQUIT` on crash, or
  `SIGKILL` on a stuck-child kill) so every child dumps core. Cores accumulate;
  clean up manually. [from-docs]
- **`remove_temp_files_after_crash` (bool, default `on`, SIGHUP)** — `off`
  keeps a crashed backend's temp files for autopsy (they pile up on repeated
  crashes). [from-docs]

## JIT / I/O developer knobs

- **`jit_debugging_support` / `jit_profiling_support` (bool, off, session-start
  only)** — register JIT functions with GDB / emit `perf` data to `~/.debug/jit/`
  (needs LLVM). **`jit_dump_bitcode` (bool, off, SUSET)** writes LLVM IR into
  `data_directory`. **`jit_expressions` / `jit_tuple_deforming` (bool, on)**
  toggle the two JIT code-gen paths. [from-docs]
- **`debug_io_direct` (string, default `''`, POSTMASTER)** — `data`, `wal`,
  `wal_init` (comma-separated) use `O_DIRECT`/`F_NOCACHE`/`FILE_FLAG_NO_BUFFERING`
  to bypass the kernel page cache. **Currently usually *reduces* performance**;
  a developer/AIO-testing knob, and may be rejected at startup if the FS lacks
  support. [from-docs]
- **`allow_in_place_tablespaces` (bool, off, SUSET)** — `CREATE TABLESPACE` with
  an empty location makes a directory directly under `pg_tblspc` (no symlink);
  for same-machine replication testing. Confuses backup tools. [from-docs]
- **`allow_system_table_mods` (bool, off, SUSET, superuser)** — permits
  structural DDL on system catalogs. Can cause irretrievable corruption; used to
  hand-hack the catalog in extremis. [from-docs]
- **`trace_notify` / `trace_sort` (bool, off)** — LISTEN/NOTIFY debug spew (needs
  `DEBUG1`+) / sort resource-usage lines. **`wal_debug`** (needs `WAL_DEBUG`),
  **`log_btree_build_stats`** (needs `BTREE_BUILD_STATS`) — compile-gated log
  spew. [from-docs]

## Links into corpus

- [[knowledge/docs-distilled/runtime-config-error-handling.md]] — sibling §20 GUC page.
- [[knowledge/docs-distilled/wal-reliability.md]] — checksums + full-page-write context for the recovery knobs.
- [[knowledge/subsystems/storage-lmgr.md]] — what `trace_locks` traces.
- [[knowledge/idioms/error-handling.md]] — `backtrace_functions` complements ereport.
- Skills: `debugging` (attach delays + backtrace), `wal-and-xlog`
  (`wal_consistency_checking`), `locking` (trace_* knobs), `parser-and-nodes`
  (the debug_*_parse_plan_trees node-test gates).

## Confidence note

All claims `[from-docs]` (Developer Options chapter, fetched 2026-07-02). A few
GucContext values the page renders imprecisely ("likely SUSET") are marked as
such in-line; the authoritative context lives in `guc_tables.c`. The cassert /
LOCK_DEBUG / WAL_DEBUG compile-flag gates are stated by the page and are the
reason these knobs error out on a stock production build.
