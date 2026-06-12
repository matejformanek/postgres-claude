# `patches/` — Phase D staged patches dashboard

5 patches built during the 2026-06-09..10 Phase A sweeps, calibrated
through Phase C (2026-06-12), ready for refinement and send.

**All 5 remain PARKED. Sending requires explicit user re-auth.**

Each `patches/<slug>/` contains:
- `0001-*.patch` — the patch (formatted via `git format-patch`)
- `COVER.md` — the pgsql-hackers cover letter draft
- `notes.md` — Phase C calibration findings + pre-send checklist

## Send-order recommendation (refined 2026-06-12)

| Order | Patch | Verdict | Key blocker | Lead committer | Days estimate |
|---|---|---|---|---|---|
| 1 | **SP2** pgstr-maxalloc | **INVESTIGATE** | Non-UTF-8 encoding worst-case | Jeff Davis | 1-2 of work + ~5 days review |
| 2 | **CB7** ltree-amplification | **REFINE** | Cap-value arithmetic mismatch | Peter Eisentraut (Michael / Tom backpatches) | ~1 day work + ~5 days review |
| 3 | **CB1** pgcrypto-bomb | **GO** (embargo path) | None substantive; add regression test | Daniel Gustafsson | <1 day + ~5 days review |
| 4 | **CB8** hstore-forge | **REFINE** | `hstore_version_diag()` contract decision | Peter Eisentraut (Michael / Tom backpatches) | 1-2 days work + ~5 days review |
| 5 | **SP6** autoprewarm-revoke | **REFINE** | Drop 1.1→1.2 install-script edit | Tom Lane | <1 day + ~3 days review |

Total prep: ~5 days of refinement + ~25 days of review-thread time
spread across the 5 patches. Parallelizable in calendar but not in
attention — recommend sending one at a time, ~3 days apart, to keep
threads manageable.

## Cross-cutting gates (per `review-checklist` Phase 0)

| Gate | CB1 | CB7 | CB8 | SP2 | SP6 |
|---|---|---|---|---|---|
| 1 `security@` embargo | ✓ ask | ✓ ask | ✓ ask | ✓ ask | ✓ exemption argued |
| 2 Test-omission | ✓ add SQL regress | ✓ pre-empt'd | ✓ add fixture | ✓ add stress test | ✓ pre-empt'd |
| 3 Install-script | n/a | n/a | n/a | n/a | **MUST FIX** |

## Patch-content findings (from Phase C calibration)

| # | Patch | Finding | Resolution |
|---|---|---|---|
| F1 | **SP2** | 3× expansion bound may not hold for non-UTF-8 (GB18030, EUC_*) | Per-encoding worst-case analysis — open question |
| F2 | **CB7** | Cap value 131072 → claimed "~3 MB scratch" actually ~1 GB worst-case | Tighten cap OR rewrite COVER §3 |
| F3 | **CB8** | `hstore_version_diag()` behavior change is a contract change | Argue prior was a lie (recommend) OR deprecation cycle |
| F4 | **SP6** | Editing shipped `--1.1--1.2.sql` violates install-script immutability | Drop 1.1→1.2 edit; ship 1.2→1.3 only |
| F5 | **CB1** | Resource ownership question on early `return` | RESOLVED — cleanup runs via `decompress_free` at filter teardown |

F5 is closed. F1-F4 require user input / refinement work.

## Pre-send checklist (per-patch)

Each patch needs (from `notes.md`):

- [ ] **CB1** — security@, refine COVER with 4 findings, add regression test, get user re-auth
- [ ] **CB7** — security@, decide F2 (tighten cap recommended), refine COVER, move `#define` to header, get user re-auth
- [ ] **CB8** — security@, decide F3 (argue prior lie recommended), add fixture regression test, expand COVER with third-state enumeration, get user re-auth
- [ ] **SP2** — security@, investigate F1 (per-encoding worst-cases), refactor to helper, add Unicode TR citation, add micro-benchmark, add PG_TEST_EXTRA=stress test, get user re-auth
- [ ] **SP6** — drop 1.1→1.2 edit per F4, expand COVER with bgworker-unaffected + cascade-idempotency sentences, get user re-auth

