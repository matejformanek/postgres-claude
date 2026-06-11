# Issue register — small `src/bin/` tools

Combined register for the smaller single-file utilities under
`src/bin/`. Sweep A20 bucket D, verified at `e18b0cb7344`.

Covers:

- `pg_archivecleanup/pg_archivecleanup.c`
- `pg_checksums/pg_checksums.c`
- `pg_config/pg_config.c`
- `pg_controldata/pg_controldata.c`
- `pg_test_fsync/pg_test_fsync.c`
- `pg_test_timing/pg_test_timing.c`
- `pg_walsummary/pg_walsummary.c`
- `pgevent/pgevent.c` (+ `pgmsgevent.h`)

`pgbench`, `pg_ctl`, `pg_resetwal`, `pg_verifybackup` have their own
registers.

## pg_checksums

- **No concurrent-postmaster guard** — `pg_checksums.c:580-586`.
  Only `ControlFile->state` is consulted; an operator who starts the
  postmaster mid-run races with our writes. (likely)

- **Skip-list is a prefix-only match** — `pg_checksums.c:321`. If PG
  ever introduces a non-temp file beginning with `PG_TEMP_FILE_PREFIX`
  it is silently skipped. (nit)

- **Skip list duplicates `basebackup.c`** — `pg_checksums.c:108-117`.
  Drift risk if backup logic adds/removes excluded files. (nit)

- **`RELSEG_SIZE` baked at build time** — `pg_checksums.c:226`. No
  on-disk validation that the cluster shares the build-time value
  (block size IS validated). (nit)

## pg_controldata

- **Version mismatch produces warning, continues interpreting bytes** —
  `pg_controldata.c:170-176`. If struct layout shifted, subsequent
  prints read arbitrary memory. The warning is the only safety net.
  (maybe)

- **Weak `WalSegSz` validation** — `pg_controldata.c:230-239`. `> 0`
  accepted; a small positive value divides cleanly and yields a
  misleading WAL filename. (nit)

- **`dbState` unrecognized-status message omits the numeric value** —
  `pg_controldata.c:69`. Forensic value reduced. (nit)

## pg_archivecleanup

- **`readdir` errno discipline fragile if loop body grows** —
  `pg_archivecleanup.c:104`. POSIX-correct today, vulnerable to future
  edits that call `errno`-setting functions inside the loop. (nit)

- **`unlink` failure mid-scan leaves a half-cleaned archive** —
  `pg_archivecleanup.c:163-166`. `pg_fatal` exits immediately. (nit)

- **Anachronistic "Customizable section" banner** —
  `pg_archivecleanup.c:37-50` and `:252-255`. Reads like a historical
  artifact; extension authors fork rather than patch in place. (nit)

## pg_test_fsync

- **`unlink` from signal handler is not strictly async-signal-safe** —
  `pg_test_fsync.c:599`. Works on every real OS but POSIX doesn't
  list it. (nit)

- **16 MiB BSS for a benchmark binary** — `pg_test_fsync.c:71`.
  `DEFAULT_XLOG_SEG_SIZE`-sized global buffer. (nit)

- **`-f` given twice leaks previous filename** —
  `pg_test_fsync.c:178`. `pg_strdup` with no `pg_free`. (nit)

## pg_test_timing

- **Single backwards clock step aborts the run** —
  `pg_test_timing.c:309-315`. Histogram data discarded. Single
  NTP-induced glitches force multiple runs to characterize. (nit)

- **TSC drift >10% exit-on-detect fights the diagnostic use case** —
  `pg_test_timing.c:221-226`. After printing the diff %, the tool
  exits 1 before printing the histogram. The histogram is exactly
  what an admin wants when chasing TSC drift. (nit)

- **Mixed `%lld` and PRI macros** — `pg_test_timing.c:402-407`.
  Cosmetic. (nit)

## pg_walsummary

- **`block_buffer` never freed across files** —
  `pg_walsummary.c:144-145`. Intentional reuse (comment at line
  169-170). Documented. (nit — not really a bug)

- **`walsummary_error_callback` missing `pg_noreturn`** —
  `pg_walsummary.c:46`. Calls `exit(1)`, so behaves noreturn. (nit)

- **No CLI-level magic check before invoking the reader** —
  `pg_walsummary.c:107-108`. Reader errors out on bad magic, but a
  cheaper up-front sanity check would give a nicer message. (nit)

## pgevent (Windows event-log DLL)

- **`wcstombs` with no bounds check** — `pgevent.c:42`. `pszCmdLine`
  encoding to >256 bytes corrupts past `event_source`. Requires hostile
  `regsvr32 /i:LONG_NAME` invocation. (maybe)

- **`_snprintf` doesn't NUL-terminate on truncation** —
  `pgevent.c:83`, `:136`. 400-byte key buffer safe by arithmetic with
  255-char max event-source name, but the pattern is a footgun. (nit)

- **`DllRegisterServer` return code ignored** — `pgevent.c:56`. If
  registration fails, `DllInstall` returns `S_OK` and `regsvr32`
  reports success. (likely)

- **Modal `MessageBox` on every failure step** —
  `pgevent.c:75`, `:88`, etc. From silent installer context, stalls.
  (nit)

- **No check on `wcstombs` (size_t)-1 return** — `pgevent.c:42`.
  Invalid wide-char sequences silently leave stale `event_source`.
  (nit)

- **Single MessageId loses Event Viewer filtering granularity** —
  `pgmsgevent.h:46`. By design but limits Windows-side admin tooling.
  (nit)

## pg_config

- **Triple-source for config keys** — `pg_config.c:42-66`. `info_items[]`,
  `help()`, and the `get_configdata` provider must agree. (nit)

- **No deduplication of repeated `--bindir`** — `pg_config.c:159-164`.
  Cosmetic. (nit)
