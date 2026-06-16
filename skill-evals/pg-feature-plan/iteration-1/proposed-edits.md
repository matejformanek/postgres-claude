# Proposed edits — iteration 1 (NOT applied yet)

## Summary of gaps surfaced by iter-1

`pg-feature-plan` is a structurally rich skill — Step 0 scenario contract,
§8a coverage gate, M2 context awareness, M5 engagement classification, §9
REJECT-track hand-off. The iter-1 evals showed the skeleton works, but
exposed five gaps where a planner skimming SKILL.md could plausibly:

1. **Drop scenario rows from §3** when they're "NOT edited" (e.g. ecpg
   pgc.l, psqlscan.l, check_keywords.pl). The §3 required-section
   description doesn't restate the Step 0 pin contract, so a planner
   reading §3 in isolation might trim the table to "files that actually
   change". The MERGE_THEN eval surfaced this — 6 of 16 scenario rows
   are "NOT edited" and a tight reader would prune them.

2. **Write a REJECT-track output as a phased plan with a tiny verdict
   line on top** rather than as a Verdict-shaped document. The skill says
   "the plan's recommended verdict shifts to REJECT" but does not name the
   Verdict-block contents (N reasons + grade + predicted reviewer +
   alternative).

3. **Refer vaguely to "Likely reviewers"** in §12 without a reflex-map.
   For REJECT-track in particular, identifying the persona whose reflex
   the proposal triggers (Tom Lane = type-system + dump-determinism;
   Andres = perf hot path; Noah = security) is part of producing a
   community-credible verdict.

4. **Not surface the REJECT-A/B/C grade rubric inline.** The skill links
   to `review-checklist/SKILL.md` Phase 0 but doesn't tell the planner
   what A/B/C mean. A planner could reasonably output verdict=REJECT and
   skip the grade.

5. **Not name the scenario layer's "ADD never DROP" rule outside Step 0.**
   The pin contract appears once at line ~263-268. §3 (the section that
   *renders* the contract) doesn't reference it.

## Concrete edits

### Edit 1 — Re-state the Step 0 pin contract in §3's required-section description

**Location:** SKILL.md lines 132-142 (the §3 "Files that change" required
section).

**Change:** after "Missing a file in this table is a Phase 2 bug.", add:

> **Pin contract reminder (from Method Step 0):** every file named in
> the pinned scenario's checklist MUST appear in §3, including rows
> marked `NOT edited` (build-time validators, auto-generated headers,
> sync-trap files like `psqlscan.l` / `ecpg/pgc.l`). Listing a row as
> `NOT edited` with a one-line rationale is correct; silently dropping
> it is the failure mode the §8a coverage gate catches.

**Rationale:** the MERGE_THEN eval has 6 NOT-edited rows out of 16. A
planner reading only §3 could plausibly trim those. The pin contract
language exists at Step 0 but doesn't echo at §3.

**Verification:** confirmed scenario `add-new-sql-keyword` rows 3, 4, 7,
8, 9, 10, 11, 13, 15, 16 are NOT-edited yet still load-bearing for
correctness (sync traps + build-time validators). Confirmed Step 0 lines
263-268 already have the pin contract — this edit echoes, doesn't
contradict.

### Edit 2 — Specify REJECT-track output structure

