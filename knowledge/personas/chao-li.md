---
name: Chao Li
email: li.evan.chao@gmail.com
role: Pure reviewer (no commits in 24mo); broad-coverage cross-subsystem
active_24mo: yes (reviewer footprint only; first R-by 2025-08-19)
first_review_year: 2025
landmark_24mo_areas: cross-cutting review — backend, replication docs, dynahash int64, optimizer touches, contrib/btree_gist tail
---

# Chao Li

## Activity profile (24 months ending 2026-06-12)

- **Zero `%an` commits in 24mo.** Pure-reviewer per `contributor-map.md`'s
  "Pure-reviewer cohort" — fits the same column as Robert Treat,
  Jelte Fennema-Nio, etc.
- **First `Reviewed-by:` trailer:** 2025-08-19 (on Peter Eisentraut's
  pgoutput docs improvement). **~10 months active** at audit time.
- **Reviewer-of counts (24mo, by committer of the patch):**
  Peter Eisentraut **58**, Fujii Masao **43**, Michael Paquier **39**,
  Melanie Plageman 23, Amit Kapila 21, Heikki Linnakangas 19,
  Nathan Bossart 17, Jacob Champion 15, Sawada 14, Jeff Davis 13.
  Spread across 10+ committers — not a single-committer attache.
- **Top *author* paired with** (`Author:` trailer on patches he
  reviewed): Melanie Plageman 22, Fujii Masao 19, Peter Smith 13,
  Tom Lane 12, Corey Huinker 9, Xuneng Zhou 7, Michael Paquier 7,
  David Rowley 7. Pattern: he reviews patches from both committers
  and non-committer authors, in roughly equal proportion to volume.
- **Path footprint** (touches under his R-by'd commits, 24mo):
  `src/backend` 677, `src/include` 265, `src/test` 206,
  `src/bin` 98, `doc/src` 94, `src/interfaces` 35,
  `contrib/btree_gist` 23, `contrib/postgres_fdw` 13.
  **Distribution suggests broad-coverage rather than subsystem-deep.**

## Domain ownership

- **No primary ownership.** Per `domain-ownership.md`, Chao Li is in
  the top-4 reviewers of **11 of 20** documented subsystems — by
  count, the most widely-spread reviewer in the corpus despite ~10
  months active. The pattern is *breadth-of-attendance*, not
  subsystem expertise.
- **Strongest single area** is the **docs / pgoutput / logical-rep
  docs** band — his earliest reviews (Aug 2025) clustered there and
  he kept reviewing in that area as it grew. Fits well with the
  Amit Kapila / Fujii Masao logical-rep cluster (per
  `domain-ownership.md` cluster 2).
- **Notable secondary areas:** dynahash / hsearch.h (the
  `dynahash.c long → int64` patch is one of his early reviews —
  `2025-08-22`), `contrib/btree_gist` and `contrib/postgres_fdw`
  (which is where the `ltree` / `hstore` / `intarray` contrib
  signals come from — relevant to the CB7/CB8 Phase C calibrations
  that flagged him).

## Style patterns (`Reviewed-by:` trailer only — no commit bodies)

Because Chao Li has no commits, his style must be inferred from the
patches he R-by'd and what survived into upstream master. Cautious
inferences (all `[inferred]`):

- **Wide net, light pass.** Reviewing 58 of Peter's commits + 43 of
  Fujii Masao's + 39 of Michael Paquier's in 10 months works out to
  ~14 reviews per month per committer. Either he attended threads
  briefly to give a +1, or he reviewed a series and the trailer
  was added to every commit in it. **Don't assume his R-by means a
  deep functional review** — it likely means "he read the thread and
  didn't object". Confirmation: he's never the lead reviewer, always
  one of 2-4 R-bys on the same commit.
- **Docs-first instinct.** His earliest reviews were on pgoutput docs
  and dynahash documentation. When a patch has both code and doc
  changes, his comment (if any) lands on the doc side.
- **No public mailing-list-archived review style yet.** Can't infer
  whether he probes invariants, asks for tests, or just signs off —
  the `Reviewed-by:` line doesn't encode that. **Phase B follow-up:
  if pgsql-hackers archive mining (#2) ever happens, his thread
  participation would clarify.**


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

- [`contrib-btree_gist`](../subsystems/contrib-btree_gist.md)
- [`contrib-postgres_fdw`](../subsystems/contrib-postgres_fdw.md)

<!-- /persona-subsystems:auto -->

## What to expect on a patch he would review

Honest answer: **he will probably add his `Reviewed-by:` trailer**
without changing the patch's outcome. Calibration value at this
stage:

1. **He is a `Reviewed-by:` trailer multiplier.** If your patch
   gets two or more good-faith reviewers, expect a Chao Li trailer
   to land on the merge commit. That's signal for "the patch was
   widely-seen", not for "the patch was deeply audited".
2. **Don't route patches to him as the lead.** He has no commit
   bit and no recorded thread-leading pattern. Lead reviewers are
   the area committers (per `domain-ownership.md` clusters); Chao Li
   is a follow-on signature.
3. **Watch for trajectory.** Per `contributor-map.md` overall:
   "Will likely overtake Tom Lane as #1 reviewer next cycle." If
   that's right, by 2027 he could have a thread-leading pattern.
   Re-write this persona when it materializes.
4. **No specific subsystem-of-strongest-instinct.** Unlike Heikki
   ("binary format"), Tom ("ABI"), Noah ("security@"), or Jeff
   ("Unicode"), Chao Li does not yet have a recognized
   subsystem-specific reflex. Treat predictions about *what* he'll
   ask as `[unverified]` until his commit-body or
   mailing-list-prose record fills in.

## Reviewer partners (calibration input)

- **Most-paired authors:** Melanie Plageman (22), Fujii Masao (19),
  Peter Smith (13). Pattern: he attends the most-active threads.
- **Most-paired committers:** Peter Eisentraut (58), Fujii Masao
  (43), Michael Paquier (39). Pattern: he attends threads where
  multiple committers can land.
- **No exclusive pairing.** Unlike Noah → Andres (42×, dominant)
  or Daniel → Jacob (TLS, dominant), Chao Li has no single
  committer he reviews more than 2.5× the next. His footprint is
  flat across 10 top committers.

## Landmark commits (last 12mo)

N/A — no commits. The closest substitute is "patches he R-by'd that
went on to become landmarks":

- `dynahash.c long → int64` (2025-08-22) — among his earliest
  reviews; an important infra change.
- pgoutput docs improvements (2025-08-19) — first review timestamp;
  marks his start as a reviewer.

## Cross-references

- `knowledge/personas/contributor-map.md` — "Pure-reviewer cohort"
  + "top-4 reviewer in 11/20 subsystems" + "likely overtakes Tom
  Lane next cycle" claim.
- `knowledge/personas/domain-ownership.md` — appears in 11 subsystems'
  top-4 reviewer column.
- `knowledge/calibration/cb7-ltree-amplification.md` §2 — first
  Phase C use; flagged as missing persona.
- `knowledge/calibration/cb8-hstore-forge.md` §2 — second Phase C
  use; flagged again.
- `knowledge/calibration/sp2-pgstr-maxalloc.md` (next) — will use
  this persona.

## Maintenance note

This persona is intentionally short — there isn't enough commit-body
or thread-prose record to write a long one. **Re-mine in 6 months**
(2026-12): if his thread-leading pattern materializes, expand the
"What to expect" section beyond the trailer-multiplier observation.
