---
source_url: https://www.postgresql.org/docs/current/regress-tap.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §33.4: TAP Tests

The Perl `prove`-driven test layer that pg_regress can't reach — anything
needing **multiple servers, restarts, crash/recovery, or client-tool
orchestration**. This repo's R13 ladder names `recovery` and `subscription`
TAP suites as separate blast-radius tiers; this is what they are.

## What TAP tests are and where they live

- "Various tests, particularly the client-program tests under `src/bin`,
  use the Perl TAP tools and are run using the Perl testing program
  **`prove`**." `[from-docs]` TAP = Test Anything Protocol.
- Test scripts live in `t/` subdirectories (e.g. `src/bin/pg_dump/t/`,
  `src/test/recovery/t/`), conventionally numbered `NNN_name.pl`. `[from-docs]`
- Requires PostgreSQL configured with **`--enable-tap-tests`** and a Perl
  with the **`IPC::Run`** module (CPAN or OS package). `[from-docs]`

## The key behavioral difference from pg_regress

- TAP tests **start their own server(s)** — even under `make installcheck`.
  Unlike the SQL regress harness, which expects an already-running server in
  installcheck mode, a TAP script provisions and tears down its own
  cluster(s). `[from-docs]` This is what lets them test multi-node
  replication, failover, and restart-after-crash that a single shared
  server can't express.

## Running them

- `make check` / `make installcheck` in a directory that has `t/` runs its
  TAP tests. `[from-docs]`
- `PROVE_FLAGS` passes options to `prove`, e.g.
  `make -C src/bin check PROVE_FLAGS='--timer'`. `[from-docs]`
- `PROVE_TESTS` restricts to a subset:
  `make check PROVE_TESTS='t/001_test1.pl t/003_test3.pl'`. `[from-docs]`
- The meson equivalent is selecting the TAP suite via `meson test --suite
  recovery` (etc.); the R13 ladder leans on exactly these per-suite
  selectors. `[inferred from build-and-run skill]`

## Useful environment variables

- **`PG_TEST_NOCLEAN=1`** — retain data + temp directories after the run
  regardless of pass/fail (essential for post-mortem):
  `PG_TEST_NOCLEAN=1 make -C src/bin/pg_dump check`. `[from-docs]`
- **`PG_TEST_TIMEOUT_DEFAULT`** — raise the default 180-second per-operation
  timeout on slow hosts. `[from-docs]`

## The Perl test modules (the API you write against)

- The harness ships `PostgreSQL::Test::Cluster`
  (`source/src/test/perl/PostgreSQL/Test/Cluster.pm` `[verified-by-code]`)
  — node provisioning, start/stop/restart, `psql`/`safe_psql`,
  `wait_for_catchup`, etc. — and `PostgreSQL::Test::Utils`
  (`source/src/test/perl/PostgreSQL/Test/Utils.pm` `[verified-by-code]`)
  — `command_ok`, `command_fails`, `slurp_file`, tempdir helpers.
  `[verified-by-code]` (paths confirmed at anchor SHA;
  the chapter excerpt itself focuses on invocation rather than the module
  API, so treat the module-name detail as code-verified, not docs-quoted.)

## Links into corpus

- The SQL-side harness this complements:
  [docs-distilled/regress-run.md](./regress-run.md)
- Coverage of the C reached by TAP runs:
  [docs-distilled/regress-coverage.md](./regress-coverage.md)
- Relevant skills: `testing`. R14 item 5 ("cross-backend / session-isolation
  TAP — exit, reconnect, verify isolation invariants") is precisely the
  class of test that *requires* this layer; sesvars' `054_sessvar_lifecycle.pl`
  is the in-repo exemplar.
