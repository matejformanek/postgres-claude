# Proposed edits — iteration 1 (NOT applied)

## Summary of gaps found

The skill scores high on with_skill (29/31, 93.5%) because the procedure + rules are tight. Two with_skill misses, both on Eval 3:

- **Bisectability rationale** — no place in SKILL.md or `pg-implement-discipline.md` explicitly names `git bisect` as a reason "WIP" commits and broken-phase commits hurt. The rules say *what* is forbidden but not *why* in the operational `bisect`/history sense.
- **Reviewer-cognition rationale** — the rules say "may go upstream via format-patch" but don't spell out that **every individual commit in a posted series is expected to compile + pass tests on its own**, which is what makes broken-phase commits especially toxic for upstream review.

Baseline almost passed on:

- R3 / no-interleaving (general "don't start phase 4 before phase 3 is done" instinct).
- Phase-end check (general "run tests before commit").
- Incremental build (general C-hacking habit).
- Naming three escalation paths for scope creep (general "small fix vs separate patch vs replan" judgment).

These are places where the skill could make the difference more cleanly by naming the PG-specific binding constraint (rule number, file:line cite, or named convention) so the with_skill answer is forced to cite, not just paraphrase general practice.

## Concrete edits to consider

### Edit 1 — Add bisectability + per-commit-must-pass rationale to SKILL.md §Strict rules / and/or §Style

**Anchor:** `.claude/skills/pg-implement/SKILL.md` around the existing §"Strict rules" block (lines 65–85) OR as a new "Why these rules exist" sub-block.

**Proposed addition (just before the existing six-item rules list, OR as new section after §Style):**

```markdown
### Why per-phase = per-commit + per-test

Two operational reasons every phase ends with a green-tested commit:

1. **Bisectability.** `git bisect` across a multi-phase patch series is
   only useful if every commit individually builds and passes the
   declared phase-end check. A broken commit in the middle of the
   series poisons bisect for the next decade of this code.
2. **Per-commit reviewability.** When the series eventually goes to
   pgsql-hackers via `format-patch`, reviewers read commits one at a
   time. Upstream PG convention is that **each commit in a posted
   series compiles and passes tests on its own** — a known-broken
   "WIP" commit, even one with a TODO trailer, is grounds for the
   patch being bounced before review starts.

This is why R3 (no interleaving), R4 (phase-end check before commit),
and the anti-pattern list (no WIP commits, no --amend across phases)
together act as one rule, not three.
```

**Verification needed:** none — these are project-policy statements, not source-cited PG facts. Verified by reading the existing `pg-implement-discipline.md` "Anti-patterns" section + R4 + R5 to confirm consistency.

**Status:** verified (policy claim, not source claim).

### Edit 2 — Inline the notes.md "Status" field values in SKILL.md so they're discoverable

**Anchor:** SKILL.md §"Phase-end log" step 14 — the existing template block already shows `**Status:** done | partial | deferred`.

**Proposed change:** add one short sentence under the template explaining when to use each:

```markdown
- `done` — phase-end check green, commit landed.
- `partial` — phase ended with known follow-ups inside the same phase
  scope (rare; requires user agreement per R7 path-1).
- `deferred` — phase stopped before its phase-end check could run
  green; branch parks here until the blocker is resolved. The next
  session reads this status first.
```

**Why:** Eval 3 specifically asked about the legitimate way to stop a phase mid-failure. The values exist in the template, but their semantics aren't spelled out — the with_skill answer had to infer them.

**Verification needed:** none — these are the values already in the SKILL.md template + `pg-implement-discipline.md` R8 wording, just expanded with intended semantics. Verified consistent with R8.

**Status:** verified.

### Edit 3 — Cross-link the SKILL.md drift-threshold to R2 explicitly

**Anchor:** SKILL.md §"Strict rules" item 2 (line 73–74):

> 2. **Verify before edit.** Spot-check 3-5 file:line citations from the plan against current source before phase 1. If drift > 10%, stop and re-run `/pg-plan` to refresh.

**Proposed replacement:**

> 2. **Verify before edit (R2).** Spot-check 3-5 file:line citations from the plan against current source before phase 1. **Drift threshold:** citations off by more than ~20 lines, or naming a since-removed symbol. If drift > 10% of the spot-checked sample, STOP — re-run `/pg-plan` to refresh; do not push through with a stale plan.

**Why:** the current SKILL.md says ">10%" without defining what "drift" means; R2 in `pg-implement-discipline.md` defines it more precisely ("off by more than ~20 lines or naming a since-removed symbol"). Promoting R2's definition into SKILL.md saves a doc hop.

