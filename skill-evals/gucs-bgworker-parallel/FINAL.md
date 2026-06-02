# `gucs-bgworker-parallel` — final eval summary

Two iterations, same three realistic prompts in `evals.json`. The skill
walked into iter-1 already complete on the with-skill side; iter-2
confirmed that the small polish edits applied between rounds didn't
regress anything.

## Scores

| Iteration | with-skill | baseline |
|---|---|---|
| 1 | 22 / 22 (100%) | 13 / 22 (59%) |
| 2 | 22 / 22 (100%) | 11 / 22 (50%) |

## Iter-1 → iter-2 deltas

**with-skill**: no change. All 22 assertions still pass. The applied
edits (§2.5 restart-policy table; §2.1 dynamic-vs-static prose
clarifier) sharpened presentation without altering correctness, and
no assertion depended on the not-applied polish items (#3 `shmem_request_hook`
cross-link, #4 boxed estimate-allocate warning, #5 cite tightening).

**baseline**: −2 (13 → 11). The natural noise floor of cold-call
answers — two assertions that happened to land in iter-1 missed in
iter-2:

- eval-3 / "workers see leader's GUCs via PARALLEL_KEY_GUC and later
  SETs don't propagate" — iter-2 baseline mentioned GUC propagation
  but not the "later SETs don't reach in-flight workers" half.
- eval-3 / "`pcxt->nworkers_launched` may be less than requested" —
  iter-2 baseline omitted the bound check entirely.

The skill catches both reliably; baseline only catches them when the
unaided answer happens to wander into the right caveat.

## Lift

22 vs 11 (iter-2): the skill nearly doubles assertion coverage. The
nine assertions the skill consistently lifts are the high-signal
ones — APIs the baseline gets wrong by name (`RegisterDynamicBackgroundWorker`
vs static, `MarkGUCPrefixReserved` vs `EmitWarningsOnPlaceholders`),
exact-value claims (TOC magic-number range, `proc_exit(0)`
short-circuiting restart, `pcxt->nworkers_launched` < requested), and
specific `file:line` cites that anchor every claim.

## Verdict

Ship. The skill is doing its job — both runs hit ceiling on
with-skill, and the baseline gap is consistently in the territory
the skill was designed to cover (operational gotchas, exact API
names, file:line citations). No edits required for a third
iteration; the proposed polish items in iter-1 §3-5 are nice-to-have
but moved zero assertions across two runs.

## Artifacts

- `iteration-1/`: evals.json, grading.json, proposed-edits.md, eval-{1,2,3}/{with_skill,baseline}/answer.md
- `iteration-2/`: evals.json, grading.json, edits-applied.md, eval-{1,2,3}/{with_skill,baseline}/answer.md
- `.claude/skills/gucs-bgworker-parallel/SKILL.md`: 475 lines, last verified against `source/` 2026-06-02
