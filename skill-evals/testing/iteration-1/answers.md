# Iteration 1 — answers (twice per eval, honest)

Each answer is what I would actually produce given only the SKILL.md (and the
companion `knowledge/conventions/testing.md` it points to). No subagents, no extra browsing.

---

## Eval 1 — regress test for a new builtin SQL function

### Attempt A

This is pure SQL (no concurrency, no initdb, no C-only hooks), so step 4 of the
decision tree applies: **regress test**.

Files to create/edit:

1. Create `source/src/test/regress/sql/<name>.sql` — write SELECTs exercising
   your new function (normal cases, edge cases, error cases).
2. Create `source/src/test/regress/expected/<name>.out` — generated, not typed
   by hand (see below).
3. Edit `source/src/test/regress/parallel_schedule` — add `<name>` to an
   existing `test:` group (max 20 entries per group), or add a new group line.

To generate the expected output:

```bash
meson test -C build regress/regress   # will FAIL the first time
cp source/src/test/regress/results/<name>.out source/src/test/regress/expected/<name>.out
meson test -C build regress/regress   # should now pass
```

Read the generated `.out` before committing. Anything OID-y, timestamp-y, or
row-order-y will be a buildfarm failure — cast it away, `ORDER BY` it, or `SET`
it away. Use `\set VERBOSITY terse` if you're checking error messages so the
output isn't tied to file/line in the source.

If you only want to run one regress test (faster loop):

```bash
cd build/src/test/regress
./pg_regress --temp-instance=/tmp/pgr --top-builddir=../../../.. <name>
```

If it fails, the first place to look is `build/src/test/regress/regression.diffs`.

### Attempt B

You want a regress test under `source/src/test/regress/`.

1. New file `sql/<feature>.sql`. Call your function with representative inputs
   and a few error cases.
2. Expected output `expected/<feature>.out`. Don't write this — generate it:
   run `meson test -C build regress/regress` (it fails the first time and
   writes `results/<feature>.out`), eyeball that result, and copy it into
   `expected/`.
3. Wire it into `source/src/test/regress/parallel_schedule` by adding it to a
   `test: ...` line (keep ≤20 per group).

Re-run the suite — should pass now. Read the new `.out` carefully before
committing: timestamps, OIDs, plan costs, and unsorted rows are common
buildfarm-flakiness sources. Use `ORDER BY`, casts, and `SET` to pin them.

Single-test runner for the inner loop:

```bash
meson test -C build regress/regress -v
```

or narrower with `pg_regress` directly per the SKILL.

If/when it fails, read `build/src/test/regress/regression.diffs` first.

---

## Eval 2 — TAP test for streaming replication catching a WAL record

### Attempt A

Step 2 of the decision tree: this needs initdb + a standby + replication, so
it's a **TAP test**. Recovery/replication tests live in
`source/src/test/recovery/t/NNN_name.pl`. Pick the next free `NNN` in that dir
— don't renumber existing tests (breaks backports).

Wire it into `source/src/test/recovery/meson.build` (and the Makefile if
present in that dir).

Skeleton, based on `001_stream_rep.pl`:

```perl
use strict;
use warnings FATAL => 'all';
use PostgreSQL::Test::Cluster;
use PostgreSQL::Test::Utils;
use Test::More;

my $primary = PostgreSQL::Test::Cluster->new('primary');
$primary->init(allows_streaming => 1);
$primary->start;

$primary->backup('bk');
my $standby = PostgreSQL::Test::Cluster->new('standby');
$standby->init_from_backup($primary, 'bk', has_streaming => 1);
$standby->start;

# Operation that emits your WAL record
$primary->safe_psql('postgres', 'SELECT my_thing()');

# Wait for replay
$primary->wait_for_replay_catchup($standby);

# Verify standby state
my $r = $standby->safe_psql('postgres', 'SELECT ...');
is($r, 'expected', 'standby replayed the record');

$standby->stop('fast');
$primary->stop('fast');
done_testing();
```

To verify a *specific* WAL record made it across, the most robust approaches are
either (a) check user-visible state on the standby after
`wait_for_replay_catchup`, or (b) compare LSNs (`pg_current_wal_lsn` on primary,
`pg_last_wal_replay_lsn` on standby) and assert the standby caught up past the
moment your record was inserted. The SKILL doesn't spell out a "match WAL record
type" API — you assert on observable effects.

Run just this test:

```bash
meson test -C build --suite recovery NNN_name -v
# or
cd source/src/test/recovery && make check PROVE_TESTS=t/NNN_name.pl
```

If it fails, read `build/testrun/recovery/NNN_name/log/regress_log_*` first
(the Perl-side log), then the per-node postmaster logs. Set `PG_TEST_NOCLEAN=1`
to keep `tmp_check/` around on success too.

Style: only `IPC::Run` from non-core Perl; must work on Perl 5.14; run
`perltidy --profile=src/tools/pgindent/perltidyrc` before submitting.

### Attempt B