**Verification needed:** Confirm R2 wording matches. Read `.claude/rules/pg-implement-discipline.md` R2 — current text says "off by more than ~20 lines or naming a since-removed symbol". Match.

**Status:** verified.

### Edit 4 — Surface the R6 forbidden-language example inline

**Anchor:** SKILL.md §"Style" (lines 226–233), the bullet that says: "Be specific in commit messages. 'fix bug' is forbidden..."

**Proposed addition (extend the existing bullet):**

> Be specific in commit messages (R6). "fix bug" is forbidden; "set
> `dropPin = false` for non-MVCC scans (plan phase 2, site
> `nbtree.c:421`)" is right. Any "fixes" / "addresses" / "implements"
> claim must point to a file:line in `source/` or a specific plan
> section (`§4 Catalog impact`, etc.).

**Why:** R6's wording (the verbs "fixes / addresses / implements" specifically) is sharper than SKILL.md's current phrasing. Importing it makes the rule discoverable without a doc hop.

**Verification needed:** Confirm R6 wording in `pg-implement-discipline.md`. R6 text: "Any 'addresses', 'fixes', or 'implements' claim in a commit message must point to a file:line in `source/` (for plan-cited sites) or a specific section in the plan (`§4 Catalog impact`, etc.)." Match.

**Status:** verified.

### Edit 5 — Promote the anti-pattern list summary into SKILL.md (currently only in rules)

**Anchor:** SKILL.md §"Strict rules" — add a sub-block at the end of that section.

**Proposed addition:**

```markdown
### Forbidden patterns (see rules §Anti-patterns)

- **WIP commits.** Every commit in `dev/` is a complete phase. No
  "wip: more of phase 3".
- **`--amend` across phases.** To correct a previous phase, use a NEW
  commit with a `Fixes: <sha>` trailer — never `--amend`.
- **Commits without a `Plan:` trailer in dev/.** If you're committing
  in `dev/`, you're implementing a plan — name it.
- **Cherry-picking individual phases.** All phases or none.
- **Mixing meta-repo + `dev/` writes in one bash invocation.** Pick
  one direction per phase (R10).
```

**Why:** these are listed in the rules file's "Anti-patterns" section, but a reader of SKILL.md alone won't see them — they have to know to hop to the rules. Mirroring them in SKILL.md tightens the contract; the cross-reference still points at the rules file as authoritative.

**Verification needed:** Confirm wording matches `pg-implement-discipline.md` "Anti-patterns" section. Five bullets verified verbatim.

**Status:** verified.

### Edit 6 — (low priority) Name the slug-naming convention example in SKILL.md

**Anchor:** SKILL.md §Inputs (lines 46–52).

**Proposed addition (as a sub-bullet under "Slug"):**

> Example: `sp2-pgstr-maxalloc`, `feature_server_side_vars`. Branch
> name in `dev/` mirrors the slug (e.g.
> `feature_sp2_pgstr_maxalloc`).

**Why:** real plans live under `planning/{cb1,cb7,cb8,sp2,sp6,sp7}-...` slugs; SKILL.md doesn't name the convention, so a new user has to grep `planning/` to learn it.

**Verification needed:** Read `planning/` ls in the worktree — confirm the slug pattern. Verified: `cb1-pgcrypto-bomb`, `cb7-ltree-amplification`, `cb8-hstore-forge`, `sp2-pgstr-maxalloc`, `sp6-autoprewarm-revoke`, `sp7-tablefunc-quoting`. R1 references "e.g. `feature_server_side_vars`" so the branch-name convention is already in rules.

**Status:** verified.

## Non-edits

- The skill correctly delegates to `commit-message-style` for the upstream PG format rather than duplicating it inline. Keep this split.
- The R10 two-repo separation is well-stated in both SKILL.md "Boundaries vs other skills" and rules. No edit needed.
- The cross-references block at the end of SKILL.md is comprehensive and current. No edit needed.

## Expected score impact

Iter-1 with_skill: 29/31 (93.5%), baseline: 12/31 (38.7%).

- Edit 1 (bisectability + per-commit-pass rationale) directly closes the two with_skill misses (Eval 3 assertions 7 + 8). Projected: 31/31 (100%).
- Edits 2-5 are defensive — they harden against regression and tighten the with_skill answer on prompts not in this set.
- Edit 6 is structural / low-priority.

If iter-2 uses the same assertions, projected with_skill = 31/31; baseline largely unchanged (~12/31).

If iter-2 uses harder variants (which I'll consider), the new floor on baseline may rise slightly as the prompts become more open-ended (e.g. "what could go wrong in a multi-phase implementation"). I'll note the choice in the iter-2 SUMMARY.
