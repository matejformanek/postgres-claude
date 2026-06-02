# review-checklist — 2-iteration eval, FINAL

## Scoreboard

| Iteration  | with_skill | baseline | delta  |
|------------|------------|----------|--------|
| Iter 1     | 23/23      | 12/23    | +11    |
| Iter 2     | 26/26      | —        | (n/a)  |

Iter-2 added 3 new assertions (one per eval) that target the gap
identified in iter-1: explicit cross-references to specialist sibling
skills. All three new assertions pass; no iter-1 assertion regressed.

## Evals used (held constant across iterations)

1. **eval-1-guc-inline-func** — review a patch adding a new GUC plus
   an inline helper in `src/include/utils/`. Tests whether the skill
   surfaces (a) the seven-phase structure, (b) the cheap-checks-first
   triage, (c) ABI implications of headers in src/include/, and
   (d) concrete-ask discipline.
2. **eval-2-wal-xlog** — CommitFest patch touching WAL with a new
   XLOG record for a new index AM. Tests Phase 6 depth: RM
   registration, hint-bits, recovery testing, master-only catalog
   discipline.
3. **eval-3-perf-claim** — pre-submission self-review of a 30%
   hot-loop speedup claim on hash-join probes. Tests the pre-submission
   self-review specifics + Phase 4 perf-verification discipline.

## Edits applied (iter-1 → iter-2)

Applied to `/.claude/skills/review-checklist/SKILL.md`:

1. **Companion-skills section** (new) — orchestrates handoff to
   nine sibling skills (`wal-and-xlog`, `locking`, `error-handling`,
   `memory-contexts`, `coding-style`, `catalog-conventions`,
   `testing`, `commit-message-style`, `patch-submission`).
2. **Phase 4** — added "hot-loop micro-optimization → retest at
   larger N" footgun bullet.
3. **Phase 6** — Storage/WAL bullet now hands off to `wal-and-xlog`;
   added explicit `MarkBufferDirtyHint` vs `MarkBufferDirty` bullet.
4. **Phase 6** — extended back-branch ABI bullet so inline functions
   and macros in `src/include/` are explicitly covered.
5. **Posting the review** — added performance-table requirement
   (master tps / patched tps / runs / hardware / flags / recipe).

Three iter-1 proposals were rejected (already-present sanity-test
bullet; no phase restructuring; no inline expansion of message-style
guide — handed off to sibling skills instead).

## Headline findings

- The skill is doing its job as an **orchestration layer**: it wins
  most on the structured, mechanical phase (E1, +6 over baseline) and
  least on the topic where the underlying knowledge is already
  widely-known mechanics (E2 WAL, +3 over baseline). That asymmetry
  is correct — the skill's value is procedural, not encyclopedic.
- The largest pre-edit gap was **isolation**: the skill didn't point
  at any of the nine specialist sibling skills. After Edit 1, a
  reviewer hitting a WAL/lock/style topic gets a named handoff
  instead of either re-deriving rules or being silently incomplete.
- The smallest residual risk: a reviewer using only this skill (not
  the sibling skill) for a WAL patch will still be at the level of an
  experienced PG hacker but will miss the deeper invariants in
  `knowledge/architecture/wal.md`. Edit 3 mitigates this with an
  explicit handoff sentence; further mitigation would require either
  (a) duplicating wal-and-xlog content here (rejected — drifts) or
  (b) auto-loading wal-and-xlog from this skill (out of scope).

## Files

- `/Users/matej/Work/postgres/postgres-claude/.claude/skills/review-checklist/SKILL.md` — updated
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/review-checklist/iteration-1/{evals,grading}.json`, `proposed-edits.md`
- `/Users/matej/Work/postgres/postgres-claude/skill-evals/review-checklist/iteration-2/{evals,grading}.json`, `edits-applied.md`
