# Eval 3 — isolation test for a heavyweight-lock conflict (BASELINE, no skill)

Two sessions with one blocking the other on a heavyweight lock is the textbook
case for an isolation test, which lives under `src/test/isolation/`. The
framework (isolationtester) detects blocking by watching `pg_locks`.

## Spec

Create `src/test/isolation/specs/<name>.spec`. Roughly:

```
setup    { CREATE TABLE t (...); }
teardown { DROP TABLE t; }

session "s1"
{
    step "s1a" { BEGIN; ALTER TABLE t ADD COLUMN b int; }
    step "s1b" { COMMIT; }
}

session "s2"
{
    step "s2a" { SELECT * FROM t; }
}

permutation "s1a" "s2a" "s1b"
```

The expected output file goes in `expected/<name>.out`. Generate it by running
the spec once and copying the produced output, rather than handwriting.

## Schedule

You also need to register the test in the isolation schedule file —
`isolation_schedule` in the same dir, I believe.

## Don't hang CI

Important: when you have a blocking step, you need to **list explicit
permutations**. Otherwise the framework will try all permutations including
ones that have no valid completion order, and the test will hang.

## Running just this one

Something like:

```bash
cd src/test/isolation
./pg_isolation_regress <name>
```

(or via meson: `meson test -C build isolation/...`).

## On failure

There will be a diff file in the output directory (probably under
`output_iso/`). Read it and decide whether the expected output needs updating
or whether the test is wrong.
