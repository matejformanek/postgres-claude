# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found in grading

The with_skill answers passed 32/32 assertions — the SKILL.md content
already covers the five-stage pipeline, the five critics (A-E), the
REJECT-A/B/C verdicts, and the Phase-0 gates by reference. Baseline
9/32 lifts cleanly with the skill (+23pp at the question level,
+72pp on absolute pass rate).

Three real defects surfaced while writing the answers and verifying
cites against the repo:

1. **Dead path reference** — SKILL.md §"Validation reference" cites
   `sessions/2026-06-02-cf6402-review-validation.md`. That file
   does not exist in `sessions/`. The calibration anchor used by
   the skill is itself broken.
2. **Dead skill reference** — SKILL.md §"What to escalate to the
   user mid-review" tells the user to "ask whether to refresh the
   corpus first via `pg-corpus-maintainer`". No such skill exists
   in `.claude/skills/`. The escalation path is wired to a missing
   handler.
3. **Implicit Critic-E severity matrix** — the per-probe severities
   ARE in the SKILL.md prose ("warning by default, escalates to
   blocking if..."), but they're scattered through eight prose
   paragraphs. A reviewer scanning the skill won't be able to
   answer "what severity should I assign for catalog #4?" without
   re-reading the whole section. A summary table at the end of
   §Critic E would make the contract scannable.

Two structural improvements that the eval prompts surfaced:

4. **Stage 0 → Stage 1 boundary is fuzzy when invoked directly**
   (not via `/pg-review`). The skill says "If invoked directly,
   this skill does it inline before stage 1" without specifying
   the minimum command list — a critic agent reading this skill
   doesn't know whether to start at Stage 0 or assume it's done.
5. **No named contract for the "verdict-recommends vs verdict-
   decides" split.** The SKILL.md §Critic E says "Critic E
   *recommends*; Stage 3 *decides*" once. Worth pulling out into
   the Stage 3 verdict section so the orchestrator agent knows it
   may overrule.

## Concrete edits to consider

### 1. Remove or replace the dead `sessions/2026-06-02-cf6402-review-validation.md` cite (BLOCKING)

Current text at SKILL.md:564-568:

> ## Validation reference
>
> The 2026-06-02 v0 review of CF #6402 in
> `sessions/2026-06-02-cf6402-review-validation.md` is the calibration
> target — re-running THIS skill against that patch should reproduce a
> review of comparable quality (same draft conclusion, same blocking-vs-nit
> split) in less wall time than the v0 manual walk.

**Issue:** the cited session file does not exist. The closest related
sessions are `2026-06-02-access-nbtree-synthesis.md` and
`2026-06-02-phase-a-setup.md`, neither of which is a CF #6402 review.

**Proposed edit options** (need user input):
- (a) Drop the §Validation reference section entirely until a real
  validation run produces a session file.
- (b) Replace the cite with a placeholder marker
  `[unverified: calibration target was the cf6402 manual review;
  session log not preserved]` per the cite-or-tag rule in
  `pg-claude/CLAUDE.md`.
- (c) Run the skill against a real patch in a follow-up session and
  drop the new session path in.

Recommend (b) for iter-2 — preserves the calibration intent without
claiming a file that doesn't exist.

### 2. Remove or replace the `pg-corpus-maintainer` reference (BLOCKING)

Current text at SKILL.md:526-528:

> - **Corpus drift** detected in stage 1 (cites stale > 10%): stop, ask
>   whether to refresh the corpus first via `pg-corpus-maintainer` or to
>   proceed with a "best-effort against possibly-stale docs" caveat.

**Issue:** no `pg-corpus-maintainer` skill exists. The escalation
points into the void.

**Proposed edit:** replace with the manual `hf(corpus):` workflow
that DOES exist (per Rule R9 of `pg-implement-discipline.md`):

> - **Corpus drift** detected in stage 1 (cites stale > 10%): stop,
>   ask the user whether to (a) refresh the corpus first via a
>   separate `hf(corpus):` commit (per Rule R9 of
>   `.claude/rules/pg-implement-discipline.md` — corpus fixes are
>   their own commits in the meta-repo), or (b) proceed with a
>   "best-effort against possibly-stale docs" caveat noted in the
>   review email's "Testing performed" block.

### 3. Add a Critic-E severity-matrix table at end of §Critic E

Current state: severities are buried in prose across 8 catalog-item
paragraphs. Proposed end-of-section addition:

```
**Critic E severity matrix at a glance:**

| Catalog # | Probe | Default | Escalates to blocking when |
|---|---|---|---|
| #4 | Cleanup-on-early-return | warning | COVER doesn't acknowledge the cleanup question |
| #5 | Multibyte / encoding | warning | text-primitive cap added with no per-encoding analysis in COVER |
| #6 | Subsystem-local cap discoverability | suggestion | — |
| #7 | "Third state" binary-format | warning | COVER doesn't enumerate bit-set-but-invalid AND bit-unset-but-looks-valid cases |
| #8 | injection_points reproducer | warning | structural argument on a security claim with no injection_points test |
| #9 | Hot-path micro-benchmark | suggestion | — |
| #10 | Symmetric-check refactor | suggestion | — |
| #11 | Persona-aware backpatch routing | suggestion | — |

REJECT-track escalation: 3+ `blocking` from this table AND context-
awareness signal (engagement class `contested` OR foreclosed
`INV-*`) → recommend REJECT-A to Stage 3.
```

Rationale: matches the existing prose, makes the contract
scannable. Verified against SKILL.md:353-365.

### 4. Tighten the Stage 0 → Stage 1 boundary for direct invocation

Current text at SKILL.md:86-89:

> Done by the `/pg-review` slash command. If invoked directly (without
> `/pg-review`), this skill does it inline before stage 1. See
> `.claude/commands/pg-review.md` for the exact recipe.

**Proposed addition:** inline the minimum Stage-0 command list, so
the skill is self-contained when invoked directly:

```
**Inline Stage 0 (when /pg-review wasn't used) — minimum commands:**

1. `cd dev && git checkout master && git pull`
2. `git checkout -b cf<N>-review` (or `pr<N>-review`)
3. Fetch the patch (CF: `curl` the v<N> from the CF entry;
   PR: `gh pr checkout <N>`; .patch file: copy in).
4. `git am /path/to/v*.patch` (apply all v<N> hunks in order).
5. `ninja -C build-debug install` — must be warning-clean.
6. `meson test --no-rebuild regress/regress` — record pass/fail.
7. `meson test --no-rebuild --suite isolation` — record pass/fail.
8. `git diff --name-only HEAD~<N>..HEAD` — capture the touched-files
   list.
9. Note any pre-existing flakes (e.g. macOS
   `recovery/040_standby_failover_slots_sync`).

Output of this stage is the dispatch block (§Stage 1 step 4); pass
it to all five critics in Stage 2.
```

### 5. Promote the "Critic E recommends; Stage 3 decides" rule into the Stage 3 §Verdict block

Current text at SKILL.md:373-380 has this only inside Critic E's
prose. Proposed addition to §Stage 3:

> **Critic-E recommendation vs orchestrator verdict.** Critic E may
> emit `recommend_verdict: REJECT-A | REJECT-B` when its catalog-item
> threshold (3+ blocking findings + context-awareness signal) fires.
> The orchestrator at Stage 3 *decides*; Critic E *recommends*. The
> orchestrator may downgrade the recommendation to "Waiting on
> Author" if the findings, in aggregate, do NOT compose to a
> design-level NACK. Critic E's recommendation is one input, not the
> verdict.

### 6. Optional: REJECT-A/B/C decision tree as a flowchart

Current §Stage 3 §Verdict has the three grades as bullet items. A
small ASCII decision tree could make the branching scannable:

```
Patch is design-rejectable per Phase 0 REJECT-track triggers?
├── No → Ready for Committer / Waiting on Author / Needs more info
└── Yes →
    ├── All critical issues identified + alternative proposed →
    │       REJECT-A (mail the reply)
    ├── Most issues identified, missed at least one major →
    │       REJECT-B (mail, acknowledge gaps)
    └── Rejected wrongly OR proposal actually sound →
            REJECT-C (STOP — escalate to user before posting)
```

Optional / nice-to-have; not blocking.

### 7. Optional: explicit "what counts as a critic in parallel" note

The skill says "Launch all five in a single message with parallel
tool calls. Use the `Agent` tool with `subagent_type:
"general-purpose"`". A concrete example block in the skill (one
tool-call shape repeated 5x) would remove all ambiguity for the
orchestrating agent. Currently each agent has to figure out the
prompt template per critic. Optional.

## Non-edits

- The five-stage structure is the right scaffold — no restructuring
  proposed.
- The split between this skill and `review-checklist` is correct
  (orchestration vs scaffold) — the §Boundaries section already
  states it clearly.
- The §Companion-skills list (10 sibling skills) is accurate and
  matches the references in the body.
- The §When NOT to invoke section is right — the three exclusions
  (already-merged, own-patch, non-PG) are the right exclusions.

## Score delta if all edits applied

Iteration 1 with_skill: 32/32 (1.000). All assertions already pass.
The edits are NOT about lifting the score; they're about fixing two
broken file references and making the Critic-E severity contract
scannable. Iteration 2's value will be qualitative: did the broken
references get cleaned up, did the severity matrix land cleanly?
