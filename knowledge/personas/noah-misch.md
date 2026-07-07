---
name: Noah Misch
email: noah@leadboat.com
role: Senior committer; correctness/durability/security specialist
active_24mo: yes
first_commit_year: 2010 (long-tenured)
landmark_24mo_areas: inplace update correctness, SQL injection / privilege fixes, encoding validation, pg_dump determinism
---

# Noah Misch

## Activity profile (24 months ending 2026-06-12)

- **87 commits** (per `committer-map.md` row, 20 in 12mo). Most are
  small, surgical, with multi-paragraph commit bodies that name the
  exact race / encoding / overflow class fixed.
- **Top paths** (file-touches, 24mo):
  - `src/test/regress` (38), `src/test/modules` (33) — every behavior
    fix lands with a regression test, often a brand-new isolation or
    injection-points fixture.
  - `src/backend/utils` (32) — encoding, multibyte, inplace-update
    helpers.
  - `src/backend/access` (28), `src/include/storage` (12) — the
    inplace-update durability series + heap-AM correctness work.
  - `src/backend/commands` (17), `src/bin/pg_dump` (16) — dump-restore
    determinism work (OID-independent sort orders).
  - `src/backend/catalog` (13), `src/pl/plperl` (13) — assorted
    correctness sweeps.
- **29 of his 87 commits (33%) name a fix/bug/leak/race/security
  class explicitly** in the subject — much higher than any other top
  committer's "fix"-share. Noah's commit shape is "this exact failure
  mode, this exact fix."
- **Backpatching:** subject lines don't carry a "backpatch" tag (he
  uses the `git` commit-body convention), but the inplace-update
  series (`aac2c9b`, `8e7e672`, `30d47ec`, `0bada39`, `e947224`) was
  backpatched aggressively. Treat him as a high-backpatch committer
  for correctness fixes.
- **Reviewer footprint** (`Reviewed-by: Noah Misch` in 24mo,
  committer view): **42× for Andres Freund**, 8× Nathan Bossart,
  6× Sawada, 5× Heikki, 4× Tom Lane, 4× Michael Paquier, 3× Munro,
  3× Davis, 3× Champion. **The Andres link is the most concentrated
  reviewer-of pair in the corpus** — Noah is effectively Andres's
  standing reviewer for the storage/AIO work.

## Domain ownership

- **Inplace-update correctness / durability** — primary owner. The
  series fixing data loss at inplace update after `heap_update()`
  (`aac2c9b`), the WAL-log-before-reveal patch (`8e7e672`), the
  uninitialized-memory read in `heap_inplace_lock()` (`e947224`),
  the unpin-buffer-before-XID-wait fix (`30d47ec`), the self-deadlock
  fix (`0bada39`), and the cosmetic revisit (`64bf53d`) are all his.
  Nobody else has touched this code path in 24mo.
- **pgcrypto encoding-validation** — `d536aee` "Require PGP-decrypted
  text to pass encoding validation" plus `c5dc7547` "Fix test 'NUL byte
  in text decrypt' for --without-zlib builds". Specifically tracks the
  pgcrypto-decompression → text-output path — directly relevant to
  CB1's calibration (this routing made him a predicted reviewer of CB1
  in `cb1-pgcrypto-bomb.md`).
- **GB18030 / multibyte SIGSEGV class** — `627acc3` "With GB18030,
  prevent SIGSEGV from reading past end of allocation" and `9f4fd11`
  "Fix SUBSTRING() for toasted multibyte characters". When a patch
  touches encoding conversion or `pg_mblen*`, expect Noah's eyes.
- **`pg_dump` determinism** — five separate commits in 24mo on
  "Sort DO_* dump objects independent of OIDs" (`0decd5e`, `b61a5c4`,
  `d49936f`, others). The dump-restore determinism cluster is his.
- **SQL injection / privilege fixes** — `46b4f5c` "Fix SQL injection
  in logical replication origin checks" is the recent flagship.

## Style patterns (`%an = Noah Misch` body conventions)

