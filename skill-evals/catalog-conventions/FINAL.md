# catalog-conventions skill — final eval report

## Bottom line

The skill ships in good shape. Across two iterations, with_skill scored
**29/29** vs baseline **26/29** on a 3-eval, 29-assertion suite — a
net **+3 points / +10.3%** delta, concentrated entirely in workflow
specificity (eval-1). The iter-2 edits did not move the numeric score
(it was already saturated) but materially strengthened the qualitative
content for all three evals, ground the OID-policy claim in
`source/src/include/access/transam.h`, and make the SKILL.md
self-contained for syscache-lifecycle questions instead of redirecting
to `knowledge/idioms/catalog-conventions.md`.

Recommendation: freeze the skill at this revision.

## Score summary

| Eval | Topic | iter-1 with_skill | iter-1 baseline | iter-2 with_skill | iter-2 baseline |
|------|-------|-------------------|------------------|--------------------|------------------|
| 1 | Add a builtin function (full workflow) | 11/11 | 8/11 | 11/11 | 8/11 |
| 2 | Add a column to pg_class | 10/10 | 10/10 | 10/10 | 10/10 |
| 3 | SearchSysCache1 lifecycle + miss behavior | 8/8 | 8/8 | 8/8 | 8/8 |
| **Total** | | **29/29** | **26/29** | **29/29** | **26/29** |

Delta: **+3 pts (+10.3%)** at both iterations. The skill wins where
project-specific conventions diverge from common PG knowledge
(eval-1); it draws where common PG knowledge already covers the
ground (eval-2, eval-3).

## What iteration 2 changed

Four edits applied to `.claude/skills/catalog-conventions/SKILL.md`,
all from `iteration-1/proposed-edits.md`:

1. **OID-policy phrasing (§2)** — expanded "8000-9999 + renumber_oids.pl"
   to include *why* (project convention for in-progress patches,
   referenced against `transam.h:160-197`) and clarified that
   10000-11999 is genbki auto-assign. Replaced the proposal's
   unverified "0-7999 reserved for already-committed pins" claim with
   wording consistent with the actual transam.h comments.

2. **"Append at end of fixed-length section" bullet (§3)** — added the
   ABI-churn rationale so callers don't shift offsets of existing
   `Form_pg_X->field` references.

3. **Worked pg_proc.dat example (§4)** — replaced two terse bullets with
   a concrete row showing only the divergent columns, plus an explicit
   "Don't write: pronargs / provolatile / proisstrict / proparallel /
   prokind" list with the reason (`AddDefaultValues` + `BKI_DEFAULT`).

4. **"Using a syscache from C" mini-section (after §6)** — full
   lifecycle: `ReleaseSysCache` pairing, "cache reference leak"
   symptom, pointer-lifetime rule, `SearchSysCacheCopy1` +
   `heap_freetuple` escape hatch, miss-is-NULL semantics, `elog` vs
   `ereport(ERRCODE_UNDEFINED_*)` idioms, `SearchSysCacheExists1`,
   `GetSysCacheOid1`, and a note on automatic shared-invalidation
   coherence.

Each edit's specific factual claims were verified against `source/...`
before writing — see `iteration-2/edits-applied.md` for the
verification log.

## Why the score didn't move

The eval suite saturates:

- **with_skill** was already at 29/29 in iteration 1. There is no
  numeric headroom.
- **baseline** is held up by general PG knowledge: evals 2 and 3 are
  squarely in the wheelhouse of any developer who has read the
  catalog/syscache header comments, and no amount of skill editing
  can suppress that.

The qualitative improvements (groundedness, self-containment,
copy-pasteable examples) are real but invisible to a binary
assertion grader. They would show up under stricter graders that
penalise vague-but-not-wrong answers, or under harder evals like the
three suggested in `iteration-1/proposed-edits.md` §"Suggested
iteration-2 evals" (varlena placement rules on pg_aggregate; minimal
.dat row for a stable strict int8 sum; declaring a new
multi-key syscache on pg_constraint). Those weren't run because the
iter-2 brief asked for the existing eval set.

## Where the skill earns its keep

Concretely, the skill beats baseline on:

- **Specific OID convention (8000-9999)** — baseline hedged with
  "around the 6000-9000 band". Skill nails it and now explains why.
- **Don't-write-pronargs / BKI_DEFAULT-omit rule** — baseline actively
  suggested writing `provolatile => 'i'`, which is exactly the
  BKI_DEFAULT and shouldn't be written. Skill calls this out
  explicitly and shows the minimal row.
- **Group .dat entries near related ones** — baseline didn't mention.
  Skill says it.

Everything else is either parity (both correct, different wording) or
material the skill mentions and baseline would also reach from general
knowledge.

## Where the skill draws

- **Adding a column to pg_class** — `BKI_DEFAULT`, `CATALOG_VARLEN`,
  catversion bump, expected-out churn, recompile-extensions reality —
  all common PG knowledge. The skill's new "append at end of
  fixed-length section" bullet adds explicit rationale that baseline
  also arrives at, but doesn't change the score.
- **SearchSysCache lifecycle** — `ReleaseSysCache` pairing, "cache
  reference leak" warning, pointer-lifetime, `SearchSysCacheCopy1`,
  miss-is-NULL, `elog` vs `ereport` idioms — all standard knowledge.
  The skill's new mini-section makes SKILL.md self-contained but
  doesn't change the score.

## Artifacts

- `iteration-1/` — initial eval, grading, and proposed edits
- `iteration-2/edits-applied.md` — what was actually applied + verification log
- `iteration-2/evals.json` — eval prompts (copied from iter-1)
- `iteration-2/eval-{1,2,3}/{with_skill,baseline}.md` — re-answered evals
- `iteration-2/grading.json` — re-graded against iter-1's assertion list
- `.claude/skills/catalog-conventions/SKILL.md` — the updated skill

## Recommendation

Freeze. The score is saturated against this eval suite. If the suite
gets harder (the three suggested follow-up evals would do it) or the
grader gets stricter, iterate again — but on the current evidence the
skill is doing its job and additional editing risks bloat without
score movement.
