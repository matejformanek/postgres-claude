# 2026-06-13 — pre-compact handoff (Claude → post-compact-Claude)

**Read this file first after the compact.** It carries the state needed
to resume the day's arc without re-deriving it from the transcript.

## The mandate

The user said, verbatim: *"continue dont stop until i say so really
until i then stop u u will go"* (sic). And earlier: *"continue, don't
stop until I say so"*.

**Operative rule:** keep producing bounded, high-value deliverables in
sequence. Don't stop on your own initiative. Only stop when the user
explicitly says "stop" (or equivalent — "merge now", "wrap up", "ok
enough").

## What landed today — 13 open PRs

All on branches off main; all opened, none merged yet.

### Skill-creator core pass (PRs 1-5 of the original plan)

| # | URL | Branch | Headline |
|---|---|---|---|
| 1 | #167 | `ft_skills_workflow_tooling` | 9 skills polish: rubric items (when_to_load + companion_skills + Cross-references) on build-and-run, debugging, testing, psql, coding-style, commit-message-style, meta-commit-style, pg-claude, memory-keeping |
| 2 | #168 | `ft_skills_planner_suite` | 3 skills polish + M2/M3/M5 into `pg-feature-plan` (context-awareness pre-step, cite-verify final step, thread-engagement classification) |
| 3 | #169 | `ft_skills_patch_review` | 3 skills polish + M4 REJECT-A/B/C grades (review-checklist Phase 0 + pg-patch-review Stage 3 + Critic E) + `patch-submission` SHRINK 201→134 LOC |
| 4 | #170 | `ft_skills_domain_knowledge` | 14 skills net: SPLIT `gucs-bgworker-parallel` → 3 new (`gucs-config`, `bgworker-and-extensions`, `parallel-query`); EXPAND `locking` 131→276 LOC; EXPAND `parser-and-nodes` 89→212 LOC; rubric on 9 others. Includes a hotfix commit (`replication-logical.md` → `replication.md`) caught by self-audit |
| 5 | #171 | `ft_knowledge_contrib_docs` | 7 contrib subsystem docs: `contrib-pgcrypto`, `-ltree`, `-hstore`, `-pg_prewarm`, `-postgres_fdw`, `-pg_stat_statements`, `-btree_gist` (~127 LOC each) |

### Post-pass followups (PRs 6-13)

| # | URL | Branch | Headline |
|---|---|---|---|
| 6 | #182 | `ft_session_skill_creator_close` | Morning session log + cross-ref audit (29 skill refs, 11 cmd refs, 6 knowledge/files/ refs verified) |
| 7 | #183 | `ft_skill_creator_gate_followups` | Re-audit snapshot (`progress/backbone-reaudit-2026-06-13.md`) + `contrib-pg_walinspect.md` (audit's 8th tier-3) + `pg-start` / `pg-start-asan` merge (→ `--asan` flag, asan file deleted) + `refresh-upstream` `pg-anchor-refresh` note |
| 8 | #184 | `ft_phaseE_run2_scaffold` | Phase E run 2 spec.md (Filip Janus's "Adding compression of temporary files" thread). Plan + comparison deferred — gate on PR #168 merging so M2/M3/M5-enhanced `pg-feature-plan` loads |
| 9 | #185 | `ft_skill_pg_shadow_implement` | `pg-shadow-implement` skill + `/pg-shadow` command — closes audit gap #1 (the deferred new skill). Codifies the shadow-implementation methodology |
| 10 | #186 | `ft_corpus_datastructures_expansion` | 3 data-structures docs: `bitmapset.md`, `multixactid.md`, `xlogreaderstate.md`. Audit named 6 candidates; collapsed to 3 (MemoryContext / Snapshot / PROCARRAY-deep already covered) |
| 11 | #187 | `ft_corpus_idioms_expansion` | 3 idioms: `list-traversal-conventions.md`, `visibility-map-update.md`, `heap-tuple-decompression-pattern.md` |
| 12 | #188 | `ft_session_day2_close` | Day-2 afternoon session log |
| 13 | #189 | `ft_corpus_idioms_remainder` | Final 2 idioms: `fastpath-locks.md`, `sinvaladt-broadcast.md`. Audit's 5 idiom candidates all landed |

## Hard constraints — DO NOT VIOLATE

These were honored on every PR. Same rules apply post-compact.

### Anti-target paths (8 protected paths; diff must be empty)

- `knowledge/calibration/**` — session-of-record, frozen
- `knowledge/personas/**` — Phase B data correct; 6-month re-mine on schedule
- `knowledge/files/**` — per-file docs, `pg-quality-auditor` owns these
- `patches/**` — Phase D PARKED
- `progress/STATE.md` — cloud `pg-evening-merger` owns this
- `progress/cloud-routines/**` — routine logs
- Top-level `CLAUDE.md`
- `pg-claude-plan.md`

Pre-commit check on every PR: `git diff --stat origin/main..HEAD -- <those paths>` must be empty.

### Multigres-lesson rule

Every concrete file:line claim must resolve at the anchor commit
**e18b0cb7344** (the current corpus anchor — `pg-anchor-refresh`
cloud routine will bump this; check at the start of each session).
If you can't verify, tag `[unverified]` or `[inferred]` honestly.
Confident-but-wrong is the failure mode to avoid.

### Worktree-first workflow

One topic per worktree. Each PR cluster gets its own
`ft_<scope>_<short_desc>` worktree, branched from up-to-date main.
Rename `worktree-<name>` → `<name>` before pushing (drop the prefix).
Use the meta-commit-style format (`ft(scope):` prefix +
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
footer).

### Cross-ref-audit discipline

Before opening a PR, verify the new file:line and `knowledge/`,
`.claude/` refs resolve. The hotfix on PR 4 (`replication-logical.md`
→ `replication.md`) was caught by a 2-line union-of-added-refs script;
worth re-running before every PR opens.

## What's deferred (NOT done; pickup candidates post-compact)

Listed roughly by leverage. Pick whichever feels right; user wants
forward motion, not exhaustive coverage of any single area.

### Gated on merges (high value, must wait)

- **Phase E run 2 plan + comparison + skill-gaps** — `temp-file-compression`.
  Needs PRs #167-#170 to merge so `pg-feature-plan` actually loads
  the M2/M3/M5 enhancements before the planner step runs. Spec
  already in PR #184. Vondra's V1-V5 are the §13 risk items the
  plan must address.

### Substantial new work

- **Cross-corpus link verifier** — extend `pg-corpus-maintainer`
  with a mode that audits internal `[[link]]` / `knowledge/...` /
  `.claude/...` references, or a new dedicated routine. Audit
  recommended; would have caught the PR 4 hotfix automatically.
  ~300-500 LOC of recipe doc + cloud-routine plumbing.

- **`contributor-map.md` Phase B #5 refresh** — ~15 archive-mining
  names that fell below the display cutoff. `knowledge/personas/`
  is anti-target so this needs a non-persona-file approach (write
  to `knowledge/community/` or a new `progress/` doc).

- **Phase D send** — still PARKED. Requires explicit user
  re-authorization. Don't touch `patches/**` from any work stream.

### Smaller bounded options

- **More contrib subsystem docs** — `pg_buffercache`, `pg_visibility`,
  `pageinspect`, `amcheck` would all be valuable. None in audit but
  all referenced from the `psql` / `debugging` skills.

- **More idiom docs** — candidates not in the audit but useful:
  `xlog-region-replay`, `cache-invalidation-registration`,
  `predicate-locks`, `heaptuple-update-chain`.

- **More data-structure docs** — `Bitmapset` is in PR #186 but
  `BufferTag`, `PgStat_Counter` family, `TupleTableSlot` could
  follow.

## Reference state

- **Anchor commit:** `e18b0cb7344` (as of 2026-06-13)
- **Methodology docs:**
  - `progress/backbone-audit-2026-06-12.md` — original audit
  - `progress/backbone-reaudit-2026-06-13.md` (PR #183) — post-pass snapshot
  - `progress/skill-creator-brief.md` — the rubric
  - `knowledge/calibration/shadow-implementation-methodology.md` — Phase E recipe
- **Phase E runs:**
  - Run 1 — `knowledge/shadow-implementations/money-fx-exchange/` (REJECT-A; M1-M5 surfaced)
  - Run 2 — `knowledge/shadow-implementations/temp-file-compression/` (spec done, plan deferred)
- **Phase status:**
  - Phase A: complete
  - Phase B: maintenance cadence (next re-mine early 2027)
  - Phase C: frozen
  - Phase D: PARKED, no user re-auth
  - Phase E: run 1 done, run 2 spec done, run 3+ scheduled
- **Skill-creator scope verdict:** all major audit findings resolved
  (SPLIT, EXPAND ×2, SHRINK, rubric polish, M1-M5 integration, 7+1
  contrib docs, 3 data-structures, 5 idioms, new pg-shadow-implement
  skill + command, slash-command merges, refresh-upstream note).
  Phase E run 2's plan and the cross-corpus verifier are the largest
  unaddressed items.

## How to resume post-compact

1. **Read this file first.**
2. **Re-fetch git state** — `git fetch origin && git log --oneline -10`.
   Check which (if any) of the 13 PRs have merged overnight or
   intra-session. If anchor changed, re-verify against the new SHA
   before adding new cites.
3. **Check anti-target paths** are not in your worktree's pending
   changes. If they are, revert before doing anything else.
4. **Pick a deferred item** from the list above. Default: smallest
   bounded thing that's still high-value. Avoid Phase E run 2's plan
   step until PR #168 merges.
5. **Worktree-first.** New worktree per PR cluster; rename branch
   before push; PR title + body follow the established format.
6. **Cross-ref audit before opening.** Union-of-added-refs script:
   ```bash
   git diff origin/main..HEAD | grep -E '^\+' \
     | grep -oE '\.claude/skills/[a-z0-9-]+/SKILL\.md|knowledge/[a-zA-Z0-9/_-]+\.md' \
     | sort -u
   ```
   Verify each exists in main (or in PRs known to add it).
7. **Continue until user says stop.** Don't second-guess; produce.

## Tally going into the compact

- 13 open PRs
- ~5000+ LOC new corpus + skill docs over the day
- 27 → 32 skills net (PR 4 SPLIT +3, PR 9 +1, rubric polish on all)
- 10 → 15 idioms (PRs 11 + 13 add 5)
- 4 → 7 data-structures (PR 10 adds 3)
- 20 → 28 knowledge/subsystems (PR 5 adds 7, PR 7 adds 1)
- 2 session logs (morning + afternoon)
- 1 broken cross-ref hotfixed inline (PR 4 fixup commit)
- All anti-targets honored across all PRs

## One-line reminder

**Continue producing bounded high-value PRs against the deferred
list until the user explicitly says stop. Anti-target rule and
Multigres-lesson rule are non-negotiable. Cross-ref audit before
opening every PR.**
