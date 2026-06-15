---
date: 2026-06-15
session: A23 — Phase A 100% close-out
agents: 12 parallel (wave 1) + 1 cleanup (A12)
outcome: 100% file-by-file coverage of src/ + contrib/ achieved
---

# Session — Phase A CLOSED: 100% file-by-file coverage

## Starting state

- `progress/coverage.md` (refreshed 2026-06-10) claimed 74.4% (1,908 / 2,564
  docs), gap ~656 files.
- `progress/STATE.md` head said "Phase A done (substantive 100%)" but
  considered ~416 mechanical files (`src/port`, `src/interfaces`, `src/test`,
  `src/backend/snowball`, `src/include/snowball`) deferred to the
  `pg-file-backfiller` cloud routine, not foreground work.
- User redirected: "Ok ur quest is to make sure we get to 100% coverage go
  through tests and def backend include and all really making sure we get to
  the 100% do not stop until i tell u to". Explicit instruction overrode the
  deferred-mechanical posture.

## Method

1. **Live re-computation of the gap** at anchor `e18b0cb7344` using stem-pair
   matching (`<path>.md` OR `<stem>.md` counts as covered). This dropped the
   gap from the stale 656 to **355 strictly-missing files** — about half the
   stale number, because earlier waves had used the stem-pair convention
   without updating the coverage table.

2. **Per-directory gap inventory** showed:
   - `src/backend` 84 (snowball 55 + mb/conversion_procs 19 + port 10)
   - `src/include` 70 (snowball 56 + port subdirs 6 + jit 5 + pch 3)
   - `src/common/unicode` 3
   - `src/port` 50 (win32 shims + libc fallbacks + CRC32C SIMD ladder)
   - `src/interfaces/ecpg` 74 (5 real + 69 generated `test/expected/*.c`)
   - `src/test` 74 (60 modules + 4 regress + 3 isolation + 6 examples + 1 locale)

3. **Twelve agents dispatched in one parallel wave** (A1–A11, with A7 split
   into A7a + A7b) covering all 355 files. Each agent received:
   - The exact list of source-file paths
   - Frontmatter template (`path / anchor_sha / loc / depth`)
   - Body structure (`## Purpose / Public symbols / Internal landmarks /
     Invariants & gotchas / Cross-refs`)
   - Confidence-tag rules (`[verified-by-code]` / `[from-comment]` etc.)
   - Pointer to two exemplar docs (`getpeereid.c.md` + `explicit_bzero.c.md`)

4. **One cleanup agent (A12)** picked up 5 modules I had mis-listed in A7a's
   prompt — the actual A7a.lst file held 5 different modules at positions
   26-30 than what the prompt's hardcoded list described. The agent read
   from the live `/tmp/pg-batch/A7a.lst` would have caught it; the lesson is
   to pass paths via file reference, not inline lists, when the inline list
   diverges from the underlying file.

## Output

- **354 new per-file docs** (substantive cite-rich for high-value files,
  thin 5-10 line stubs for machine-generated stemmers + ecpg golden outputs).
- **3 collective READMEs**:
  - `knowledge/files/src/interfaces/ecpg/test/expected/README.md` —
    explains the generated-output regression suite + naming convention +
    regeneration flow + categories.
  - `knowledge/files/src/backend/snowball/libstemmer/README.md` — auto-
    generated Snowball stemmers, deferral rationale, file naming, upstream
    provenance, regeneration via `src/tools/snowball-build/`.
  - `knowledge/files/src/include/snowball/README.md` — companion header
    directory, encoding axis × language matrix, deferral rationale.
- **1 substantive `snowball_runtime.h.md`** — three jobs of the PG shim
  (postgres.h-first, MAXINT/MININT undef, palloc redirect) + public-symbols
  table.
- **377 registry rows** appended to `progress/files-examined.md`.

## Findings worth graduating to `knowledge/issues/`

These surfaced during the per-file reads and belong in the relevant issue registers:

