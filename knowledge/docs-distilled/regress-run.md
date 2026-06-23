---
source_url: https://www.postgresql.org/docs/current/regress-run.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §33.1: Running the Regression Tests

How the test harness is invoked. The operational counterpart to the
`testing` and `build-and-run` skills — every `meson test` / `make check`
in this repo is a special case of what this chapter spells out.

## `check` vs `installcheck` — the load-bearing distinction

- **`make check`** runs against a **temporary installation built inside the
  build tree**: it spins up a throwaway server (its own data directory,
  socket, port) for the duration of the run, then tears it down. It does
  **not** require an already-running cluster. It **cannot be run as root**
  (the temp postmaster refuses). `[from-docs]`
- **`make installcheck`** runs against an **already-initialized, already-running
  installation**. It contacts the server at `PGHOST` / `PGPORT`, creates a
  database named `regression` (**dropping any pre-existing database of that
  name** — the data-loss footgun), and transiently creates cluster-wide
  objects prefixed `regress_`. `[from-docs]`
- The meson equivalent is `meson test` (which by default behaves like the
  temp-install path); the `--suite <name>` selector this repo's R13 ladder
  leans on chooses which suite directory runs. `[inferred from build-and-run skill]`

## Parallelism and the connection ceiling

- Tests run in **parallel groups** driven by a schedule file
  (`src/test/regress/parallel_schedule` `[verified-by-code]` —
  `source/src/test/regress/parallel_schedule`); a `serial_schedule` exists
  for forcing serial execution. `[from-docs]`
- Default max concurrency is **twenty parallel scripts = forty processes**
  (one server backend + one psql per script). The per-user process limit
  must be **≥ 50**. `[from-docs]`
- Throttle with `make MAX_CONNECTIONS=10 check` when the host is small or
  the ulimit is tight. `[from-docs]`
- Output line prefixes: `+` marks a test run in a parallel group, `-` marks
  a sequentially-run test. Success banner: `# All NNN tests passed.` `[from-docs]`

## The "-world" suites (what R12's full gate actually covers)

`make check-world` / `make installcheck-world` run **every applicable
suite**, not just core regress: `src/pl` (procedural languages), `contrib`,
`src/interfaces/libpq/test` + `src/interfaces/ecpg/test`,
`src/test/authentication`, `src/test/isolation`, `src/test/recovery`,
`src/test/subscription`, and `src/bin`. `[from-docs]` This is why R13's
scope ladder treats contrib / isolation / recovery as *separate* suites
invisible to a regress-only check. Recommended: `make check-world -j8`.

## Opt-in extras: `PG_TEST_EXTRA` and `EXTRA_TESTS`

- **`EXTRA_TESTS`** runs non-default core tests, e.g.
  `make check EXTRA_TESTS=numeric_big` (long-running / platform-dependent
  tests excluded from the default schedule). `[from-docs]`
- **`PG_TEST_EXTRA`** opts into heavyweight / environment-sensitive suites:
  `kerberos`, `ldap`, `ssl`, `load_balance`, `libpq_encryption`, `oauth`,
  `regress_dump_restore`, `sepgsql`, `wal_consistency_checking`,
  `xid_wraparound`. Several open TCP sockets or are resource-intensive; all
  require `--enable-tap-tests`. `[from-docs]`

## Locale / encoding / custom settings knobs

- Temp-install only: `LANG`, `LC_COLLATE`, `LC_CTYPE` are honored;
  **`LC_ALL` does NOT work** for this purpose. `ENCODING=EUC_JP` forces a
  test encoding; `NO_LOCALE=1` disables locale entirely. `[from-docs]`
- installcheck inherits the **cluster's** locale — it cannot be set
  per-run. `[from-docs]`
- `PG_TEST_INITDB_EXTRA_OPTS='-k --wal-segsize=4 -c work_mem=50MB'` passes
  initdb flags; `PGOPTIONS="-c debug_parallel_query=regress"` passes runtime
  GUCs; `EXTRA_REGRESS_OPTS="--temp-config=test_postgresql.conf"` injects a
  whole postgresql.conf fragment into the temp instance. `[from-docs]`

## Links into corpus

- Result comparison + spurious-failure taxonomy:
  [docs-distilled/regress-evaluation.md](./regress-evaluation.md)
- Multiple expected files / resultmap:
  [docs-distilled/regress-variant.md](./regress-variant.md)
- Perl TAP harness: [docs-distilled/regress-tap.md](./regress-tap.md)
- Coverage instrumentation: [docs-distilled/regress-coverage.md](./regress-coverage.md)
- Relevant skills: `testing`, `build-and-run`. The R13 scope ladder in
  `.claude/rules/pg-implement-discipline.md` is the in-repo enforcement of
  this chapter's "separate suites" reality.
