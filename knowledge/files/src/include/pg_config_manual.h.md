# `src/include/pg_config_manual.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~368
- **Source:** `source/src/include/pg_config_manual.h`

Manually-set build-time configuration symbols and limits. Included
by `c.h` immediately after `pg_config.h` (`c.h:58`). The preface
warns: "changing them is only useful in very rare situations or for
developers. If you edit any of these, be sure to do a *full* rebuild
(and an initdb if noted)" (`pg_config_manual.h:3-7`).
[from-comment]

The file mixes (a) hard limits readers must respect (NAMEDATALEN,
FUNC_MAX_ARGS, INDEX_MAX_KEYS, MAXPGPATH, BLCKSZ-via-pg_config_…),
(b) defaults (DEFAULT_XLOG_SEG_SIZE, DEFAULT_BACKEND_FLUSH_AFTER),
(c) compile-time feature toggles (USE_VALGRIND, USE_SSL,
MEMORY_CONTEXT_CHECKING, RANDOMIZE_ALLOCATED_MEMORY), and (d) debug
prints (LOCK_DEBUG, WAL_DEBUG, TRACE_SYNCSCAN).

## API / declarations

### initdb-affecting limits

- `DEFAULT_XLOG_SEG_SIZE = 16 MiB` (`pg_config_manual.h:20`) — default
  `wal_segment_size`. Must be a valid segment size.
- `SLRU_PAGES_PER_SEGMENT = 32` (`pg_config_manual.h:30`) — 256 KB
  segments. "Changing this requires an initdb."
- `NAMEDATALEN = 64` (`pg_config_manual.h:39`) — max identifier
  length (incl. trailing NUL). "Changing this requires an initdb."
- `INDEX_MAX_KEYS = 32` (`pg_config_manual.h:79`) — initdb required.
- `PARTITION_MAX_KEYS = 32` (`pg_config_manual.h:84`).

### Recompile-only limits

- `FUNC_MAX_ARGS = 100` (`pg_config_manual.h:53`) — min 8 (GIN
  needs it), max ~600 (bounded by pg_proc index tuple size at
  default BLCKSZ). Does NOT need initdb, but requires full backend
  recompile including any user-defined C functions.
- `FMGR_ABI_EXTRA = "PostgreSQL"` (`pg_config_manual.h:70`) — 32-byte
  string in module-magic block; forks change this for ABI-incompat
  detection.
- `USE_FLOAT8_BYVAL = 1` (`pg_config_manual.h:92`) — vestigial;
  built-in 8-byte types now always pass-by-value.
- `MAXPGPATH = 1024` (`pg_config_manual.h:105`) — buffer size for
  pathnames.
- `BITS_PER_BYTE = 8` (`pg_config_manual.h:111`) — "try changing if
  you have a machine with bytes of another size, but no guarantee".
- `ALIGNOF_BUFFER = 32` (`pg_config_manual.h:119`) — preferred disk
  I/O buffer alignment.

### Platform / feature gates

- `EXEC_BACKEND` (`pg_config_manual.h:130-132`) — auto-defined on
  Windows. Forks postmaster via fork+exec instead of plain fork.
- `USE_POSIX_FADVISE` (`pg_config_manual.h:140-142`) — when libc has it.
- `USE_PREFETCH` (`pg_config_manual.h:150-152`) — gated on POSIX
  fadvise.
- `DEFAULT_BACKEND_FLUSH_AFTER = 0` /
  `DEFAULT_BGWRITER_FLUSH_AFTER = 64` /
  `DEFAULT_CHECKPOINT_FLUSH_AFTER = 32` — only when
  `HAVE_SYNC_FILE_RANGE`.
- `WRITEBACK_MAX_PENDING_FLUSHES = 256`.
- `USE_SSL` (`pg_config_manual.h:176-178`) — auto-defined on USE_OPENSSL.
- `DEFAULT_PGSOCKET_DIR = "/tmp"` (Unix) / `""` (Windows) — comment
  warns "Caution: changing this risks breaking your existing client
  applications" (`pg_config_manual.h:181-186`).
