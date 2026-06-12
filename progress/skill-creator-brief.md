# Skill-creator pass — briefing

Input doc for the claude.ai skill-creator plugin. Pairs with
`progress/backbone-audit-2026-06-12.md`.

## Goal

Take the 27 skills + 20 slash commands + 1 rules file + selected
knowledge expansions in `progress/backbone-audit-2026-06-12.md` and
produce the best-quality skill pile this project can support.

## Files in scope

### Tier 1 — skills (priority order from the audit)

**HIGH-value targets** (clear improvement available):

1. `.claude/skills/gucs-bgworker-parallel/SKILL.md` — **SPLIT** into 3:
   - `.claude/skills/gucs-config/SKILL.md`
   - `.claude/skills/bgworker-and-extensions/SKILL.md`
   - `.claude/skills/parallel-query/SKILL.md`
2. `.claude/skills/parser-and-nodes/SKILL.md` — **EXPAND** to ~200 LOC.
   Cover: AST → Query tree → Plan tree; mutator/walker conventions;
   the major node types reference; node-tag invariants.
3. `.claude/skills/locking/SKILL.md` — **EXPAND** to ~200 LOC.
   Add: multi-XID interaction; LWLock rank ordering; common
   deadlock patterns cheat-sheet; HW_PROFILE rules.
4. `.claude/skills/patch-submission/SKILL.md` — **SHRINK** to ~80 LOC.
   Make it a thin wrapper around `pg-patch-review --self` +
   `commit-message-style` finalize step. Delete the duplicated
   critic descriptions.

**MEDIUM-value targets** (polish without restructure):

- Any 200-500 LOC skill the plugin spots as bloated. Apply
  surgical edits only.
- Cross-reference completeness: most skills cite each other; the
  pass can add missing `[[link]]`s.

### Tier 2 — commands (lower priority but clean)

- `.claude/commands/pg-start.md` + `.claude/commands/pg-start-asan.md`
  → **MERGE** into one, `--asan` is a flag.
- Add `.claude/commands/pg-shadow.md` — wraps the new
  `pg-shadow-implement` skill (created in same PR via the
  shadow-implementation methodology doc).
- `.claude/commands/refresh-upstream.md` — add a one-line note that
  the daily anchor-bump path is now the `pg-anchor-refresh` cloud
  routine; this command stays as the manual escape hatch.

### Tier 3 — knowledge expansions (NEW docs the plugin should write)

If the plugin can produce these from existing corpus + skills:

1. **`knowledge/subsystems/contrib-pgcrypto.md`** — used by CB1
   calibration; needed for future shadow-implementations near
   crypto.
2. **`knowledge/subsystems/contrib-ltree.md`** — CB7.
3. **`knowledge/subsystems/contrib-hstore.md`** — CB8.
4. **`knowledge/subsystems/contrib-pg_prewarm.md`** — SP6.
5. **`knowledge/subsystems/contrib-postgres_fdw.md`** — Etsuro
   Fujita's primary area.
6. **`knowledge/subsystems/contrib-pg_stat_statements.md`** —
   high-traffic area; touched by many threads.
7. **`knowledge/subsystems/contrib-btree_gist.md`** — Tomas
   Vondra's recent commits.

Each should mirror the existing `knowledge/subsystems/<x>.md`
shape (front matter + Purpose + File map + Invariants + Owners
block + Local reviewer reflexes if any).

### Anti-targets — DO NOT modify

- `knowledge/calibration/**` — session-of-record, frozen.
- `knowledge/personas/**` — Phase B data is correct;
  6-month re-mine is on canonical schedule.
- `knowledge/files/**` — per-file docs; the
  `pg-quality-auditor` is the audit tool for these.
- `patches/**` — the 5 staged patches + their notes; PARKED
  pending Phase D resume.
- `progress/STATE.md` — multi-file edits collide with the cloud
  routines' state-log discipline.
- `progress/cloud-routines/**` — routine logs and digests.
- `pg-claude-plan.md`, top-level `CLAUDE.md` files —
  project-level docs the user maintains.

## "Best quality" — what good looks like

Per-skill checklist (the plugin should apply this to each):

1. **Single sentence opening** stating what the skill is for and
   when to load it.
2. **Companion skills** list — which other skills this calls into,
   which call into this.
3. **Methodology** in numbered steps (not prose paragraphs).
4. **Concrete file:line cites** into `source/...` whenever the
   skill references PG internals — not bare claims.
5. **Confidence tags** (`[verified-by-code]`, `[from-README]`,
   `[from-comment]`, `[inferred]`, `[unverified]`) wherever the
   skill makes a factual claim.
6. **One "common mistake" or "anti-pattern" block** if applicable.
7. **Cross-references** section at the bottom — relative paths to
   other skills, knowledge docs, and personas the skill touches.
8. **Frontmatter** with `name`, `description`, `when_to_load`,
   and `companion_skills` keys (consistent with existing skills).

Per-skill anti-checklist:

- No long quotes from `source/...` — link via `file:line` instead.
- No restating of PG documentation that's already in
  `knowledge/docs-distilled/`.
- No "future work" sections — those go in
  `progress/STATE.md` or follow-up PRs.
- No "TODO" tags — concrete actions only.

## Output expectations

The plugin's output PR (separate from this one) should:

- One commit per tier-1 skill change (so each is reviewable).
- One commit per new subsystem doc.
- Bulk commit for the cross-reference + frontmatter normalization
  pass.
- Commits should reference this brief in the body:
  `Skill-creator pass per progress/skill-creator-brief.md`.

## How this brief interacts with the shadow-implementation loop

After the skill-creator pass lands, the **first shadow-implementation
run** (per
`knowledge/calibration/shadow-implementation-methodology.md`) will
be the test of whether the improved skills produce better
implementations. If the shadow-implementation diff against the
upstream patch is significantly closer than the baseline (skills
before the pass), the skill-creator pass was net-positive. If not,
the gaps surface in the shadow-implementation calibration doc and
feed back into another pass.

This brief is meant to be **regeneratable** — when the next
skill-creator pass runs (in ~6 months or after a major Phase D
campaign), refresh this doc with the next round of targets.

## Cross-references

- `progress/backbone-audit-2026-06-12.md` — full audit data
- `knowledge/calibration/shadow-implementation-methodology.md` —
  the test that proves whether the pass worked
- All 27 skills in `.claude/skills/<name>/SKILL.md`
- All 20 commands in `.claude/commands/<name>.md`
