# 2026-06-13 — Skill-creator backbone pass: 5 PRs open

## What I did

Executed the 2026-06-12-finalized plan (skill-creator pass over all
backbone skills) in 5 PRs across one session. All open at:

- PR 1 #167 — `ft_skills_workflow_tooling` — 9 skills polish (rubric)
- PR 2 #168 — `ft_skills_planner_suite` — 3 skills polish + M2/M3/M5
- PR 3 #169 — `ft_skills_patch_review` — 3 skills polish + M4 +
  `patch-submission` SHRINK 201→134 LOC
- PR 4 #170 — `ft_skills_domain_knowledge` — SPLIT
  `gucs-bgworker-parallel`→3, EXPAND `locking` 131→276 / `parser-and-nodes`
  89→212, 9 skills polish
- PR 5 #171 — `ft_knowledge_contrib_docs` — 7 contrib subsystem
  docs (`pgcrypto`, `ltree`, `hstore`, `pg_prewarm`, `postgres_fdw`,
  `pg_stat_statements`, `btree_gist`), 892 LOC total

Rubric items applied to every skill: `when_to_load:` +
`companion_skills:` frontmatter; formal `## Cross-references` section
at bottom (normalized from existing inline references in 5 skills,
freshly added in the rest).

## What I learned

- **Scoping the brief's "Heavy mode" matters.** The plan asked for
  the literal skill-creator subagent eval loop on every skill.
  Pragmatic call: skip the eval loop on the 9 LEAVE-alone skills in
  PR 1 — non-regression on no-structural-change is no signal at all
  — and reserve the eval machinery for the SHRINK/SPLIT/EXPAND
  skills in PRs 3 and 4. Flagged the choice to the user; not
  redirected. Saved ~600K output tokens that would have produced
  noise.
- **Worktree-tool path footgun.** The Edit tool ignored the worktree
  CWD twice early in PR 1 — landed edits in the main checkout instead.
  Recovery: copy modified files into worktree paths, revert main, re-do.
  After that, used explicit worktree-rooted absolute paths for every
  Edit call. The shell wrapping that resets cwd between Bash calls is
  the proximate cause — Edit's CWD isn't tied to the worktree.
- **Cross-ref sweep scope is narrow on purpose.** The plan
  explicitly limited the `gucs-bgworker-parallel` retarget sweep to
  `.claude/skills/`, `knowledge/idioms/`, `.claude/cloud/`, and
  `MEMORY.md`. Left `knowledge/files/**`, `knowledge/community/**`,
  `knowledge/docs-distilled/**`, `knowledge/conventions/**` alone
  even where they had pointer references. Right call — the
  out-of-scope refs are either anti-target (`files/`), low-traffic
  (`ideologies/`), or auto-regenerated (`community/`).
- **The Multigres-lesson rule held.** PR 5's 7 contrib docs each
  cite struct lines I genuinely read at the anchor (`ltree.h:32-36`,
  `hstore.h:17-33`, etc.). Things I didn't verify (LOC counts of
  `pg_stat_statements.c`'s function table; recent committer name
  for `btree_gist`) tagged `[unverified]` or kept vague enough to
  not be a confidently-wrong claim. The personas-driver claims for
  some docs are weaker than the structural claims and that's
  honestly reflected.

## What I'm unsure about

- Whether the SPLIT of `gucs-bgworker-parallel` will pay off in
  practice. The three siblings (`gucs-config`,
  `bgworker-and-extensions`, `parallel-query`) loaded together
  consume slightly more tokens than the original on a task that
  touches all three; the bet is that most tasks touch only one,
  and the cleaner companion-skills graph + the new content in
  `bgworker-and-extensions` (hooks-chain pattern) +
  `parallel-query` (execParallel.c plumbing) earn it back.
- Whether PR 5's contrib-docs persona claims should be moved to
  `knowledge/personas/<name>.md` updates instead of being inline
  in each doc. Probably yes; deferred to a future Phase B refresh.
- PR 1 and PR 4 both edit `pg-claude/SKILL.md` — PR 1 added
  flagged stubs, PR 4 replaced them with unflagged rows + dropped
  the deprecated row. Conflict resolution at merge time is
  mechanical but it's a manual merge moment.

## Pointers left for next time

1. **Phase E run 2 (Filip Janus's temp-file compression)** is
   unblocked once PRs 2 and 3 merge (M2/M3/M4/M5 land). Run it
   against the methodology fixes to confirm they help. See
   `knowledge/calibration/shadow-implementation-methodology.md`
   and `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`
   for the prior calibration.
2. **Re-run the backbone-audit methodology** (in
   `progress/backbone-audit-2026-06-12.md`) after the 5 PRs merge.
   If any audit verdict still applies, open a follow-up.
3. **Phase D send is still PARKED.** Do not touch `patches/**` from
   any skill-related work stream.
4. **Per-doc persona refresh.** When the next Phase B
   persona-refresh runs (6mo cadence), pull the persona claims from
   the 7 contrib docs into the canonical persona files.
5. **The `pg-claude` master index manual merge.** When PR 4 merges
   after PR 1: the deprecated `gucs-bgworker-parallel` row PR 1
   left in needs dropping (PR 4 already drops it).

## Cross-ref self-audit (post-PRs-open)

After all 5 PRs opened, I ran a union-of-added-refs check across
all 5 branches. 29 unique skill cross-references (all resolve: 26
to existing skills, 3 to PR 4-new skills). 11 unique slash-command
references (all resolve). 6 unique `knowledge/files/*` references
(all resolve, important since `knowledge/files/` is an anti-target
— can't be fixed retroactively). 103 unique non-source-tree
markdown refs total.

One real broken link found and fixed via hotfix on PR 4:
`replication-overview/SKILL.md` cited
`knowledge/subsystems/replication-logical.md` but the corpus has a
single `replication.md` covering both physical and logical.
Collapsed to the existing doc. Hotfix commit landed on
`ft_skills_domain_knowledge` (PR #170), 1 line change.

## Anti-target rule held

Pre-commit diff check against the 8 protected paths
(`knowledge/calibration`, `knowledge/personas`, `knowledge/files`,
`patches`, `progress/STATE.md`, `progress/cloud-routines`,
top-level `CLAUDE.md`, `pg-claude-plan.md`) was empty on every PR.
Honored.

## Cross-references

- `progress/backbone-audit-2026-06-12.md` — the audit this pass
  resolved (most verdicts; some structural ones still need follow-up).
- `progress/skill-creator-brief.md` — the rubric this pass applied.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`
  — source of M1–M5 methodology findings; M2/M3/M5 landed via PR 2,
  M4 via PR 3, M1 still belongs in the methodology doc itself.
- `sessions/2026-06-12-phaseDE-storm-and-skill-creator-pivot.md` —
  the user's pivot from Phase D send to this backbone pass.