TAP test under `source/src/test/recovery/t/`, named `NNN_<topic>.pl` with NNN
the next free number (don't renumber existing files — cherry-pick / backport
hostile). Wire into `source/src/test/recovery/meson.build`.

Skeleton uses `PostgreSQL::Test::Cluster`:

- `Cluster->new('primary')` then `->init(allows_streaming => 1)` then `->start`.
- `->backup('name')` → `Cluster->new('standby')->init_from_backup($primary,
  'name', has_streaming => 1)` → `->start`.
- Run your DDL/DML on the primary that emits the WAL record.
- `$primary->wait_for_replay_catchup($standby)` to sync.
- Use `safe_psql` on the standby to assert the resulting state.

The SKILL doesn't give a way to assert "WAL record of type X was applied"
directly — it's a black-box test. You verify the effect (table contents, LSN
advance, a system view).

Fast single-test loop:

```bash
meson test -C build --suite recovery 0NN_name
```

When it fails: `build/testrun/recovery/0NN_name/log/regress_log_*` is the
Perl-side log — read that before the postmaster logs. `PG_TEST_NOCLEAN=1`
preserves `tmp_check/`.

Rules: `done_testing();` at the end, only `IPC::Run` outside Perl 5.14 core,
`perltidy` per the project profile before submitting.

---

## Eval 3 — isolation test for a new heavyweight-lock conflict on ALTER TABLE

### Attempt A

Step 1 of the decision tree: multiple sessions + heavyweight-lock contention
→ **isolation spec** under `source/src/test/isolation/specs/<name>.spec`.
This is the sweet spot for isolationtester: it detects blocking by polling
`pg_locks` for `granted = false`, and heavyweight locks are exactly what it
sees. (LWLocks/buffer pins are invisible — would need injection points.)

Spec shape:

```
setup    { CREATE TABLE t (a int); INSERT INTO t VALUES (1); }
teardown { DROP TABLE t; }

session "s1"
{
    step "s1_begin"  { BEGIN; }
    step "s1_alter"  { ALTER TABLE t ADD COLUMN b int; }
    step "s1_commit" { COMMIT; }
}

session "s2"
{
    step "s2_begin"  { BEGIN; }
    step "s2_select" { SELECT * FROM t; }
    step "s2_commit" { COMMIT; }
}

permutation "s1_begin" "s1_alter" "s2_begin" "s2_select" "s1_commit" "s2_commit"
```

The critical point: when steps block, you **must** list `permutation` lines
explicitly. Without them, isolationtester auto-generates every valid
interleaving including ones that deadlock-with-no-rescuer, and the test will
hang until canceled (after `2 * PG_TEST_TIMEOUT_DEFAULT`).

Files to touch:

1. `source/src/test/isolation/specs/<name>.spec`
2. `source/src/test/isolation/expected/<name>.out` — generate by running the
   test once and copying from `output_iso/results/<name>.out`.
3. `source/src/test/isolation/isolation_schedule` — add `test: <name>`.

Avoid `_1.out` / `_2.out` variants; if timing of the "waiting" report is
flaky, use markers on the permutation entries instead — `s1_alter(*)` to force
an immediate "waiting" report, `s1_alter(s2_commit)` to defer reporting until
`s2_commit` completes, etc.

Run just it:

```bash
cd build/src/test/isolation
./pg_isolation_regress --temp-instance=/tmp/iso \
    --top-builddir=../../../.. <name>
```

On failure: `build/src/test/isolation/output_iso/regression.diffs`. A hang
means an invalid permutation.

### Attempt B

Heavyweight-lock contention with two sessions is exactly what isolation tests
are for. Spec under `source/src/test/isolation/specs/<name>.spec`; expected
output under `expected/<name>.out`; register in `isolation_schedule`.

Sketch the spec with `setup`/`teardown` (global, on a control connection),
per-session `setup`/steps/`teardown`, and an explicit `permutation` line
showing the interleaving you actually want. **Listing the permutation
explicitly is mandatory whenever steps block**, otherwise the auto-generator
will try interleavings that hang forever.

To not-hang-CI:

- always write the `permutation` lines yourself for blocking tests
- prefer markers (`step(*)`, `step(other_step)`, `step(other_step notices N)`)
  over `_1.out` variants to stabilize race-y "waiting" reporting

Generate expected output by running once, inspecting
`build/src/test/isolation/output_iso/results/<name>.out`, and copying it to
`expected/`.

Inner-loop runner:

```bash
cd build/src/test/isolation
./pg_isolation_regress --temp-instance=/tmp/iso --top-builddir=../../../.. <name>
```

Failures: `output_iso/regression.diffs`. Hangs = invalid permutation that
blocks without anything to release it.

Caveat from the SKILL: isolationtester only detects heavyweight-lock waits via
`pg_locks`. Your ALTER TABLE / SELECT case is heavyweight, so this is fine. If
the real conflict were LWLock or buffer pin, you'd need
`src/test/modules/injection_points` instead.
