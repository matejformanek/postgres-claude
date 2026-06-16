---
name: pg-feature-plan
description: Drop a heavy, citation-rich implementation plan for a scoped PostgreSQL backend feature — Phase 2 of the two-phase PG planner, the bridge from a brainstorm-with-picked-approach to /pg-implement. Names every src/backend or src/include file that must change with file:line cites at a pinned anchor, enumerates catalog / CATALOG_VERSION_NO / WAL / on-disk / lock-order / extension-ABI risks, proposes the test surface (regress / iso / TAP), structures the patch into independently-reviewable phases, picks a CommitFest landing strategy, and emits the plan-mode plan that /pg-implement executes phase-by-phase with plan-linked commits. **Use proactively whenever the user invokes /pg-plan, says "plan this PG feature", "make a plan for X in PG", "drop a heavy plan", "plan-mode plan for [PG feature]", "i picked option [A/B/C] in the brainstorm, now plan it", "we settled on the [approach] for the [PG topic], write me the phase plan with file:line cites", "spec-to-plan this pgsql-hackers thread", "shadow-implementation plan against [hackers URL]", "REJECT-track plan for CF NNNN", or has a brainstorm doc + a picked approach for a PostgreSQL backend change and wants the file-by-file rollout — even when they don't use the literal word "plan".** Skip when the idea is still exploratory and no approach is picked (use pg-feature-brainstorm first), for product / sprint / Q4 / roadmap / Jira / OKR planning, application architecture planning, Terraform / k8s / Helm / Ansible / CI infrastructure plans, React / Redux / Zustand / Vue / Angular frontend refactor plans, migration plans between non-PG databases (MySQL→PG migration is a DBA migration plan, not a PG feature plan), generic non-PG database feature planning (SQLite, DuckDB, MongoDB, MySQL features), and code-review of an already-submitted patch (use pg-patch-review or review-checklist).
when_to_load: Pick an approach is picked, drop a heavy plan with file:line cites; shadow-implementation runs; spec-to-plan from a pgsql-hackers thread; REJECT-track plans where the proposal should be declined.
companion_skills:
  - pg-feature-brainstorm
  - pg-implement
  - pg-claude
  - pg-patch-review
  - review-checklist
  - patch-submission
  - commit-message-style
companion_scenarios:
  - add-new-builtin-function
  - add-new-data-type
  - add-new-operator-class
  - add-new-operator
  - add-new-cast
  - add-new-aggregate-function
  - add-new-error-code
  - add-new-system-catalog-column
  - add-new-system-view
  - add-new-sql-keyword
  - add-new-node-type
  - add-new-utility-statement
  - add-new-plan-node
  - add-new-expression-eval-step
  - add-new-cost-model-knob
  - add-new-index-am
  - add-new-table-am
  - add-new-wal-record
  - add-new-buffer-strategy
  - add-new-guc
  - add-startup-hook
  - add-new-bgworker
  - add-new-hook
  - add-new-lwlock-tranche
  - add-new-shared-memory-region
  - add-new-pg-stat-view
  - add-new-protocol-message
  - add-new-replication-message
  - add-new-extension
  - add-new-test-module
  - bump-catversion
---

# pg-feature-plan — Phase 2 of the PG planner

The heavy stage. Phase 1 (`pg-feature-brainstorm`) narrowed the
design space; Phase 2 makes it implementable. Output is a plan-mode
plan with file:line cites that `/pg-implement` (NOT the generic
`/implement`) executes phase-by-phase with plan-linked commits.

## Inputs

- **Slug** (required): the planning directory under `planning/<slug>/`.
  If `brainstorm.md` exists, read it first — the picked approach + the
  DECISION: answers are your constraints.
- **No brainstorm?** Fine — accept a direct natural-language description
  of the picked approach + any constraints the user has already locked
  down. But note in the plan's intro that Phase 1 was skipped (and
  therefore some design-space exploration may be missing).
- **Thread spec?** A `planning/<slug>/spec.md` extracted from a
  pgsql-hackers thread (shadow-implementation runs). Run the spec
  through the engagement-classification step below before treating
  any of its content as locked.

## Context awareness — mandatory pre-step (M2)

