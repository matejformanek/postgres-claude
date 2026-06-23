---
source_url: https://www.postgresql.org/docs/current/regress-evaluation.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §33.2: Test Evaluation

How pg_regress decides pass/fail, and the taxonomy of *spurious* failures
that look like regressions but aren't. This is the chapter to re-read
whenever a phase-end check shows a red that "shouldn't" be red.

## The comparison mechanism — it's just `diff`

- Each test's actual output lands in `src/test/regress/results/<test>.out`;
  pg_regress runs **`diff`** against the reference in
  `src/test/regress/expected/<test>.out`. Any differences are concatenated
  into **`src/test/regress/regression.diffs`** for inspection. `[from-docs]`
- Override diff flags via `PG_REGRESS_DIFF_OPTS` (e.g.
  `PG_REGRESS_DIFF_OPTS='-c'` for context diffs). `[from-docs]`
- Corollary: a "failed" test means *byte-different output*, NOT necessarily
  a bug. The whole rest of the chapter is about telling the two apart.

## The six classic sources of spurious failures

1. **Error-message wording** — system-routine error strings differ across
   platforms; the test "fails" but conveys the same information. `[from-docs]`
2. **Locale / collation sort order** — a server initialized with a
   collation locale other than `C` produces different row orders in
   sort-dependent output. Run `make check NO_LOCALE=1` or a specific
   `LANG=` to match the reference files. `[from-docs]`
3. **Date / time** — reference files are generated for time zone
   **`America/Los_Angeles`**. The driver sets `PGTZ=America/Los_Angeles`
   to force this; failures appear if that doesn't take effect. `[from-docs]`
4. **Floating point** — `double precision` math from table columns varies
   by platform and even by **compiler optimization level**. The `float8`
   and `geometry` tests are the most fragile. Edge cases: minus-zero shown
   as `-0` vs `0`; `pow()`/`exp()` error-signaling differences. `[from-docs]`
5. **Row ordering** — most scripts deliberately omit `ORDER BY`, so row
   order is unspecified per SQL and may differ by platform, locale, or
   non-default `work_mem` / planner cost GUCs. **Not a bug** unless an
   explicit `ORDER BY` is violated. `[from-docs]`
6. **The `random` test** — intentionally produces random output; in very
   rare runs it genuinely fails. `diff results/random.out
   expected/random.out` should show only a line or two. `[from-docs]`

## Two non-locale failure modes worth flagging

- **Stack depth**: if the `errors` test crashes the server at
  `select infinite_recurse()`, the OS stack-size limit is smaller than
  `max_stack_depth` claims. Fix by raising the OS limit (≈4MB) or lowering
  `max_stack_depth`. `[from-docs]`
- **Non-default GUCs under installcheck**: settings like `enable_seqscan` /
  `enable_indexscan` change plans and break any `EXPLAIN`-based test. A
  reason `make check` (clean temp instance) is more reproducible than
  installcheck against a tuned cluster. `[from-docs]`

## When the failure is genuinely valid output

If inspection convinces you a platform's differing output is correct, you
add a **variant comparison file** rather than editing the canonical
`expected/<test>.out` — see §33.3. `[from-docs]` This is the legitimate
path; never "fix" a test by loosening the canonical expected file to match
a platform quirk.

## Links into corpus

- The harness that produces these files:
  [docs-distilled/regress-run.md](./regress-run.md)
- The variant / resultmap mechanism this chapter defers to:
  [docs-distilled/regress-variant.md](./regress-variant.md)
- Relevant skills: `testing`. The R4 "phase-end check must pass" rule
  assumes you can distinguish a real red from a spurious one — this
  chapter is that decision table.
