# PostgreSQL testing infrastructure — how to add a test that gets accepted

Cites use `source/` paths; numbers are line refs in the upstream tree at session time.

## 1. The four flavors

PostgreSQL ships four distinct test mechanisms. Pick the **lowest-power** one that
can exercise the behavior — reviewers push back on TAP tests when a `.sql` would
do. `[from-readme source/src/test/perl/README:42]`: *"You should prefer to write
tests using pg_regress in src/test/regress, or isolation tester specs in
src/test/isolation, if possible."*

| Flavor | Lives in | Driver | Good for | Bad for |
|---|---|---|---|---|
| **regress** | `src/test/regress/sql/*.sql` + `expected/*.out` | `pg_regress` (psql) | Pure SQL: planner output, builtins, DDL semantics, error messages | Anything needing >1 backend, crashes, server restart, OS-level state |
| **isolation** | `src/test/isolation/specs/*.spec` | `pg_isolation_regress` + `isolationtester` (libpq, N conns) | Concurrent SQL: locking, MVCC, deadlock, predicate-locking, snapshot tests | Anything needing initdb-time config, multiple clusters, replication |
| **TAP** | `src/test/<area>/t/NNN_*.pl`, `src/bin/*/t/*.pl`, `contrib/*/t/*.pl` | Perl `prove` + `PostgreSQL::Test::Cluster` | initdb, multi-cluster replication, crash/restart, pg_basebackup, CLI tools, auth, SSL, signals | Quick SQL checks — too much overhead |
| **modules (C extensions)** | `src/test/modules/<name>/` | Loaded by one of the above | Testing C-level hooks, APIs, undocumented internals (`injection_points`, `test_shm_mq`, etc.) | Anything reachable from SQL |

