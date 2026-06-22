---
source_url: https://www.postgresql.org/docs/current/regress-coverage.html
fetched_at: 2026-06-22T00:00:00Z
anchor_sha: 031904048aa2
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §33.5: Test Coverage Examination

How to measure which C lines the test suite actually exercises. The
quantitative backstop to R14 ("comprehensive own-test-suite") — if you want
to *prove* a new code path is tested rather than assert it, this is the tool.

## Prerequisites

- Requires **GCC**, **`gcov`**, and **`lcov`** installed. `[from-docs]`
- Coverage is a build-time instrumentation flag, so it needs a dedicated
  build (don't mix it into your normal debug tree). `[inferred]`

## Autoconf / make workflow

```bash
./configure --enable-coverage ... OTHER OPTIONS ...
make
make check                 # or any other test suite
make coverage-html         # HTML report → coverage/index.html
```

- `make coverage` is the text alternative: emits a `.gcov` file per source
  file instead of HTML. `[from-docs]`
- **Caveat:** `make coverage` and `make coverage-html` overwrite each
  other's output — pick one per session. `[from-docs]`
- `make coverage-clean` resets execution counters between runs;
  **counts accumulate across test runs** otherwise (run multiple suites,
  then report once, to get aggregate coverage). `[from-docs]`
- `make distclean` for full cleanup. Reports can be generated in a
  **subdirectory** to scope coverage to just that part of the tree.
  `[from-docs]`

## Meson workflow

```bash
meson setup -Db_coverage=true ... OTHER OPTIONS ... builddir/
meson compile -C builddir/
meson test -C builddir/
cd builddir/ && ninja coverage-html
# report → ./meson-logs/coveragereport/index.html
```

`[from-docs]`

## The flag cheat-sheet

| build system | enable flag          | report target        | report path                                   |
|--------------|----------------------|----------------------|-----------------------------------------------|
| autoconf     | `--enable-coverage`  | `make coverage-html` | `coverage/index.html`                         |
| meson        | `-Db_coverage=true`  | `ninja coverage-html`| `meson-logs/coveragereport/index.html`        |

`[from-docs]`

## Why a corpus-mining routine cares

- A `pg-quality-auditor` / R14 review can use coverage to falsify a "this is
  well tested" claim: run the feature's own suite under coverage and check
  the new `.c` lines light up. Accumulation-across-runs means you can layer
  regress + isolation + the feature's TAP suite and read one combined
  report. `[inferred]`

## Links into corpus

- The suites whose reach you're measuring:
  [docs-distilled/regress-run.md](./regress-run.md),
  [docs-distilled/regress-tap.md](./regress-tap.md)
- Relevant skills: `testing`, `build-and-run`. R14's comprehensive-suite
  mandate is the *qualitative* requirement; this chapter is how you put a
  *number* on it.