- **Commit bodies name the precise failure mode.** Not "fix a bug"
  but "stop reading uninitialized memory in `heap_inplace_lock()`"
  with the line range and the trigger condition. R6 of the
  implementation discipline (cite or don't claim) is observably his
  baseline.
- **Tests live in the same commit as the fix.** Every correctness
  commit in the 24mo window lands its test (`src/test/regress` +33,
  `src/test/isolation` +22, `src/test/modules` +33 across 87
  commits is well above project average). When asked "where's the
  test?", his answer is in the diff.
- **Injection-points discipline.** He maintains the
  `src/test/modules/injection_points` machinery and uses it heavily
  for race-condition reproducers (`4f6ec38` "Disable runningcheck
  for src/test/modules/injection_points/specs" is meta-work on the
  fixture itself).
- **Multi-version backpatch cadence.** When he backpatches the
  inplace-update series, he backpatches everything that
  semantically belongs together — not piecemeal.
- **Reverts > amendments.** `64bf53d` "Revisit cosmetics of [...]"
  is a *follow-on cosmetic commit* rather than an `--amend`. Same
  discipline as R-Anti-pattern in the meta repo's
  pg-implement-discipline.


## Scenarios I'd review
<!-- persona-scenarios:auto -->

*Derived from Domain-ownership paths overlapping each scenario's §Files section. If this persona claims a directory and a scenario mentions any file under it, they're a likely reviewer.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none — persona has no owned paths that overlap any scenario's files)_

<!-- /persona-scenarios:auto -->


## Subsystems I know
<!-- persona-subsystems:auto -->

*Derived from Domain-ownership paths overlapping each subsystem's `## Files owned` block.*
*Refresh via `scripts/build-persona-scenario-matrix.py`.*

_(none)_

<!-- /persona-subsystems:auto -->

## What to expect on a patch he would review

The CB1 calibration in `knowledge/calibration/cb1-pgcrypto-bomb.md`
already enumerated Noah's predicted feedback shape for that specific
patch. Generalized:

1. **"Where's the test?"** Confidence: very high. Any behavior-change
   patch without a regression test (or a stated reason for not adding
   one, with reviewer-acceptance) will get this comment first. The
   "this is a structural fix, the failure mode is hard to fixturize"
   argument has to be made explicitly — not assumed.
2. **"Has security@ been notified?"** Confidence: high for any DoS /
   privilege / injection / overflow patch that lands on a public SQL
   API. Noah is the most likely reviewer to flag a public-disclosure
   issue. `pgsql-hackers` is the *wrong* forum for an
   embargo-warranted patch; he will say so.
3. **"What's the back-patch story?"** Confidence: very high. He
   back-patches correctness and security fixes aggressively (the
   inplace-update series went to every supported branch). If the
   commit body says "master only", expect "why?".
4. **"Did you check the multibyte / encoding interaction?"**
   Confidence: medium-high for any patch in `src/backend/utils/mb/`,
   `pgcrypto`, `pg_mblen*`, `varlena`/`text`, or `bytea`/`text`
   conversion code. He has the strongest reflex in the project for
   "this works for ASCII but does it work under GB18030?".
5. **"Show the failure-mode reproducer."** Confidence: medium-high.
   If you're claiming "this fixes a race" or "this fixes a leak",
   expect "reproduce it in `injection_points`". A patch that asserts
   a race without a fixture often gets pushed back to add one.
6. **"What about inplace update?"** Confidence: medium for patches
   touching `heap_update()`, `heap_inplace_*`, or the
   `RelationCacheInitializePhase*` paths. He has built up a complete
   mental model here; expect cross-cuts you didn't think about
   (HOT updates, locked-buffers invariant, the buffer-pin/xid-wait
   ordering).
7. **"Don't `--amend` upstream commits."** Confidence: high. Even his
   own cosmetic fixes go in as new commits with `Fixes: <sha>`
   pointers. Same discipline R-Anti-pattern in this meta repo.

## Reviewer partners (calibration input)

- **Andres Freund** — 42× pairing in 24mo. If a patch is in the
  storage/AIO area, the realistic review path is Andres-author /
  Noah-reviewer (or vice versa, less common). Both should be
  CC'd on the thread.
- **Nathan Bossart** (8×), **Heikki Linnakangas** (5×), **Sawada**
  (6×) — secondary pairings on storage/access fixes.
- For **pgcrypto** specifically (relevant to CB1 calibration): no
  Noah-with-Gustafsson direct pairing in 24mo, but he committed the
  recent pgcrypto encoding-validation patch independently. Treat
  him as a parallel reviewer to Daniel, not a pair.

## Landmark commits (last 12mo)

- `46b4f5c11b0` (2026-05-11) — **Fix SQL injection in logical
  replication origin checks.** Flagship security fix; sets the
  template for "this exact injection, this exact bound check, this
  exact test" Noah-style commit bodies.
- `9f4fd119b2c` (2026-02-14) — **Fix SUBSTRING() for toasted
  multibyte characters.** The encoding-validation reflex.
- `d536aee5566` (2026-02-09) — **Require PGP-decrypted text to pass
  encoding validation.** Directly relevant to CB1 calibration —
  paired commit `c5dc7547` is the test side.
- `aac2c9b` and the surrounding 5-commit inplace-update series
  (mostly 2025-Q1/Q2) — the durability landmark of the cycle. Bus-
  factor candidate (only-Noah-touches-it confirmed across 24mo).
- `627acc3caa7` (2025-05-05) — **With GB18030, prevent SIGSEGV from
  reading past end of allocation.** Cleanest single-commit example
  of the "multi-byte SIGSEGV class" reflex.

## Cross-references

- `knowledge/personas/committer-map.md` — row 16 (87 commits 24mo /
  20 12mo). Filed the original "Noah persona missing" follow-up
  from `cb1-pgcrypto-bomb.md` §6.1.
- `knowledge/personas/contributor-map.md` — top reviewer signal +
  the 42× Andres pairing.
- `knowledge/personas/domain-ownership.md` — cluster 1 (storage / AIO);
  he's the standing reviewer there.
- `knowledge/personas/andres-freund.md` — his most-paired author.
- `knowledge/calibration/cb1-pgcrypto-bomb.md` — first use of this
  persona for review prediction. The persona file resolves that
  doc's §6 follow-up #1.
