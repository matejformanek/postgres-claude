# Eval 3 — isolation test for a new heavyweight-lock conflict (WITH SKILL)

Step 1, item 1 of the decision tree: multiple sessions, heavyweight-lock
contention → **isolation spec**. This is exactly what `isolationtester` is for:
it polls `pg_locks` for `granted = false` to detect blocking, and heavyweight
locks are precisely what shows up there. (LWLocks / buffer pins are invisible —
that would be `source/src/test/modules/injection_points/` territory. ALTER
TABLE vs SELECT is heavyweight, so isolation spec is correct.)

## Spec

`source/src/test/isolation/specs/<name>.spec`:

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

## Don't hang CI

**When any step blocks, explicit `permutation` lines are mandatory.** Without
them isolationtester auto-generates every valid interleaving, including ones
that deadlock with nothing to release them; the test then hangs until cancelled
(after `2 * PG_TEST_TIMEOUT_DEFAULT`).

## Files to touch

1. `source/src/test/isolation/specs/<name>.spec`
2. `source/src/test/isolation/expected/<name>.out` — generated; run the spec
   once and copy from `build/src/test/isolation/output_iso/results/<name>.out`.
3. `source/src/test/isolation/isolation_schedule` — add `test: <name>`.

## Stabilization

**Avoid `_1.out` / `_2.out` variants.** If the "waiting" report is race-y, use
markers on the permutation entries instead: `s1_alter(*)` forces an immediate
"waiting" report; `s1_alter(s2_commit)` defers reporting until `s2_commit`
finishes; `s1_alter(s2_commit notices 1)` waits for one NOTICE too.

## Single-spec runner

```bash
cd build/src/test/isolation && \
  ./pg_isolation_regress --temp-instance=/tmp/iso \
    --top-builddir=../../../.. <name>
```

## On failure

`build/src/test/isolation/output_iso/regression.diffs`. A hang means an invalid
permutation (a step blocks with nothing to release it).
