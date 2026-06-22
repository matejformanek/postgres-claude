---
source_url: https://www.postgresql.org/docs/current/regress-variant.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §33.3: Variant Comparison Files

The two mechanisms for "the same test legitimately produces different
output on different platforms." Knowing these stops you from
mis-"fixing" a canonical expected file when a platform variant is the
right answer.

## Mechanism 1 — `resultmap` (explicit platform → file mapping)

- File: `src/test/regress/resultmap` `[verified-by-code]`
  (`source/src/test/regress/resultmap` exists at the anchor SHA). `[from-docs]`
- One line per mapping, format:

  ```
  testname:output:platformpattern=comparisonfilename
  ```

  - **testname** — the regression module name.
  - **output** — which output stream; for standard regress tests always
    `out`.
  - **platformpattern** — a regex in Unix `expr` style with an **implicit
    `^` anchor**, matched against the platform name emitted by
    `config.guess`.
  - **comparisonfilename** — base name of the substitute expected file.
  `[from-docs]`
- Worked example:

  ```
  float4:out:.*-.*-cygwin.*=float4-misrounded-input.out
  ```

  On any host whose `config.guess` matches `.*-.*-cygwin.*`, pg_regress
  compares against `float4-misrounded-input.out` instead of
  `float4.out`. `[from-docs]`

## Mechanism 2 — best-match numbered variants (no resultmap entry)

- Naming convention: the standard file is `testname.out`; variants are
  `testname_0.out` … `testname_9.out` (single digit). `[from-docs]`
- Selection algorithm in the driver:
  1. Consider `testname.out` plus all `testname_<digit>.out` variants.
  2. If **any** file is an exact match → the test passes.
  3. Otherwise report the failure using the variant that yields the
     **shortest diff**.
  4. If `resultmap` names a substitute base, that base replaces
     `testname` before this search. `[from-docs]`
- Canonical example — the `char` test:
  `char.out` holds results for `C`/`POSIX` locales; `char_1.out`
  (`source/src/test/regress/expected/char_1.out` `[verified-by-code]`)
  holds the ordering seen under many other locales. `[from-docs]`

## The important caveat

- Best-match selection **cannot know which variant is actually correct**
  for the current environment — it just picks the closest. So it is only
  safe when **all** variants are equally valid results. Use it for genuinely
  locale-/platform-indeterminate output, not to paper over a real
  divergence. `[from-docs]`

## Links into corpus

- Why you'd reach for a variant — the spurious-failure taxonomy:
  [docs-distilled/regress-evaluation.md](./regress-evaluation.md)
- The harness that consumes resultmap:
  [docs-distilled/regress-run.md](./regress-run.md)
- Relevant skills: `testing`. R14's "identifier / boundary / type-variety"
  own-test-suite should prefer explicit `ORDER BY` over relying on a
  variant file, so the suite is deterministic across platforms.
