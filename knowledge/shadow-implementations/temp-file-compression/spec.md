---
slug: temp-file-compression
thread-url: https://www.postgresql.org/message-id/flat/CAFjYY%2BJJ3x-QUBpSYr5eTdapERhS9Nw3SEAH%2BQnBB%3DkypoXUJw%40mail.gmail.com
first-message-url: (original COVER not directly fetched — used the v2 patch announcement as the canonical recent COVER)
v2-cover-url: https://www.postgresql.org/message-id/CAFjYY%2BJJ3x-QUBpSYr5eTdapERhS9Nw3SEAH%2BQnBB%3DkypoXUJw%40mail.gmail.com
key-reply-url: https://www.postgresql.org/message-id/29c87c10-fdbc-4d0f-b0f4-15e14dd36bce%40vondra.me
author: Filip Janus <fjanus@redhat.com>
captured-at: 2026-06-13
captured-anchor: e18b0cb7344
posted-at: 2024-11-18T21:58:27 (v2 patch)
cf-entry: CF 2025-03 (active)
shadow-run-status: SPEC EXTRACTED; PLAN + COMPARISON DEFERRED (M2/M3/M5-enhanced pg-feature-plan lands via PR #168)
---

# Spec extracted from pgsql-hackers thread

## Context awareness (M2 pre-step from `pg-feature-plan`)

Per the M2 context-awareness step added via PR #168:

- **Posting date:** 2024-11-18. Not April-1, not within 2 weeks of
  a release-branch cut. Realistic CF target: CF 2025-03 (which is
  where the entry currently lives, per the public CF tracker).
- **Author posture:** Filip Janus (Red Hat). Per
  `knowledge/personas/archive-participants.md`, classified as a
  "pure-archive author" — proposing his own work, no merged
  trailer yet, but a sustained engagement on this thread (v1 → v2
  → compiler-warning fix). Real proposal worth treating
  seriously, not speculative.
- **Engagement class (M5):** `debated`. Tomas Vondra's reply
  (2024-11-20) is constructively critical with 5 concrete asks:
  algorithm choice, memory allocation, scope limitation, testing,
  benchmark rigor. Plan should enumerate the open questions as
  §13 risks (per M5 rule for `debated`), not paper over them.

## What this does (verbatim claim from COVER)

The patch introduces temporary-file compression to reduce:
- Disk I/O overhead when queries spill to disk.
- Storage space for large temporary datasets.
- Query execution time when temporary files are required.

**Claimed design:**

- **Scope:** hashjoin spill files first (`nodeHashjoin.c` /
  `nodeHash.c` writing through `BufFile`). Future expansion to
  sorts, GiST index creation, "etc."
- **Algorithm:** LZ4 chosen initially; author explicitly
  acknowledges pglz might be better starting choice.
- **Mode:** block-mode compression (one compress call per
  buffer write). Stream mode considered for future.
- **Activation:** new GUC (default `'none'`); caller path opts in
  via `BufFileCreateTemp(compress=true)` (inferred from Vondra's
  reply mentioning the parameter).
- **v2 patch artifact:**
  `0001-This-commit-adds-support-for-temporary-files-compres-v2.patch`
  (13.4 KB).

**Author's stated benchmarks (single-run, machine specs not given):**

| Dataset | Compressed? | Temp Usage | Exec Time | `work_mem` |
|---|---|---|---|---|
| A (highly compressible) | yes | 3.09 GiB | 22.586 s | 4 MB |
| A | no | 21.89 GiB | 35.000 s | 4 MB |
| B (less compressible) | yes | 333 MB | 1.816 s | 4 MB |
| B | no | 146 MB | 1.500 s | 4 MB |
| C (realistic) | yes | 40 MB | 1.011 s | 1 MB |
| C | no | 53 MB | 1.034 s | 1 MB |

Headline: ~20 GB → 3 GB on highly compressible data with ~13 s
speedup; minimal overhead on incompressible data. (Vondra
flagged the methodology — see §"Open questions".)

## Touched subsystems (per our `domain-ownership.md` lookup + inferred)

- `src/backend/storage/file/buffile.c` — `BufFile` API; the
  primary surface this patch extends.
- `src/include/storage/buffile.h` — public API (new
  `BufFileCreateTemp(compress=true)` parameter).
- `src/backend/executor/nodeHashjoin.c` + `nodeHash.c` — caller
  sites opting into compression on the spill files.
- `src/backend/utils/misc/guc_tables.c` — new GUC registration
  (likely `temp_file_compression` with values `none` / `pglz` /
  `lz4`).
- `src/common/pg_lzcompress.c` (pglz) or `src/common/file_perm.c`
  + LZ4 bindings — compression primitives. Build dependency on
  `--with-lz4` for the LZ4 path.
- `doc/src/sgml/config.sgml` — new GUC documentation.
- `src/test/regress/sql/` — regression test (gated on availability
  of the algorithm; per Vondra, this is one of the open questions).

Owners (per `domain-ownership.md`):
- **`storage-buffile`** sits inside the broader `storage` cluster.
  Active committers on `buffile.c` over the last 24 months:
  Heikki Linnakangas, Thomas Munro, Andres Freund.
- **Hash join** (`executor`): Heikki Linnakangas, David Rowley,
  Thomas Munro.
- **Compression / `pg_lzcompress`**: Tom Lane (historical),
  Andres Freund (recent), Tomas Vondra (LZ4 work).

## Predicted reviewer set (per Phase C calibration patterns)

| Rank | Reviewer | Why |
|---|---|---|
| 1 | **Tomas Vondra** | Already engaged on the thread with 5 concrete asks; lead candidate to commit when the asks are addressed. |
| 2 | Heikki Linnakangas | `BufFile` + executor hash-join expertise; likely to validate the spill-path interaction. |
| 3 | Thomas Munro | Async / parallel angle; sharedtuplestore implications. |
| 4 | Andres Freund | Performance reflex on memory-allocation patterns (echoes Vondra's §2 concern). |
| 5 | Tom Lane | Universal style + correctness reviewer; will check the `BufFile` ABI implications. |
| 6 | Filip Janus (author) | Multi-round respondent. |

## Open questions raised in thread before this shadow run

Tomas Vondra's reply (2024-11-20) raised five concrete asks. These
become the plan's §13 "Known risks" entries per the M5 `debated`
rule:

1. **Algorithm choice (V1).** "Start with `pglz` instead of LZ4 —
   pglz is built-in and universally available; LZ4 needs
   `--with-lz4` at build time. Other algorithms (zstd, etc.) come
   later." This is a design-level disagreement, not a nit.

2. **Memory allocation (V2).** Per-compression `palloc` / `pfree`
   calls will be expensive for large (>8 KB) buffers. Adding
   buffers to the `BufFile` struct would double memory overhead
   for hash joins (which already consume massive amounts).
   **Suggested alternative:** pass a single reusable buffer as
   a function argument from the caller.

3. **Scope limitation (V3).** Patch enables compression for hash
   join spill files only. Why not sorts, index creation,
   reorderbuffer spills, materialize nodes? Vondra hypothesizes
   that **compressed files don't support random access**, which
   may be the limiting factor (sort spills are read sequentially,
   so should work; index creation may need random access).

4. **Testing gap (V4).** Regression tests won't exercise
   compression by default (GUC defaults to `'none'`). Two
   alternatives proposed:
   - Explicit regression test with `SET temp_file_compression`
     override (won't work if LZ4 is unavailable at build).
   - New env var `PG_TEST_USE_COMPRESSION` set in CI to force
     compression on for the whole regress suite.

5. **Benchmark rigor (V5).** Are results single-run or averaged?
   Need reproduction script + machine specs. Page-cache effects
   may obscure I/O savings — clear the page cache between runs
   or run with cold cache.

Additional minor request:
- Document when `compress=true` is legal in `BufFileCreateTemp()`
  (caller-contract clarification).

## Phase 0 gates that apply (per `review-checklist` Phase 0)

| Gate | Triggers? | Note |
|---|---|---|
| 1 `security@` embargo | ✗ | Not a vulnerability fix. |
| 2 Test-omission | partial | Vondra V4 above; the plan will explicitly resolve this rather than skip. |
| 3 Install-script immutability | ✗ | No `--*.sql` changes. |

## REJECT-track decision (per `review-checklist` Phase 0 M4)

**Not a REJECT-track candidate.** Engagement is `debated` not
`contested`; no documented INV is foreclosed; the design is
implementable with the V1-V5 asks addressed. Proceed to phased
plan when M2/M3/M5-enhanced `pg-feature-plan` is available.

## What this shadow run will produce next (deferred)

Once PR #168 lands (M2/M3/M5 in `pg-feature-plan`) and PRs #167-#170
merge to give the full backbone:

1. **`plan.md`** — heavy plan per `pg-feature-plan` §3-§13. Will
   address Vondra's V1-V5 in §13. Most likely shape:
   - V1 (algorithm): pick `pglz` as the MVP path; LZ4 behind a
     compile-time flag. The plan's §1 "Picked approach" reflects
     this.
   - V2 (memory): reusable-buffer-per-caller pattern. §7
     "Memory + resource management".
   - V3 (scope): start with hashjoin AND sorts (both sequential
     paths). Defer index-creation / reorderbuffer. §2 "Scope
     contract".
   - V4 (testing): `PG_TEST_USE_COMPRESSION` env var pattern,
     per `daniel-gustafsson.md` online-checksums precedent
     (catalog item 2 in `gap-catalog.md`). §9 "Test surface".
   - V5 (benchmarks): the plan's §13 risks should require a
     reproduction recipe before commit; not blocking on the
     planner side.

2. **`comparison.md`** — diff between the produced plan and
   Filip's actual v2 patch:
   - Did the planner address V1-V5 in line with Vondra's
     concerns?
   - Did the planner miss any concern Vondra raised?
   - Did the planner raise novel concerns Vondra did NOT?
   - File:line accuracy on the cited sites.

3. **`skill-gaps.md`** — any methodology / skill improvements
   surfaced by this run.

## Cross-references

- `knowledge/calibration/shadow-implementation-methodology.md`
  — the recipe this shadow run follows.
- `knowledge/shadow-implementations/money-fx-exchange/` — Phase E
  run 1 (REJECT-A grade; surfaced M1-M5 methodology fixes).
- `knowledge/personas/archive-participants.md` — Filip Janus's
  archive-only-author classification.
- `knowledge/personas/tomas-vondra.md` (if present) — Vondra's
  reviewer reflexes; performance + memory-allocation focus.
- PR #168 (`ft_skills_planner_suite`) — M2/M3/M5 enhancements
  this run will use when running the plan step.