**Before drafting any plan content**, run a context probe. Surfaced
by the money-fx-exchange shadow run (April-1 2026 joke proposal that
the planner initially treated earnestly).

1. **Posting date.** Check the thread's first-message date:
   - April 1 → flag for joke-check (look for `[PoC]` / `[RFC]`
     wording, absence of patch attachment, deadpan replies).
   - Within 2 weeks of a release-branch cut → flag for late-cycle
     context; the realistic CF target is the *next* window, not
     this one.
   - During an open CommitFest's commit window → check if the
     author intends this CF or the next.
2. **Author history.** One-shot poster vs sustained contributor.
   `git -C source log --author=<email> --oneline` and a quick
   pgsql-hackers archive search. A one-shot speculative post
   warrants different planning energy than a sustained
   contributor's serious proposal.
3. **Thread engagement signal** (see M5 below for the taxonomy).
   Reply count alone is misleading; classify what kind of
   engagement the replies represent.

Output a `## Context` block at the top of the plan that names date,
author posture, and engagement class. If the probe surfaces signal
that the proposal isn't serious (deadpan-only replies, joke
indicators, demonstrably unimplementable), the plan's recommended
verdict shifts to **REJECT** with cited reasons rather than a phased
implementation. See `.claude/skills/review-checklist/SKILL.md` Phase 0
for the REJECT-A/B/C grade rubric.

## Thread-engagement classification (M5)

When the input includes a thread (typical for shadow-implementation
runs), classify the engagement explicitly — not just the reply count.
Surfaced by the money-fx-exchange shadow run, where the deadpan
"thanks, add to commitfest" reply was the only public signal.

| Class | Signature | Plan implication |
|---|---|---|
| `unengaged` | No technical replies; deadpan acks; silence | Treat the spec as the *author's* unreviewed take. Don't pretend community endorsement exists. |
| `acked` | Technical replies with no objections | Spec is community-validated; proceed at normal confidence. |
| `debated` | Multiple substantive replies with disagreements + counter-proposals | Plan should enumerate the open questions as §13 risks, not paper over them. |
| `contested` | Named senior contributors raising correctness / design objections | Plan should NOT proceed to implementation phases until the objections are addressed. Output may be a REJECT or a brainstorm-revival pointer. |

Record the classification in the plan's `## Context` block.

## Output

A single file at `planning/<slug>/plan.md` following the structure
below. Length scales with the feature: ~400 lines for a small change,
~1500 lines for a medium feature, more for a major patch series.

### Required sections (in this order)

1. **What this plan is** (1 paragraph). State the picked approach (link
   to the brainstorm if it exists). Name the chosen scope (MVP vs
   full). State the target PG version + CF window.

2. **Scope contract** (3-5 bullets). Hard boundaries: what this plan
   COVERS, and what's explicitly OUT of scope. The plan-mode rule is
   strict: anything not in scope here is a follow-up.

3. **Files that change** (a table). Each row:
   - File path (under `source/...` or `dev/...` for new files).
   - Change type: `new` / `modify` / `delete`.
   - Approximate size: `tiny (<10 lines)` / `small (10-50)` / `medium
     (50-200)` / `large (>200)`.
   - One-sentence summary of what changes.
   - Per-file doc citation: `[via knowledge/files/.../X.md]` if one
     exists.

   Aim for completeness here. Missing a file in this table is a Phase 2
   bug. If you don't know all the sites, do another grep pass.

4. **Catalog + on-disk impact** (bulleted). Each item is yes/no with
   rationale:
   - New `pg_proc.dat` / `pg_operator.dat` / `pg_type.dat` / `pg_cast.dat`
     / `pg_opclass.dat` entries? Which file?
   - `catversion.h` bump required? (Bump if any catalog `*.dat` or
     `*.h` change.)
   - New on-disk format? (Page format, WAL record, file layout.) If
     yes, name the upgrade path.
   - `genbki.pl` re-run needed? (Implied if catalog files changed.)

