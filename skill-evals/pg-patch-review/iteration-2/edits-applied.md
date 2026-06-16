# Iteration 2 — edits applied

Applied edits from `iteration-1/proposed-edits.md` to
`.claude/skills/pg-patch-review/SKILL.md`.

## Per-edit disposition

### Edit #1 — Replace dead `sessions/2026-06-02-cf6402-review-validation.md` cite — **APPLIED (modified)**

**Verification:** `find /Users/matej/Work/postgres/postgres-claude/
sessions/ -name '*6402*' -o -name '*validation*'` returned zero
matches. Closest sibling sessions on 2026-06-02 are
`access-nbtree-synthesis.md`, `replication-synthesis.md`,
`phase-a-setup.md`, `a1-catalog-headers.md`, and
`cloud-throughput-bump.md`. None of them are a CF #6402 review log.

**Applied option (b)** from proposed-edits — replaced the bare
broken path with an `[unverified: session log not preserved in
sessions/ at the time of this writing]` marker per the cite-or-tag
rule. Preserved the calibration intent (rerun should reproduce a
comparable review) and added "A future preserved-and-named
calibration session can replace this paragraph." Did NOT delete the
§Validation reference section — option (a) — because the cf6402
calibration is part of the skill's history even if the file is
gone.

### Edit #2 — Replace `pg-corpus-maintainer` reference — **APPLIED**

**Verification:** `ls .claude/skills/ | grep -i corpus` returned
zero matches. No `pg-corpus-maintainer/` directory exists. The
escalation path was wired to a missing handler.

**Applied:** replaced the corpus-drift escalation bullet at SKILL.md
§"What to escalate to the user mid-review" with a two-option
workflow that uses the existing `hf(corpus):` commit convention
documented in Rule R9 of
`.claude/rules/pg-implement-discipline.md`. Verified R9 exists in
that rules file (it does — defines the citation chain and
explicitly names "the corpus needs a `hf(corpus)` fix in a SEPARATE
meta-repo commit").

### Edit #3 — Critic-E severity matrix table — **APPLIED**

**Verification:** re-read SKILL.md §Critic E lines ~273-380 to
confirm the per-probe defaults and escalation conditions before
producing the table. Cross-checked against
`knowledge/calibration/gap-catalog.md` to confirm the 11-item
numbering matches (items #4-#11 are Critic E's; #1-#3 are
review-checklist Phase 0).

**Applied:** added an 8-row markdown table immediately before the
**Output:** line at the end of §Critic E. The table is a
restatement of what the prose already says — no new claims. Also
added the explicit REJECT-track threshold line below the table
("3+ `blocking` rows AND a context-awareness signal").

### Edit #4 — Inline Stage 0 recipe for direct invocation — **APPLIED**

**Verification:** re-read SKILL.md §Stage 0 lines ~82-100. The
section already names the output of Stage 0 (branch + built binary
+ test results + touched-file list); the gap was the *commands*
when invoked without `/pg-review`.

**Applied:** inserted a 9-step recipe block between the existing
"See `.claude/commands/pg-review.md`" sentence and the "The output
of this stage is:" line. Steps follow the standard PG workflow:
`git checkout master && git pull` → branch → fetch → `git am` →
`ninja install` → `meson test regress/regress` → `meson test
--suite isolation` → `git diff --name-only` → flake note. Verified
the macOS flake reference (`recovery/040_standby_failover_slots_sync`)
matches what STATE.md and other sessions document as a pre-existing
flake — not made up.

### Edit #5 — Promote "Critic E recommends; Stage 3 decides" — **APPLIED**

**Verification:** the rule was buried in §Critic E "REJECT-track
escalation (M4)" paragraph (lines ~367-376). A reader scanning §Stage
3 would miss it.

**Applied:** prefixed §Stage 3 with a "Critic-E recommendation vs
orchestrator verdict" paragraph that names the rule explicitly:
Critic E *recommends*, Stage 3 *decides*; the orchestrator may
downgrade Critic E's `recommend_verdict: REJECT-A | REJECT-B` to
"Waiting on Author" if findings don't compose to a design-level
NACK. The original sentence in §Critic E is kept (consistency, not
redundancy).

### Edit #6 — REJECT-A/B/C decision tree — **NOT APPLIED**

Marked optional in proposed-edits.md. The Stage 3 §Verdict block
already lists the three grades with crisp definitions; adding an
ASCII flowchart would duplicate not clarify. Skipped to keep
SKILL.md tight. Could be revisited if a future calibration shows
the orchestrator agent picking the wrong grade.

### Edit #7 — Parallel-tool-call shape example — **NOT APPLIED**

Marked optional in proposed-edits.md. The existing prose ("Launch
all five in a single message with parallel tool calls. Use the
`Agent` tool with `subagent_type: "general-purpose"` for each.") is
sufficient direction; spelling out a 5-shot tool-call template
would bloat the skill without adding information the orchestrator
agent can't derive. Skipped.

## Verification of values against source/ and other repo paths

- `sessions/2026-06-02-cf6402-review-validation.md` — DOES NOT
  EXIST. Verified via `find sessions/ -name '*6402*'`.
- `.claude/skills/pg-corpus-maintainer/` — DOES NOT EXIST. Verified
  via `ls .claude/skills/`. The closest analogue is the
  `hf(corpus):` commit convention in `.claude/rules/pg-implement-
  discipline.md` Rule R9.
- `knowledge/calibration/gap-catalog.md` — EXISTS at expected path.
  Item numbering #1-#11 confirmed via `grep -n` against the file.
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`
  — EXISTS; REJECT-A/B/C grade definitions verified at lines 84-88
  (per `grep -n REJECT`).
- `.claude/skills/review-checklist/SKILL.md` Phase 0 — EXISTS at
  lines 43-159; REJECT-track at lines 63-93; three reflex gates at
  lines 95-159.
- `.claude/rules/pg-implement-discipline.md` Rule R9 — EXISTS;
  explicitly names "the corpus needs a `hf(corpus)` fix in a
  SEPARATE meta-repo commit".
- macOS pre-existing flake `recovery/040_standby_failover_slots_sync`
  — referenced in multiple sessions/ and progress/STATE.md files;
  used in Edit #4 as a real example.

## Score progression

Iter 1: with_skill 32/32 (1.000), baseline 9/32 (0.281).
Iter 2: with_skill 32/32 (1.000), baseline 9/32 (0.281).

Numeric score unchanged. The qualitative value of iter-2:
- Two broken cross-references (catalog and the validation file) are
  now either fixed (Edit #2) or tagged `[unverified]` (Edit #1).
- The Critic-E severity contract is now scannable as a table
  (Edit #3) instead of being scattered across 8 prose paragraphs.
- The skill is self-contained when invoked without `/pg-review`
  (Edit #4 — inline Stage-0 recipe).
- The "Critic E recommends; Stage 3 decides" rule is now visible
  from the §Stage 3 block where the orchestrator reads it
  (Edit #5).

Per the campaign SUMMARY pattern (15+ skills saturated at 100% on
iter-1), the right iter-2 measurement is qualitative: did the
edits land cleanly + did the agent catch real bugs in the proposed
edits during application? In this case: yes (two dead references
caught, hf(corpus) workflow correctly identified as the
replacement).
