# Eval 1 — regress test for a new builtin SQL function (BASELINE, no skill)

For a new SQL function, you want a regression test in PostgreSQL's regress
framework. Create a SQL file with test queries, run the tests, and the framework
will compare against expected output.

## Files

1. Create a new `.sql` file under `src/test/regress/sql/` — call it after your
   feature, e.g. `mystringfn.sql`. Put SELECTs in it that exercise the function:
   typical inputs, NULLs, edge cases, error cases.
2. You'll also need an expected-output file under `src/test/regress/expected/`
   with the same base name. Write what the queries should produce.
3. Add the test name to the regression schedule so it actually runs — I believe
   it's `serial_schedule` or `parallel_schedule` in `src/test/regress/`.

## Generating the expected output

Rather than handwriting `expected/mystringfn.out`, run the test once with an
empty/placeholder expected file. The framework writes actual output to a
`results/` directory; you can then copy that into `expected/` after eyeballing
it.

Something like:

```bash
cd src/test/regress
make check
cp results/mystringfn.out expected/mystringfn.out
```

(Adjust for meson if that's what the build uses — `meson test` from the build
directory.)

## Running just your test

```bash
cd src/test/regress
./pg_regress mystringfn
```

or rerun `make check` to re-run the whole regress suite.

## When it fails

The framework writes a diff somewhere under the build/test output directory —
look for `regression.diffs`. Make sure your expected output doesn't depend on
anything volatile (timestamps, generated OIDs, parallel-row ordering).