5. **WAL impact** (bulleted). Each yes/no with detail:
   - New rmgr or new info byte for existing rmgr?
   - Existing record extended with new fields? (Compat policy.)
   - Replay function changes? (`*_redo` impact.)
   - `pg_waldump` desc/identify updates needed? (Implied by any record
     change.)
   - Hot Standby conflict generation? (Cite
     `knowledge/subsystems/access-nbtree.md` or
     `knowledge/subsystems/replication.md` for the pattern if applicable.)

6. **Locking + concurrency** (bulleted). Each item is "we need / we
   don't need" with cite:
   - New LWLock? (Add to `lwlocknames.h`?)
   - New heavyweight lock mode?
   - Buffer lock ordering implications? (Cite the relevant subsystem
     doc's lock-order section.)
   - Atomic-vs-spinlock decisions for shmem fields?
   - SSI predicate-lock implications?

7. **Memory + resource management** (bulleted):
   - New `MemoryContext`? Where in the hierarchy?
   - Per-query or per-tuple allocations?
   - Long-lived state (TopMemoryContext, CacheMemoryContext)?
   - `palloc_aligned` / DSA / shmem-resident state?

8. **Phased implementation** (the meat). Break into 3-6 phases. Each
   phase:
   - Phase number + title.
   - Files this phase touches (subset of §3).
   - The 5-10 concrete edits this phase makes (each with file:line where
     possible).
   - **Phase-end check**: how `/implement` knows this phase is done
     (e.g. "regress passes; new test in `src/test/regress/sql/foo.sql`
     exists and passes").

   A phase is self-contained enough that you could stop after it and
   the tree still builds. (This is the `/implement` skill's
   requirement.)

9. **Test surface** (bulleted with file paths):
   - **Regress** (`src/test/regress/sql/`): new `.sql`/`.out` pair? Or
     extend existing? Name the file.
   - **Isolation** (`src/test/isolation/specs/`): concurrency races
     this feature could cause? Name the spec file(s).
   - **TAP** (`src/test/recovery/t/` or similar): multi-node /
     subscriber / replication? Name file(s).
   - **`src/test/modules/`**: in-tree C test module needed?
   - **amcheck / `pg_amcheck`**: if AM-related.
   - **pgbench**: if performance-relevant.

10. **Docs** (bulleted):
    - SGML page(s) to add/update under `doc/src/sgml/`?
    - `release-N.sgml` entry needed?
    - GUC documentation (if a new GUC)?
    - System-catalog doc table update (if catalog changes)?

11. **Patch-series structure** (1 paragraph + bullets). Single patch
    or split? If split, name each patch and what depends on what.
    Default to single patch for ≤500 lines + one logical change; split
    for refactor-then-feature or multi-subsystem changes.

12. **CommitFest landing strategy** (bulleted):
    - Which CF? (e.g. "PG20-1, open now until 2026-06-30").
    - Pre-existing thread to revive, or new thread?
    - Likely reviewers? (Authors of nearby subsystems.)
    - Pre-mail self-review checklist: `review-checklist` skill.
    - First-patch-cover-letter structure.
    - Upstream commit-message style: `commit-message-style` skill
      (NOT `meta-commit-style` — those are for the meta repo only).

13. **Known risks + unknowns** (numbered list with severity tags).
    Each item:
    - **Severity:** blocker / high / medium / low.
    - **What:** the specific risk or open question.
    - **Mitigation / next step:** what we'd do to resolve.

14. **Phase-zero validation** (bulleted, optional but recommended).
    Quick checks the user can run BEFORE phase 1 of implementation to
    confirm the plan's assumptions still hold:
    - "verify file foo.c:NN still has function bar() at the cited line"
    - "grep for any since-introduced uses of struct X that the plan
      didn't account for"

### Forbidden in Phase 2

- "We'll figure it out during implementation" for anything in §3-§10.
  Either decide it here or move it to §13 as an open question.
- Citations without `file:line` from `source/`. Vague references like
  "the executor" are Phase 1 talk.
- Skipping §13 (Known risks). Every non-trivial plan has unknowns.

## Method

### Step 0 — Match the brainstorm against `knowledge/scenarios/` (hard integration)

**This is the FIRST thing the planner does, before any corpus loading.**

The scenarios layer (`knowledge/scenarios/`) is task-shaped: one
playbook per recurring change-class, each with an authoritative file
checklist. When the brainstorm's picked approach matches a scenario,
that scenario's checklist is **load-bearing** — it becomes the
starting authoritative §3 table.

Process:

1. **Read `knowledge/scenarios/_index.md`** — the decision tree + the
   31-scenario inventory.
2. **Match the brainstorm's change-class** against the index:
   - **Exactly one scenario matches** → its file checklist is the
     **starting authoritative §3 table**. Every file named in the
     checklist MUST land in the plan. The planner can ADD sites
     discovered by grep but can NEVER drop sites the scenario named.
     Dropping a site requires explicit user approval AND a follow-up
     edit to the scenario itself.
   - **Multiple scenarios match (composite feature)** → union their
     checklists. The §3 table is the deduplicated union; verify each
     row still applies, but do not drop entries from the union.
   - **Zero scenarios match** → ESCALATE to the user with a flag:
     "The scenarios layer has a gap for this change-class." Record
     the gap in `progress/scenarios-coverage.md` under "Gaps
     surfaced by planner runs". Continue with grep-based discovery
     only.
3. **Check anchor drift.** Read the scenario's `last_verified_commit:`
   frontmatter. If the plan's anchor SHA ≠ `last_verified_commit`,
   emit a **"scenario stale" warning** in the plan's §1 and run a
   fresh grep pass to validate every checklist row before treating
   the table as authoritative.
4. **Record which scenario(s) the plan pins to** in the plan's
   `## Context` block (after the date / author posture / engagement
   class). Format: `Scenario(s): add-new-data-type, add-new-operator-class`.

Step 0 is the hard contract — it's what makes the scenarios layer
load-bearing rather than advisory.

### Subsequent steps

1. **Read brainstorm + DECISION answers.** If they're missing or stale,
   re-run brainstorm or ask the user inline before proceeding.

2. **Load corpus deeply.** Read the 1-3 subsystem docs from the
   brainstorm. Then walk per-file docs (`knowledge/files/src/...`) for
   the directories you'll touch. Open the actual `source/` files for
   anything not in the per-file corpus. Also load every per-file doc
   linked from the pinned scenario's checklist.

3. **Inventory the change sites.** Run targeted greps over `source/`
   for the symbols, structs, and call sites the plan will touch. Build
   the §3 table from this. Don't skip files you "think" don't need
   changes — verify.

4. **Decide catalog + WAL + lock + memory** (§4-§7) BEFORE writing
   §8 phases. The phases depend on these decisions.

5. **Phase the work.** Each phase should be 1-3 sittings of editing
   for a human. Group related edits; don't intersperse unrelated
   sites.

6. **Write tests in the plan, not in the code.** Phase-end checks (§8)
   should reference specific test files in §9.

7. **Risk surface (§13) is mandatory.** If you genuinely can't think
   of any, you haven't probed deeply enough.

8. **Verify every file:line cite — required final step (M3).**
   Surfaced by the money-fx-exchange shadow run (`cash_out` initially
   cited as `provolatile='i'`; actual is `'s'` per
   `source/src/include/catalog/pg_proc.dat:1954`).

   For each cite that appears in the produced plan:
   - Resolve the file at the anchor commit (today: `e18b0cb7344`;
     update when `pg-anchor-refresh` lands the next bump).
   - Confirm the symbol / line / value matches what the plan claims.
   - For `.dat` / config cites: spot-check the actual cell value
     (`provolatile`, `proisstrict`, GUC default, etc.), not just the
     file:line.
   - Reuse `pg-quality-auditor`'s file:line discipline (already
     established for merged docs).

   If any cite fails resolution: fix the plan inline. **Do not hand
   off a plan with stale cites.**

8a. **Scenario-coverage gate — required (M3 extension).** For every
    scenario pinned in Step 0, cross-check that **every file in the
    scenario's checklist appears in the plan's §3 table**. Missing
    files invalidate the plan:
   - If a file from the checklist is genuinely not needed for this
     specific feature, the user must explicitly approve dropping it
     AND the scenario itself must be edited (don't paper over the
     drop). Until the scenario is edited, the file stays in §3 even
     if the plan's §8 phases skip it; the deviation is recorded in
     §13 risks.
   - If anchor-drift was flagged at Step 0 and the checklist appears
     stale, run a fresh grep pass to validate each row; update the
     scenario's `last_verified_commit:` if you do the verification.

    The gate is binary: a plan with scenario-coverage gaps fails
    validation. Don't ship a plan that quietly drops scenario sites.

9. **End with a one-line hand-off:** *"Run `/pg-implement <slug>` to
   start phase 1."* (Use `/pg-implement`, NOT the generic
   `/implement` — the PG version enforces plan-linked commits, per-phase
   tests, and the file:line citation rules in
   `.claude/rules/pg-implement-discipline.md`.)

   For a REJECT-track plan (context awareness or thread engagement
   surfaced design-level problems), the hand-off is instead: *"Plan
   recommends REJECT — see Verdict block. Write a thread reply per
   `.claude/skills/review-checklist/SKILL.md` Phase 0."*