**Location:** SKILL.md ~line 116 (end of the "Thread-engagement
classification (M5)" section) or as a new section before "## Output".

**Change:** add a short subsection:

```
## REJECT-track output shape (when verdict is REJECT)

When the Context-awareness probe (M2) or Engagement classification (M5)
recommends REJECT, the plan file's body becomes a **Verdict block** in
place of §3-§14. Required contents:

1. **Verdict line.** `REJECT-A`, `REJECT-B`, or `REJECT-C` per the
   `review-checklist/SKILL.md` Phase 0 rubric (summarized below).
2. **N concrete reasons against the design** (numbered, 3-7 typical).
   Each cites a `source/<path>:<line>` invariant, a
   `knowledge/subsystems/<x>.md` INV-tag, or a documented persona
   reflex.
3. **Predicted lead reviewer** with the reflex they trigger
   (e.g. "Tom Lane — type-system + dump-determinism").
4. **Concrete alternative shape** if one exists (the "what they
   probably wanted" rewrite). Skip only if the proposal is irredeemable.
5. **Hand-off line** points to `review-checklist/SKILL.md` Phase 0
   ("Write a thread reply"), NOT `/pg-implement`.

The §1 "What this plan is" + Context block still appear; §2-§14 do not.

### REJECT-A/B/C grade summary (full rubric: `review-checklist/SKILL.md` Phase 0)

| Grade | Meaning |
|---|---|
| `REJECT-A` | Identified all critical design problems + proposed correct alternative. Saves community cycles. |
| `REJECT-B` | Identified most critical problems but missed one. |
| `REJECT-C` | Rejected for wrong reasons OR rejected a sound proposal. Self-correct: re-run as a serious plan. |
```

**Rationale:** the money-fx-exchange eval forced a REJECT plan, and
without this section the skill leaves the *shape* implicit. The Method
§9 hand-off line correctly redirects to review-checklist, but the
planner has no template for what the plan.md file itself should contain.

**Verification:** REJECT-A/B/C rubric copied from
`source` of the local file `.claude/skills/review-checklist/SKILL.md:83-87`,
not invented.

### Edit 3 — Add reflex-map hint to §12 "Likely reviewers"

**Location:** SKILL.md line 218 (the `Likely reviewers?` bullet under §12).

**Change:** expand the bullet:

```
- Likely reviewers? Name 2-3 with the **reflex** each would apply.
  Anchor on the file the patch touches:
  - Type-system / catalog / dump-determinism / API-back-compat → Tom Lane
  - Performance / executor hot path / parallel safety → Andres Freund
  - Security / install-script immutability / test-omission → Noah Misch
  - Parser / locale / Windows → Michael Paquier, Peter Eisentraut
  - Replication / logical decoding → Amit Kapila, Masahiko Sawada
  See `.claude/personas/` if those notes exist; otherwise grep
  `git -C source log --pretty='%an' -- <touched-file>` for recent
  committers.
```

**Rationale:** the REJECT eval needs a reflexive "who's going to land on
this with what objection" prediction. The current bullet just says "Authors
of nearby subsystems" which is a generic technique, not a useful reflex map.

**Verification:** I'll cite the personas/ directory only if it exists in
the worktree; if not, the bullet drops the cite and keeps the inline map.

### Edit 4 — Cross-link §3 to §8a explicitly

**Location:** SKILL.md line 142, just after the (proposed) "Pin contract
reminder" from Edit 1.

**Change:** add:

> The §8a Scenario-coverage gate at Method Step 8a verifies this contract
> at plan-finalization time. A plan that fails §8a is a planning bug,
> not an implementation bug — fix it before hand-off.

**Rationale:** the §8a gate exists at line ~335 but §3 doesn't reference
it. Closing the citation loop helps a planner who reads sections in order.

### Edit 5 — Cite a specific file:line example in the §3 description

**Location:** SKILL.md line 138 ("Per-file doc citation").

**Change:** rephrase that bullet to:

```
- Per-file doc citation: `[via knowledge/files/.../X.md]` if one exists;
  AND a `source/<path>:<line>` cite for any file:line claim in the
  one-sentence summary. Example row:
  `src/backend/utils/adt/lockfuncs.c | modify | small | Add PG_FUNCTION_INFO_V1 + body (model after pg_advisory_lock at source/src/backend/utils/adt/lockfuncs.c:605-650) | —`
```

**Rationale:** the skill repeatedly says "Cite or don't claim" (line ~382)
and §3 enforces the cite contract by exemplar. Currently §3 doesn't *show*
the cite shape.

### Edit 6 — Tighten the "Forbidden in Phase 2" list

**Location:** SKILL.md line 238 ("Forbidden in Phase 2").

**Change:** add a fourth bullet:

```
- Dropping a scenario-checklist row from §3 without an explicit user
  approval + a follow-up edit to the scenario file itself. The §8a
  coverage gate fails the plan if it happens silently.
```

**Rationale:** the existing forbidden-list catches vague references and
"we'll figure it out", but doesn't explicitly forbid the silent-drop
failure mode that the MERGE_THEN eval probes. The rule is already in
Step 0 — this is just promotion.

## Non-edits considered + dropped

- **Don't inline the REJECT-A/B/C rubric in full.** The skill correctly
  delegates to `review-checklist/SKILL.md` Phase 0; only the *summary
  table* belongs inline (Edit 2). Duplicating the full rubric would
  drift.
- **Don't list every persona in `.claude/personas/`.** Edit 3 hits the
  5 most common reflex-mapping anchors; the rest stays in the personas
  directory.
- **Don't restructure Step 0.** It's already correct. Edits 1+4 echo
  Step 0's contract into §3 without changing Step 0 itself.
- **Don't add a new §15.** The 14-section spine works; adding a §15 for
  "predicted reviewer reflex" would just bloat the template. Reflex
  hint lives in §12 (Edit 3).

## Score-delta estimate if all edits applied

Iter-1 with_skill: 35/35 (1.000), baseline 9/35 (0.257), lift +0.743.

Edits 1, 4, 6 harden against the scenario-drop failure mode that the
MERGE_THEN eval probed. Edits 2, 3 sharpen the REJECT-track output.
Edit 5 is cosmetic (showing the cite shape by exemplar).

Expected iter-2 with_skill: still 35/35 (rubric saturated). Real
measurement will be the qualitative one: does the planner spontaneously
emit Verdict block shape on the REJECT eval without being told, and does
it preserve all 16 scenario rows on the keyword eval?