- **`win32error.c`** has a duplicate `ERROR_INVALID_HANDLE` mapping
  (lines 42-44 → `EBADF`, lines 120-122 → `EINVAL`). First match wins, so
  the second entry is effectively dead code. → `knowledge/issues/port.md`
- **`win32setlocale.c`** uses a single shared 100-byte static buffer for
  both input and output mappings — thread-unsafe. → `knowledge/issues/port.md`
- **`win32fdatasync.c`** depends on the undocumented `NtFlushBuffersFileEx`
  from ntdll to get true `fdatasync`-flavored flush (the documented
  `FlushFileBuffers` is `fsync`-flavored — slower). → `knowledge/issues/port.md`
- **`win32stat.c`** reports Windows directory junctions as `S_IFLNK`, which
  is load-bearing for PG tablespace handling. → tablespace cross-ref.
- **`pqsignal.c`** uses an `MyProcPid != getpid()` check to defend against
  signal handlers running in `system(3)`-forked children that would otherwise
  corrupt shared memory. → idiom worth surfacing in `knowledge/idioms/`.
- **`qsort_arg.c`** differs from glibc's `qsort_r` in argument order vs.
  BSD's — cross-platform footgun. → `knowledge/issues/port.md`
- **`pg_regress.c`** convention drift: the brief still referenced the
  `convert_sourcefiles` / `@abs_builddir@` template mechanism; current code
  uses `PG_ABS_SRCDIR` + `PG_ABS_BUILDDIR` env vars set by
  `initialize_environment()` (`pg_regress.c:745-746`). Brief was stale by
  ~years. → corpus correctness note.
- **`regress.c`** no longer has `trigger_check`; closest current entry is
  `trigger_return_old` at `:263`. → brief-correction note.
- **`ecpg test/expected/preproc-describe.c`** has no matching
  `preproc/describe.pgc` and is not listed in `ecpg_schedule` — orphan kept
  in the tree, no longer reachable from the test driver. → `knowledge/issues/ecpg.md`
- **`win32common.c`** + **`win32dlopen.c`** + **`win32setlocale.c`** all
  share thread-unsafe statics; common Windows thread-safety pattern worth
  documenting as an idiom.
- **`test_checksums`** depends on `--enable-injection-points`; every SQL
  entry errors if that build option isn't set. Cross-module dependency
  test_aio ↔ injection_points worth surfacing.
- **`pg_numa.c`** does chunked `move_pages()` calls to work around a Linux
  kernel bug — note the kernel-version threshold.
- **`pgcrypto/decompress`** (already in `issues/pgcrypto.md`) cross-validates
  with the new ecpg `expected/` golden orphan: stale committed artifacts.

## Next steps (not done in this session)

1. Mine the per-file docs for new `[ISSUE-*]` tags and append rows to
   `knowledge/issues/{port,ecpg,test,snowball}.md`.
2. Re-anchor older `4b0bf0788b0`-tagged docs to `e18b0cb7344` (the
   `pg-anchor-refresh` cloud routine's job; it has 1,500+ candidates).
3. Retire `pg-file-backfiller` cloud routine or repurpose to anchor refresh.
4. Resume Phase E (skill-creator audit + shadow-implementation calibration).

## Stats

- Total new artifacts: **358** (354 per-file + 3 READMEs + 1 substantive runtime)
- Registry rows appended: **377** (includes a few pre-existing doc fixes)
- Source files now covered: **2,564 / 2,564 (100.0%)**
- Doc files total: **2,580** (excess over source count = READMEs + stem-pair
  docs covering companion artifacts)
- Anchor: `e18b0cb7344` (post-A18 refresh from 2026-06-10)
- Wall-clock from gap-inventory to 100%: ~30 minutes (parallel-agent fan-out)
- Parallel agents in main wave: 12

## Closes

- `progress/coverage-gaps.md` — retired as work queue, kept as history
- `pg-file-backfiller` cloud routine — its mandate is complete

## Cross-refs

- `progress/coverage.md` — updated with 100% across all 11 trees
- `progress/STATE.md` — Phase A CLOSED entry prepended
- `progress/files-examined.md` — 377 new rows