## Boundaries vs other skills

- **`pg-feature-brainstorm`** (Phase 1): the upstream. Re-run if scope
  shifts mid-plan.
- **`/pg-implement`** (Phase 3 — the PG-specific implementer, NOT the
  generic `/implement`): takes this plan and walks the phases
  interactively with the user. Auto-discovers `planning/<slug>/plan.md`
  and enforces the rules in `.claude/rules/pg-implement-discipline.md`
  (plan-linked commits per phase, file:line citations, etc.).
- **`patch-submission`**: takes over once code is done; this skill stops
  at the plan.
- **`review-checklist`**: pre-mail check; references in §12 but doesn't
  run here.
- **`memory-keeping`**: session log of the planning effort goes through
  this skill at end.

## Style

- Cite or don't claim. Every file:line in the plan must be verifiable
  with grep against current source at the anchor commit. Tag claims
  not from `source/` with `[from knowledge/...]` or `[unverified]`.
- Be specific. "We'll need to update the planner" → which `planner.c`
  function, at which line, doing what.
- Be honest about scope. If a phase is going to be a full week of
  work, say so. Don't pretend a refactor is small.
- Plans rot. Stamp the plan with the source commit it was written
  against (in §1). When the gap from current master grows, re-validate.

## Where the artifact lives

