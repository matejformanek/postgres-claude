# Phase C — review-pipeline calibration

**Status:** kickoff 2026-06-12. CB1 (pgcrypto bomb) is the shake-down run.
**Owner doc:** `progress/STATE.md` "Phase" line.
**Feeds:** the `pg-patch-review` and `review-checklist` skills.

## What Phase C is

Phase A built the corpus (file-by-file knowledge of the source). Phase B
identified **who** owns each subsystem and **how each owner reviews**
(`knowledge/personas/`, `knowledge/personas/domain-ownership.md`). Phase C
joins the two: for every staged patch in `patches/<slug>/`, predict the
review feedback the actual PG committers and reviewers would give, then
diff that prediction against what the in-repo review pipeline
(`pg-patch-review` skill) produces unaided.

**The output of Phase C is twofold:**

1. **Per-patch calibration docs** under `knowledge/calibration/<slug>.md`
   — one per staged patch. Each names predicted reviewers, predicted
   feedback per reviewer, the generic review-pipeline output, and the
   **gaps** (what the personas catch that the generic pipeline misses).
2. **A consolidated gap catalog** at the end of the phase — feeds
   concrete improvements into the `pg-patch-review` and
   `review-checklist` skills so the next pass narrows the gap.

Phase C succeeds when the calibration loop has run for every staged
patch and the gap catalog has been digested into skill edits.

## Why this matters

Without calibration the review pipeline is generic — it catches style
nits, untested paths, missing trailers. Phase B showed that the actual
PG reviewers have **subsystem-specific reflexes** (Daniel Gustafsson
asks about OpenSSL/LibreSSL version conditionals on TLS patches; Tom
Lane probes API/ABI back-compatibility on header changes; Peter
Geoghegan asks for nbtree invariant proofs on access-method patches).
A generic pipeline doesn't know to apply these. The calibration loop
is how the skill grows those reflexes.

The Multigres lesson (`pg-claude-plan.md` Appendix A) is the negative
example: confident-sounding wrong claims about locking order made it
through because no reviewer with PG instincts was simulated. Phase C
is the explicit countermeasure.

## Inputs

For each `patches/<slug>/`:

- The patch itself (`0001-*.patch` + `COVER.md`).
- The subsystem it touches → look up in
  `knowledge/personas/domain-ownership.md` to get the top-4 committers
  and top-4 reviewers from the last 24 months.
- For each predicted reviewer, the corresponding
  `knowledge/personas/<name>.md` — specifically the "What to expect on
  a patch they would review" section.
- The relevant `knowledge/subsystems/<x>.md` doc — invariants the
  reviewer would expect the patch to honor.
- The relevant `knowledge/issues/<x>.md` register — the original
  problem report this patch resolves (so the diff against COVER.md is
  apparent).

## Methodology — per-patch calibration

For every patch, the calibration doc carries these six sections in
order. Anything novel that doesn't fit one of them gets a notes block
at the end.

### 1. Patch summary (one paragraph)

What the patch changes, scope, files touched, behavior delta. Pull
from COVER.md but compress to a paragraph.

### 2. Predicted reviewers

A table of 3-5 names with: name, why-they-would-review (from
`domain-ownership.md` — top-N committer or reviewer for this
subsystem, 24mo signal), and the cited persona file. Rank by
**likelihood of commenting**, not seniority. The first row is the
most-likely landing committer.

### 3. Predicted review feedback, per reviewer

For each predicted reviewer, a bulleted list of the comments they
would most likely raise on this specific patch, **derived directly
from their persona's "What to expect" section** applied to this
patch's shape. Cite the persona bullet that drives each prediction —
this is what makes the calibration auditable.

Phrase each prediction the way a reviewer would phrase it on
pgsql-hackers (terse, specific, citing a line). Do not editorialize.

### 4. Generic pipeline output

Run the `pg-patch-review` skill (or, mid-phase-C, summarize what it
*would* produce given the patch + corpus) and record the findings as
a flat list. This is the baseline.

### 5. Gap analysis

A side-by-side: which predicted-reviewer comments are covered by §4,
and which are missed entirely. For each miss, name **why** the
generic pipeline missed it — usually because the rule lives in a
persona and not in the skill. These are the candidate skill edits.

### 6. Recommended skill edits

A short list of edits to `pg-patch-review` or `review-checklist`
that would close the gaps surfaced in §5, each tagged with the
persona/bullet that motivates it. Edits are **proposed**, not made
inside the per-patch doc — they're collected here for the consolidated
gap-catalog pass at the end of Phase C.

## What Phase C does NOT do

- It does **not** send the staged patches to pgsql-hackers. Phase D
  remains parked. The calibration is a paper exercise; the real
  review only happens in Phase D.
- It does **not** modify the patches themselves. If the calibration
  surfaces a real bug in a patch, log it under `patches/<slug>/notes.md`
  for Phase D consumption — don't fix it inside the calibration doc.
- It does **not** modify personas mid-phase. If a calibration shows a
  persona is wrong, raise a `hf(corpus)` PR to fix the persona in a
  separate commit — don't smear that fix into a calibration doc.

## Calibration order

The 5 patches will be calibrated in roughly increasing subsystem
familiarity:

1. **CB1 pgcrypto-bomb** — pgcrypto, well-bounded owner set
   (Gustafsson + Lane + Paquier). Shake-down — this is the doc that
   the methodology is validated against.
2. **CB7 ltree-amplification** — contrib/ltree, owner set thinner.
3. **CB8 hstore-forge** — contrib/hstore, owner set thinner still.
4. **SP2 pgstr-maxalloc** — touches `src/backend/utils/mb` (encoding
   conversion), broader reviewer cohort.
5. **SP6 autoprewarm-revoke** — contrib/pg_prewarm, the only
   "privileges-and-install-scripts" patch in the set; will test the
   pipeline against the install-script reviewer reflex.

Each one stops for user review before the next. After all 5, the
consolidated gap catalog gets its own PR.

## Cross-references

- `progress/STATE.md` — Phase C status.
- `knowledge/personas/domain-ownership.md` — owner lookup table.
- `knowledge/personas/<name>.md` — per-reviewer style.
- `knowledge/subsystems/<x>.md` — invariants for the touched subsystem.
- `patches/<slug>/COVER.md` — patch summary baseline.
- `.claude/skills/pg-patch-review/SKILL.md` — the pipeline being
  calibrated.
- `.claude/skills/review-checklist/SKILL.md` — the static checklist
  that the gap-catalog feeds into.