- `DEFAULT_EVENT_SOURCE = "PostgreSQL"` — Windows event log name.
- `PG_CACHE_LINE_SIZE = 128` (`pg_config_manual.h:217`) — for
  cache-aligned struct padding. "Default is 128, which should be
  large enough for all supported platforms."
- `PG_IO_ALIGN_SIZE = 4096` (`pg_config_manual.h:223`) — direct I/O
  alignment.

### Debug-build toggles

Commented-out by default; uncomment for diagnostic builds:
- `FORCE_JSON_PSTACK` — force non-recursive JSON parser.
- `USE_VALGRIND` (`pg_config_manual.h:261`) — Valgrind client
  requests in memcontext allocator. Critical caveat: "Do not try to
  test the server under Valgrind without having built the server
  with USE_VALGRIND; else you will get false positives from sinval
  messaging". Use with `MEMORY_CONTEXT_CHECKING`.
- `CLOBBER_FREED_MEMORY` (`pg_config_manual.h:268-270`) — auto-defined
  under cassert. pfree'd memory cleared immediately.
- `MEMORY_CONTEXT_CHECKING` (`pg_config_manual.h:277-279`) —
  auto-defined under cassert OR USE_VALGRIND. Sentinel-byte overflow
  checks.
- `RANDOMIZE_ALLOCATED_MEMORY` — palloc'd memory filled with random
  data. "horrendously expensive". Catches uninit reads.
- `DISCARD_CACHES_ENABLED` (`pg_config_manual.h:300-312`) —
  auto-defined under cassert. Enables `debug_discard_caches` GUC.
- `RECOVER_RELATION_BUILD_MEMORY` (`pg_config_manual.h:314-325`) —
  three-way: define as 0/1 or leave undefined (use cassert default).
- `DEBUG_NODE_TESTS_ENABLED` (`pg_config_manual.h:328-339`) —
  auto-defined under cassert. Enables debug_copy_parse_plan_trees /
  debug_write_read_parse_plan_trees / debug_raw_expression_coverage_test
  GUCs.
- `REALLOCATE_BITMAPSETS` — find dangling Bitmapset pointers.
- `LOCK_DEBUG` (`pg_config_manual.h:357`) — debug-print lock
  operations.
- `WAL_DEBUG` (`pg_config_manual.h:363`) — pair with `wal_debug` GUC.
- `TRACE_SYNCSCAN` (`pg_config_manual.h:368`) — pair with
  `trace_syncscan` GUC.

## Notable invariants / details

- The auto-enabling chain under `USE_ASSERT_CHECKING` is
  load-bearing: cassert → CLOBBER_FREED_MEMORY,
  MEMORY_CONTEXT_CHECKING, DISCARD_CACHES_ENABLED,
  DEBUG_NODE_TESTS_ENABLED. A non-cassert build that wants any of
  these must define them explicitly. [verified-by-code]
- `NAMEDATALEN` is the single most-cited initdb-affecting constant —
  it sets the size of `NameData` (c.h:829-832) and every
  `pg_class.relname`-style catalog column. Changing it post-initdb
  → catalog corruption. [from-comment]
- `FUNC_MAX_ARGS = 100` is exposed via `PG_MODULE_ABI_DATA`
  (fmgr.h:489-497); extensions compiled with a different value
  are rejected at load. [verified-by-code]
- `FMGR_ABI_EXTRA` must be ≤ 32 bytes; StaticAssertDecl at
  `fmgr.h:510` enforces. Forks should change this to a recognizable
  string. [from-comment]
- `EXEC_BACKEND` automatically on Windows; manual `--enable-exec-backend`
  on Unix is for testing the EXEC_BACKEND code paths only.
- `USE_VALGRIND` requires `MEMORY_CONTEXT_CHECKING` for full
  coverage of repalloc; without it instrumentation is "inferior"
  (`pg_config_manual.h:258-260`). [from-comment]
- `RANDOMIZE_ALLOCATED_MEMORY` is the canonical "find missing
  initialization" debug switch. It significantly slows the backend;
  CI rarely runs it. [inferred]