`planning/<slug>/plan.md`, next to `brainstorm.md` from Phase 1. Both
under `planning/<slug>/`. Also acceptable:
`planning/<slug>/notes.md` — running notes from `/implement`,
appended-to per phase.

When the feature lands upstream, link the plan from the commit message
("see planning/<slug>/plan.md in pg-claude meta repo for design
notes") and consider archiving the brainstorm if it's no longer useful.

## Cross-references

- `.claude/skills/pg-feature-brainstorm/SKILL.md` — Phase 1 upstream; consumes the brainstorm + DECISION: answers.
- `.claude/skills/pg-implement/SKILL.md` — Phase 3 consumer; executes the plan phase-by-phase with the discipline rules.
- `.claude/skills/pg-patch-review/SKILL.md` — Critic E supplies the REJECT-A/B/C grade rubric this skill references.
- `.claude/skills/review-checklist/SKILL.md` — Phase 0 REJECT-track is the destination when context-awareness or engagement classification recommends REJECT.
- `.claude/skills/patch-submission/SKILL.md` — used after `/pg-implement` lands the code, not here.
- `.claude/skills/commit-message-style/SKILL.md` — referenced from §12 (CF landing strategy); upstream-PG style, not meta.
- `.claude/skills/meta-commit-style/SKILL.md` — the plan.md file itself commits to the meta repo via this style.
- `.claude/skills/memory-keeping/SKILL.md` — session log of the planning effort goes through this skill at end.
- `.claude/skills/pg-claude/SKILL.md` — master nav for picking subsystem docs.
- `knowledge/scenarios/README.md` + `knowledge/scenarios/_index.md` — the scenarios layer Step 0 pins against.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md` — M2/M3/M5 origin (Phase E run 1).
- `knowledge/calibration/shadow-implementation-methodology.md` — methodology this skill participates in.
- `.claude/commands/pg-plan.md` — slash-command wrapper.