`[from-readme source/src/test/README:1-50]` lays out the directory; `[from-readme
source/src/test/modules/README:1-21]` confirms modules exist to expose C APIs
to the test layer ("If you're adding new hooks or other functionality exposed as
C-level API this is where to add the tests for it").

## 2. Adding a regress test

Mechanism: `pg_regress` runs each `.sql` through psql, captures output to
`results/<name>.out`, then `diff`s against `expected/<name>.out`. Identical → pass.

`[from-docs https://www.postgresql.org/docs/current/regress.html]`,
`[verified-by-code source/src/test/regress/pg_regress.c:2004]` — failures append
to `regression.diffs`.

### Steps

1. **Create `src/test/regress/sql/<name>.sql`** — the input. Naming convention is
   short, lower_snake_case, matches a feature (`select.sql`, `merge.sql`).
2. **Create `src/test/regress/expected/<name>.out`** — what psql should print.
   Easiest workflow:
   - Run `make check` once (it will fail and write `results/<name>.out`).
   - Inspect it carefully — every byte becomes the contract.
   - Copy: `cp src/test/regress/results/<name>.out src/test/regress/expected/<name>.out`.
3. **Wire into `src/test/regress/parallel_schedule`** `[verified-by-code
   source/src/test/regress/parallel_schedule:17]`. Add to an existing
   `test: …` group (≤20 per group by convention, line 8), or add a new group.
   Comment dependencies above the line.
4. **Wire into `src/test/regress/schedule` too** — wait, there's only
   `parallel_schedule` here `[verified-by-code]`; some PG forks also keep
   `serial_schedule`. Upstream master uses only `parallel_schedule`.
5. **Alternative expected outputs** — if output legitimately differs by
   platform/locale/encoding, create `<name>_1.out`, `<name>_2.out`, etc.
   `pg_regress` accepts any of them. `[verified-by-code
   source/src/test/regress/expected/char_1.out]` and per-platform pinning via
   `src/test/regress/resultmap` `[verified-by-code source/src/test/regress/resultmap:1]`:
   ```
   float4:out:.*-.*-cygwin.*=float4-misrounded-input.out
   ```

### Style rules (commonly enforced in review)

- No timestamps, OIDs, or random values in output. Use `\set VERBOSITY terse`,
  cast away volatile fields, or pin with `SET`.
- No `\d` of catalog tables whose layout changes between releases — use targeted
  queries.
- Don't leak global state. Drop your objects in the same file, or place them in a
  named schema and `DROP SCHEMA ... CASCADE`.
- Don't depend on plan choice unless that's the point. If it is, `SET
  enable_seqscan = off` etc. and use `EXPLAIN (COSTS OFF)`.

`[from-wiki https://wiki.postgresql.org/wiki/Regression_test_authoring]`

## 3. Adding an isolation test

For concurrent behavior — two or more sessions interleaved deterministically.
The sweet spot is **heavyweight-lock tests, deadlock tests, MVCC visibility
tests, predicate locking, two-phase commit interactions**. Anything where
"session A does X, then session B does Y while A is still in-flight" is the
shape of the bug.

### Spec grammar `[from-readme source/src/test/isolation/README:56-130]`

```
setup    { <SQL> }       # once before each permutation (control conn)
teardown { <SQL> }       # once after each permutation
session "s1" {
    setup    { <SQL> }   # in s1's own connection
    step "s1a" { <SQL> } # each step is named, must be unique across file
    step "s1b" { <SQL> }
    teardown { <SQL> }
}
session "s2" { ... }
permutation "s1a" "s2a" "s1b" "s2b"   # explicit interleaving
```

If no `permutation` lines are given, the tester runs **all valid interleavings**
(steps within one session keep their order). For blocking tests you **must**
list permutations manually `[from-readme isolation/README:124-130]`, otherwise
the test will explore permutations that hang forever (canceled after `2 *
PG_TEST_TIMEOUT_DEFAULT`).

### Blocking detection

`isolationtester` decides a step has blocked by polling `pg_locks` for `granted
= false` `[from-readme isolation/README:147-149]`. **Only heavyweight locks are
detected** — LWLock / spinlock / buffer pin contention is invisible. For those
use injection points (`src/test/modules/injection_points`) or a custom C
extension.

### Stabilizing flaky timing

Markers on permutation entries delay reporting of completion `[from-readme
isolation/README:163-205]`:
- `s1a(*)` — force "waiting" report immediately
- `s1a(s2b)` — don't report s1a as complete until s2b completes
- `s1a(s2b notices 3)` — wait until s2b has emitted ≥3 NOTICEs

### Files to touch

1. `src/test/isolation/specs/<name>.spec`
2. `src/test/isolation/expected/<name>.out` (generate via run-and-copy like regress)
3. `src/test/isolation/isolation_schedule` — add `test: <name>` line
4. `_1.out` / `_2.out` variants discouraged `[from-readme isolation/README:154-159]`
   — prefer markers.

## 4. Adding a TAP test

When you need: a real cluster (initdb), multiple clusters, controlled restart,
backup tooling, replication, signals, file-system inspection, environment
variables, auth/SSL setup, or CLI tools (`pg_dump`, `pg_rewind`, `pg_basebackup`).

### Where it goes

- Replication/recovery: `src/test/recovery/t/NNN_name.pl`
- Logical replication: `src/test/subscription/t/NNN_name.pl`
- A CLI tool: `src/bin/<tool>/t/NNN_name.pl`
- Auth: `src/test/authentication/t/NNN_name.pl` (`[verified-by-code
  source/src/test/authentication/]`)
- SSL: `src/test/ssl/t/NNN_name.pl`
- Contrib extension: `contrib/<ext>/t/NNN_name.pl`

**Numbering** `[from-readme source/src/test/perl/README:55]`: scripts run in
alphabetical order; the convention is `NNN_short_name.pl` starting at `001`. Pick
the next free integer in the directory. Avoid renumbering existing tests (cherry-
pick / backport friction).

### Skeleton `[verified-by-code source/src/test/recovery/t/001_stream_rep.pl:5-18]`

```perl
use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $node = PostgreSQL::Test::Cluster->new('primary');
$node->init(allows_streaming => 1);
$node->start;

my $r = $node->safe_psql('postgres', 'SELECT 1');
is($r, '1', 'sanity');

$node->stop('fast');
done_testing();
```

### Key `PostgreSQL::Test::Cluster` API `[verified-by-code source/src/test/perl/PostgreSQL/Test/Cluster.pm:1-100]`

- `Cluster->new($name)` — allocate a port and data-dir, **don't initdb yet**.
- `$node->init(%opts)` — run initdb. `allows_streaming => 1` adds replication
  config; `auth_extra => [...]` passes to initdb.
- `$node->init_from_backup($src, $name, has_streaming => 1)` — create a standby
  from a base backup `[verified-by-code 001_stream_rep.pl:26]`.
- `$node->start` / `$node->stop('fast'|'immediate'|'smart')` / `$node->restart`.
- `$node->append_conf('postgresql.conf', "...")` then `$node->restart`.
- `$node->safe_psql($db, $sql)` — return stdout, die on error.
- `$node->psql($db, $sql, stdout => \$o, stderr => \$e, on_error_die => 1)` —
  full control.
- `$node->backup($name)` — pg_basebackup to a temp slot.
- `$node->poll_query_until($db, $sql)` — busy-wait until the query returns `t`.
- `$node->wait_for_replay_catchup($standby)` — sync helper.
- From `PostgreSQL::Test::Utils`: `command_ok([...], 'label')`, `command_fails`,
  `command_like` for invoking CLI tools.

### Style rules

- `--enable-tap-tests` must be on (it's default in meson builds).
- Use `IPC::Run` only — no other non-core Perl modules `[from-readme
  src/test/perl/README:106-110]`. Must work on Perl 5.14.
- `perltidy --profile=src/tools/pgindent/perltidyrc` before submitting
  `[from-readme src/test/perl/README:47]`.
- Always `done_testing();` at end (not a fixed plan count — easier to extend).

## 5. `make check` vs `make installcheck`

`[from-docs regress.html]`,
`[from-readme src/test/recovery/README:18-23]`:

- **`make check`** — builds a temp instance in `tmp_check/`, runs tests, throws
  it away. Safe, always reproducible. **Default for CI and patch submission.**
- **`make installcheck`** — runs tests against an already-`make install`-ed
  cluster you started yourself (uses `PGHOST`/`PGPORT`). Faster iteration; **will
  pollute the target DB** and sometimes outright fails if the cluster's settings
  don't match expectations. Some suites (e.g. `src/test/modules`) explicitly
  warn not to point this at valuable data `[from-readme
  src/test/modules/README:9-13]`.

Meson equivalent: `meson test -C build` runs everything; `meson test -C build
--suite <suite>` targets a directory.

## 6. Debugging failures

### regress

- `src/test/regress/regression.diffs` — unified diff of every failing test
  (expected vs actual). Always your first stop. `[verified-by-code
  source/src/test/regress/pg_regress.c:2004]`
- `src/test/regress/results/<name>.out` — the actual output. If the diff looks
  acceptable, this is what should become the new `expected/<name>.out`.
- `src/test/regress/log/postmaster.log` — server log from the temp instance.

### isolation

- `src/test/isolation/output_iso/regression.diffs` and `output_iso/results/`.
- Hangs almost always mean an invalid permutation that blocks without a session
  to unblock it.

### TAP

- `tmp_check/log/regress_log_NNN_*` — the Perl-side log (`Test::More` `diag`
  output, every `safe_psql` call, etc.). **Read this first**
  `[from-readme src/test/perl/README:22-24]`.
- `tmp_check/log/<node>_*.log` — postmaster logs per node.
- Set `PG_TEST_NOCLEAN=1` to preserve `tmp_check/` after a passing run too.
- Slow CI? `PG_TEST_TIMEOUT_DEFAULT=600` `[from-readme
  src/test/perl/README:26-28]`.

## 7. Running just what you need

### A single regress test against a temp instance
```
cd build
meson test -C . regress/regress -v   # full regress suite, verbose
# or, narrower:
cd ../source/src/test/regress
./pg_regress --temp-instance=/tmp/pgr --top-builddir=../../../../build \
    --dlpath=../../../../build/src/test/regress <test_name>
```

### A single isolation spec
```
cd build/src/test/isolation
./pg_isolation_regress --temp-instance=/tmp/iso \
    --top-builddir=../../../.. fk-contention fk-deadlock
```
`[from-readme src/test/isolation/README:20-24]`

### A single TAP test
```
meson test -C build --suite recovery 001_stream_rep
# or via make:
cd source/src/test/recovery
make check PROVE_TESTS=t/001_stream_rep.pl
```
`[from-readme src/test/perl/README:12-13]`, `[verified-by-code
source/src/test/recovery/meson.build:13]`

### All buffer-related tests (worked example)
There's no "buffer suite" — buffering coverage is spread across:
- `regress`: planner/cost coverage uses buffers implicitly; no dedicated `.sql`.
- `recovery` TAP tests exercise WAL → buffer interactions
  (`015_promotion_pages`, `008_fsm_truncation`).
- `src/test/modules/test_shm_mq`, `injection_points` for low-level hooks.

The single best one-liner to exercise the buffer manager broadly:
```
meson test -C build --suite recovery --suite regress
```
(There is no `--suite buffer`; PG doesn't split tests by subsystem.)

## 8. Quick "easy to get wrong" list

1. **Forgetting to add the test to `parallel_schedule` / `isolation_schedule` /
   the suite's `meson.build`.** The file exists but nothing runs it; CI passes;
   reviewer notices.
2. **Volatile output**: OIDs, timestamps, plan costs, row order without
   `ORDER BY`. Tests are stable on your laptop, flaky on the buildfarm.
3. **Adding a TAP test for something a `.sql` could express.** Reviewers will
   ask you to downgrade.
4. **Isolation test with no explicit `permutation` lines when steps block** —
   auto-generated permutations will hang.
5. **Renumbering existing TAP tests** when inserting a new one — breaks
   backports. Always pick the next free `NNN`.
6. **Relying on `pg_locks` to detect LWLock waits in isolation tests.** Only
   heavyweight locks are visible `[from-readme isolation/README:147-149]`.