- `DISCARD_CACHES_ENABLED` is the modern replacement for the
  pre-12 `CLOBBER_CACHE_ALWAYS` / `CLOBBER_CACHE_RECURSIVELY`
  macros (`pg_config_manual.h:308-312`). Old custom builds with
  these still work via the backward-compat shim.
- `MAXPGPATH = 1024` — many code paths use `char buf[MAXPGPATH]`;
  paths longer than 1023 bytes are silently truncated by `strlcpy`.
  Linux's `PATH_MAX = 4096`, so deep nesting is technically
  representable but PG won't handle it.
  [ISSUE-correctness: MAXPGPATH = 1024 < Linux PATH_MAX = 4096
  silently truncates long paths (likely)]
- `PG_CACHE_LINE_SIZE = 128` — over-padding compared to typical
  64-byte cache lines on x86. The 2× over-estimate is intentional
  to handle Power9/Apple-silicon (128) and to be safe against
  L2 prefetcher pulling pairs of lines. [from-comment]
- `BITS_PER_BYTE = 8` is hard-coded; ports to exotic-byte-size
  machines aren't realistic. [verified-by-code]

## Potential issues

- `pg_config_manual.h:39` — NAMEDATALEN is hard-cap 64. Catalog
  identifiers are limited to 63 bytes + NUL. Extensions like
  Citus that prefix long namespaces routinely run into this.
  [ISSUE-api-shape: NAMEDATALEN = 64 is a hard limit for forks
  with long identifiers (likely)]
- `pg_config_manual.h:53` — FUNC_MAX_ARGS = 100 is exposed via ABI
  block; forks raising it can't load against stock-built backends.
  [ISSUE-api-shape: FUNC_MAX_ARGS in ABI block means forks need
  custom backend (nit)]
- `pg_config_manual.h:105` — MAXPGPATH = 1024 silently truncates
  long paths; no header-level Assert that paths fit.
  [ISSUE-correctness: MAXPGPATH = 1024 silently truncates (likely)]
- `pg_config_manual.h:181-201` — DEFAULT_PGSOCKET_DIR `"/tmp"`
  enables a known squatting hazard: any user on the system can
  create `/tmp/.s.PGSQL.5432` before postmaster startup and
  intercept connections. PG's permission check is part of the
  mitigation, but the default location is the issue.
  [ISSUE-security: DEFAULT_PGSOCKET_DIR `/tmp` is a known
  socket-squatting hazard (confirmed)]
- `pg_config_manual.h:217` — PG_CACHE_LINE_SIZE = 128 wastes some
  RAM on 64-byte-cache-line platforms but is hard-coded; tuning per
  platform would require configure-time detection.
  [ISSUE-stale-todo: PG_CACHE_LINE_SIZE could be configure-detected
  (nit)]
- `pg_config_manual.h:223` — PG_IO_ALIGN_SIZE = 4096 is hard-coded
  for 4K sectors. NVMe drives with 16K sector size silently lose
  alignment benefits. [ISSUE-correctness: PG_IO_ALIGN_SIZE = 4 KB
  may be insufficient for 16 KB sector NVMe (maybe)]
- `pg_config_manual.h:30` — SLRU_PAGES_PER_SEGMENT = 32 (256 KB) is
  fine for small CLOG but cramped for large multixact archives;
  bumping requires initdb. [ISSUE-stale-todo:
  SLRU_PAGES_PER_SEGMENT could be made GUC-tunable (likely)]
- `pg_config_manual.h:261-262` — USE_VALGRIND comment says "client
  requests fall in hot code paths, so USE_VALGRIND slows execution
  by a few percentage points even when not run under Valgrind".
  This makes Valgrind-enabled buildfarm animals slow CI.
  [ISSUE-stale-todo: VG client requests slow non-VG runs (nit)]
- `pg_config_manual.h:328-339` — DEBUG_NODE_TESTS_ENABLED auto-on
  under cassert means CI exercises copy/equal/out/read codecs
  redundantly for every parse tree. Performance regression
  unavoidable. [ISSUE-style: auto-enable hides perf cost (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../issues/include-misc.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/slru-page-replacement.md](../../../idioms/slru-page-replacement.md)
