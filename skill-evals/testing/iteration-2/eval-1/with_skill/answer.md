# Eval 1 — regress test for a new builtin SQL function (WITH SKILL)

The new function lives in `src/backend/utils/adt/varlena.c` and is exercised
purely from SQL. The decision tree (Step 1) lands on item 4: pure SQL behavior
with no concurrency, no initdb, no C-only hook → **regress test**.

## Files

1. `source/src/test/regress/sql/<name>.sql` — SELECTs exercising the new
   function: normal inputs, edge cases (empty string, NULL, multibyte),
   error cases.
2. `source/src/test/regress/expected/<name>.out` — **generated**, not typed.
3. `source/src/test/regress/parallel_schedule` — add `<name>` to an existing
   `test:` group (**max 20 tests per group**), or add a new group line.

## Generating expected output

```bash
meson test -C build regress/regress         # FAILS the first time
cp source/src/test/regress/results/<name>.out \
   source/src/test/regress/expected/<name>.out
meson test -C build regress/regress         # should now pass
```

**Always read the generated `.out` before committing.** Anything OID-y,
timestamp-y, plan-cost-y, or row-order-y is a future buildfarm failure. Cast it,
`ORDER BY` it, `SET` it away. For error-message tests use `\set VERBOSITY terse`
so output isn't tied to source file/line.

## Fast inner loop

```bash
cd build/src/test/regress && \
  ./pg_regress --temp-instance=/tmp/pgr --top-builddir=../../../.. <name>
```

## When it fails

Open `build/src/test/regress/regression.diffs` first. If the diff is what you
expected, copy `results/<name>.out` over `expected/<name>.out`.
