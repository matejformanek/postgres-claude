---
source_url: https://wiki.postgresql.org/wiki/Regression_test_authoring
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: mechanics page; the schedule-file format and copy-results-to-expected
  workflow are stable. Pairs with the `testing` skill for the regress-vs-iso-vs-TAP
  decision and the exact meson/make invocations Claude runs.
---

# Wiki distilled — Regression test authoring

The nuts-and-bolts of adding a `pg_regress` test: where the files live, the
schedule-file grammar, and the canonical "run once, eyeball the diff, copy
results→expected" loop. The `testing` skill decides *which* flavor to use; this
page is the *how* for the SQL/expected-output flavor.

## What the wiki page says

- **Tests live in `src/test/regress/`.** `sql/foo.sql` holds the commands,
  `expected/foo.out` the reference output, `results/foo.out` the actual output
  of the last run. [from-wiki]
- **Two schedule files, two drivers:** `parallel_schedule` is consumed by
  `make check`; `serial_schedule` by `make installcheck`. Add a new test's name
  to **both** for consistent coverage. [from-wiki]
- **Schedule grammar:** lines starting `test:` define tests; blank lines and
  trailing-`#` lines are ignored. **Multiple names on one `test:` line run in
  parallel**; a lone name runs by itself. `parallel_schedule` allows up to ~20
  names per parallel group. [from-wiki]
- **One "feature" per SQL file** is the convention — the harness lists each file
  as its own test item. [from-wiki]
- **The expected file echoes the input.** `expected/foo.out` contains not just
  query results but the SQL text itself, *including comments* — because
  `pg_regress` diffs the psql session transcript, not just result sets. This is
  why a stray comment edit can "break" a test. [from-wiki]
- **The authoring loop:** write `sql/foo.sql` → run the suite once → inspect
  failures → if `results/foo.out` is what you wanted, copy it to
  `expected/foo.out` → run again to confirm green. [from-wiki]
- **Determinism is on you.** Because the diff is exact-text, output must be
  reproducible: add explicit `ORDER BY` (heap/scan order is not guaranteed),
  avoid printing OIDs / timestamps / row counts that vary, and avoid
  timing-dependent output. [inferred, from-wiki authoring-loop implications]
- **Ignore list ≠ skip.** A test on `pg_regress`'s ignore list still *runs*;
  only its failure is ignored — useful for a known-unstable test without
  removing coverage. [from-wiki]
- **`.source` templated tests** (`input/*.source`, `output/*.source`) exist for
  tests needing filesystem paths; preprocessing substitutes `@abs_srcdir@`
  (source tree, for data files under `data/`) and `@abs_builddir@` (build tree —
  differs under VPATH/out-of-tree builds) before they become runnable
  `sql/`+`expected/` files. [from-wiki]
- **For tricky expected-output updates across variants, the `merge` tool** (RCS
  package) can three-way-reconcile: e.g.
  `merge output/largeobject.source expected/largeobject.out results/largeobject.out`.
  [from-wiki]

## How this maps to what Claude does

- This is the `pg_regress` half of the `testing` skill; the skill also covers
  isolationtester (concurrency/deadlock specs + permutations) and TAP
  (multi-node `PostgreSQL::Test::Cluster`) which this page does not. [inferred]
- The "copy results/ → expected/" step is exactly what Claude does after adding
  a behavior change under `/pg-implement`, and the determinism rules are why a
  generated `.out` sometimes needs an `ORDER BY` added to the `.sql`. [inferred]
- R11 (test-first when changing behavior) means the new `sql/` + `expected/`
  pair lands in the *same* phase as the code change, not a follow-up. [inferred]

## Links into corpus

- [[knowledge/conventions/testing.md]] — regress vs isolation vs TAP overview.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the tests-AND-docs gate
  that makes a regress test mandatory for a behavior change.
- [[knowledge/community/patch-workflow.md]] — where running the suite fits the flow.
- Skill: `testing` — flavor selection + the meson `--suite`/`--test` invocations.
- Skill: `pg-implement` — drives the per-phase test run (R4 phase-end check).
- Command: `/pg-test` — runs the suites against the dev build.

## Confidence note

Schedule-file/workflow claims are `[from-wiki]` (page fetched 2026-06-05). The
determinism guidance is `[inferred]` from the exact-text-diff mechanism the page
describes plus general PG practice. No source-code cites — mechanics page.