## Committer routing (from Phase B + Phase C)

| Lead (To:) | CB1 | CB7 | CB8 | SP2 | SP6 |
|---|---|---|---|---|---|
| Daniel Gustafsson | ✓ | | | | |
| Peter Eisentraut | | ✓ | ✓ | | |
| Jeff Davis | | | | ✓ | |
| Tom Lane | | | | | ✓ |

| CC (review reflexes) | CB1 | CB7 | CB8 | SP2 | SP6 |
|---|---|---|---|---|---|
| Tom Lane | ✓ (backpatch) | ✓ (backpatch) | ✓ (backpatch + contract) | ✓ | (lead) |
| Michael Paquier | ✓ | ✓ (backpatch lander) | ✓ (backpatch lander) | ✓ | ✓ |
| Noah Misch | ✓ | ✓ (security@ + multibyte) | ✓ (security@) | ✓ (security@ + multibyte) | ✓ |
| Heikki Linnakangas | | | ✓ (binary format) | ✓ (perf) | ✓ |
| Jeff Davis | | ✓ (Unicode) | | (lead) | |
| Peter Eisentraut | ✓ (include) | (lead) | (lead) | ✓ (helper refactor) | ✓ (style) |
| Daniel Gustafsson | (lead) | | | | ✓ (test-module + TAP) |
| Nathan Bossart | | | | | ✓ (autoprewarm internals) |
| Thomas Munro | | | | ✓ (encoding) | |

**Cross-cutting note:** Tom Lane appears on EVERY patch's CC list —
ABI + backpatch + contract reviewer for the whole pile. He's the
de-facto co-reviewer of any Phase D submission.

## What Phase C bought us

5 calibration docs (`knowledge/calibration/cbN-*.md`, `spN-*.md`)
plus the consolidated `gap-catalog.md`. Each `notes.md` here cites
the calibration doc that drove its findings.

The Phase C catalog's 11 items showed up in these notes:

| Catalog item | CB1 | CB7 | CB8 | SP2 | SP6 |
|---|---|---|---|---|---|
| 1 security@ embargo gate | ✓ | ✓ | ✓ | ✓ | exemption |
| 2 Test-omission override | ✓ | n/a | ✓ | ✓ | n/a |
| 3 Install-script immutability | n/a | n/a | n/a | n/a | ✓ MUST-FIX |
| 4 Cleanup-on-early-return | ✓ resolved | n/a | n/a | n/a | n/a |
| 5 Multibyte/encoding | n/a | ✓ doc-add | n/a | ✓ MUST-INVESTIGATE | n/a |
| 6 Cap discoverability | n/a | ✓ move | n/a | n/a | n/a |
| 7 Third-state cross-check | n/a | n/a | ✓ doc-add | n/a | n/a |
| 8 injection_points reproducer | n/a | optional | n/a | n/a | n/a |
| 9 Hot-path microbenchmark | n/a | n/a | optional | ✓ add | n/a |
| 10 Symmetric-check refactor | n/a | n/a | n/a | ✓ refactor | n/a |
| 11 Persona-aware backpatch routing | n/a | ✓ CC | ✓ CC | n/a | n/a |

Every one of the 11 catalog items was triggered by at least one of
the 5 patches.

## Cross-references

- `knowledge/calibration/README.md` — Phase C methodology
- `knowledge/calibration/gap-catalog.md` — 11-item catalog
- `knowledge/calibration/{cb1,cb7,cb8,sp2,sp6}-*.md` — per-patch
  calibration source
- `.claude/skills/review-checklist/SKILL.md` — Phase 0 gates
- `.claude/skills/pg-patch-review/SKILL.md` — Critic E reflexes
- `knowledge/personas/*.md` — committer/reviewer style references
