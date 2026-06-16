# Iteration 2 — answers

Same three prompts as iter-1, run against the UPDATED `.claude/skills/pg-implement/SKILL.md` (six edits from `iteration-1/proposed-edits.md` applied — see `edits-applied.md`).

`baseline` is identical to iter-1 (general PG-internals + Claude Code workflow knowledge only; not regenerated). `with_skill` is regenerated with the updated SKILL.md content loaded.

---

## Eval 1 — Walk through phase 2 of sp2-pgstr-maxalloc

### with_skill

Phase 2 implementation against `planning/sp2-pgstr-maxalloc/plan.md` — slug pattern matches the in-repo examples (`sp2-pgstr-maxalloc`, `cb1-pgcrypto-bomb`, `sp7-tablefunc-quoting`) named in SKILL.md §Inputs. The procedure lives in SKILL.md §Method; the binding invariants are R1–R12 in `.claude/rules/pg-implement-discipline.md`. Where they disagree, rules win.

**Pre-phase (5 min) — SKILL.md §Pre-phase, R2:**

1. Open `planning/sp2-pgstr-maxalloc/plan.md` and read the phase-2 sub-section: "Files this phase touches", "5–10 concrete edits", and "Phase-end check".
2. **R2 pre-flight verify.** Spot-check 3–5 file:line citations from phase 2 against current `source/`. Drift signals (per SKILL.md §Strict rules item 2): citations off by more than ~20 lines, or naming a since-removed symbol. If drift > 10% of the spot-checked sample, STOP — re-run `/pg-plan` to refresh; do not push through with a stale plan.
3. Re-read the relevant `knowledge/subsystems/X.md` doc and the per-file docs for files in this phase. Note any `INV-*` invariants the phase touches.
4. Decide on cluster state: if phase 2 edits a catalog or adds a GUC, `/pg-stop` first because the postmaster will need a fresh start. Otherwise keep it running for fast feedback (SKILL.md §Pre-phase step 4).

**Edit (the main work) — SKILL.md §Edit:**

5. Make the 5–10 edits the plan names. Prefer `Edit` over `Write` to preserve surrounding context and produce clean diffs.
6. After each edit in `src/backend`, run `cd dev/build-debug && ninja install 2>&1 | tail -5`. Catch compile errors immediately, not at phase end.
7. Append to `planning/sp2-pgstr-maxalloc/notes.md` as you go: file + line range + one-sentence "what", plus surprises (e.g. a comment imposing an unexpected constraint) and drift from the plan. R8 makes this notes log mandatory.

**Phase-end check — SKILL.md §Phase-end check, R4:**

8. Run exactly the test scope named in the plan's phase-2 phase-end check:
   - Most phases: `meson test --no-rebuild regress/regress`.
   - Catalog/WAL phases: regress + `meson test --no-rebuild --suite isolation`.
   - Replication phases: above + relevant TAP under `meson test --no-rebuild --suite recovery`.
9. **R4: phase-end check must pass before commit.** Failures during this phase belong to this phase — fix-in-place, do NOT commit broken state and "follow up".
10. Once green, run `git -C dev status` and verify the changed files match the plan's §3 file table for this phase. Flag any extras to the user before committing (the R7 scope-creep gate).

**Per-phase commit — SKILL.md §Per-phase commit, R5:**

11. Stage the phase's files: `git -C dev add <files>`.
12. Compose the commit via the `commit-message-style` skill (upstream PG style): imperative title scoped to **the phase** (NOT the whole feature); wrap body near 76 cols; no `Co-Authored-By` because dev/ commits may be `format-patch`-ed upstream.
13. Required trailers per R5 / SKILL.md §"Plan-linked commit message format":
    - `Plan: planning/sp2-pgstr-maxalloc/plan.md (phase 2: <phase title>)` — **required**.
    - `Sites: <file:line>, <file:line>, ...` when the diff spans more than one non-obvious file (3–5 max).
    - No emoji, no conventional-commits prefix, no ticket numbers, no Signed-off-by.
    - R6: any "addresses" / "fixes" / "implements" claim in the body must point to a file:line in `source/` or a specific plan section (`§4 Catalog impact`, etc.).

**Phase-end log — SKILL.md §Phase-end log, R8:**

14. Append to `planning/sp2-pgstr-maxalloc/notes.md`:

    ```markdown
    ## Phase 2 — <title> — <date> <time>

    **Status:** done | partial | deferred
    **Commit:** <short-sha> "<title>"
    **Tests run:** <scope> — <result>

    ### What changed
    - <one-line summary per site>

    ### Surprises / drift
    - <anything that wasn't in the plan>

    ### What this phase did NOT do
    - <items deferred to later phases>
    ```

    Status field semantics (SKILL.md §Phase-end log):
    - `done` — phase-end check green, commit landed.
    - `partial` — known follow-ups inside the same phase scope; rare, requires user agreement per R7 path-1.
    - `deferred` — phase stopped before phase-end check went green; branch parks until the blocker is resolved.

15. Tell the user phase 2 is done, name phase 3, ask whether to continue. R3 forbids interleaving — phase 2 (including commit + notes append) must finish before phase 3 starts.

**Forbidden patterns** (SKILL.md §Forbidden patterns, mirroring rules §Anti-patterns):
- No `wip: more of phase 2` commits — every commit in `dev/` is a complete phase.
- No `--amend` across phases; use a NEW commit with a `Fixes: <sha>` trailer.
- No committing without a `Plan:` trailer in dev/.
- No cherry-picking individual phases.
- No mixing meta-repo + `dev/` writes in one bash invocation (R10).

### baseline

(Identical to iter-1; not regenerated.)

To implement phase 2 of the plan, I'd start by opening the plan file and re-reading the phase-2 section so I know what's in scope. Then:

1. Make sure phase 1 is committed cleanly and tests still pass on that branch.
2. Read through the file:line references in phase 2 and sanity-check them — code drifts.
3. Make the edits one by one. After each meaningful change, run `ninja` (or `make`) in the build directory.
4. Once edits are done, run the regression test suite. Run isolation or TAP tests too if relevant.
5. If tests fail, fix them before committing.
6. Commit using a reasonable PostgreSQL-style commit message: imperative subject, wrapped body, no emoji. Mention the phase so reviewers can correlate.
7. Update working notes.
8. Move on to phase 3 only after phase 2 is fully done.

A few standard cautions: don't mix unrelated changes into one phase; if the plan was wrong about a file, stop and talk to the planner; if the phase involves catalog changes you'll need to restart the postmaster.

---

## Eval 2 — Mid-phase need to touch a file outside §3

### with_skill

This is the textbook scope-creep case **R7** exists for, and SKILL.md §Strict rules item 6 (which now cross-references R7 explicitly) makes it discoverable from the skill itself.

**Step 1 — STOP editing.** R7 is unambiguous: "If a phase reveals a needed change outside the plan's §3 'Files that change' table, STOP." Do NOT silently add `visibilitymap.c` to the diff. Silent scope expansion is forbidden under SKILL.md §Forbidden patterns and rules §Anti-patterns.

**Step 2 — Classify the new site.** R7 enumerates three resolution paths in order of preference (now mirrored in SKILL.md §Strict rules item 6):

1. **Small + tightly coupled to the in-flight phase** → update the plan (add `visibilitymap.c` to §3 with a one-line "added during phase 3 — see notes.md") AND add it to the commit's `Sites:` trailer. Continue the phase. Cheapest path; appropriate when the new site is a 1–5 line edit intrinsic to making the phase compile or pass tests.
2. **Separate concern** → defer to a follow-up patch. Record the deferral in `planning/<slug>/notes.md` under "Surprises / drift" per R8's template. Do NOT touch `visibilitymap.c` in this phase.
3. **The new site invalidates the phase boundary** → escalate to the user for a re-plan. Phase as scoped is wrong; pushing through corrupts the plan structure.

**Step 3 — Pick a path, but only with the user's go-ahead if it's not (1).** SKILL.md §"When to escalate to the user" lists "A phase reveals a needed change outside §3 file table (scope creep)" as an explicit escalation trigger. Tell the user what you found, propose which path fits, wait. Do not push through.

**Step 4 — Document.** Regardless of path chosen, the `notes.md` append for phase 3 (per R8) must include the surprise:
- "Surprises / drift" section: "phase 3 needed an edit in `visibilitymap.c:NNN` that wasn't in §3. Resolved by <path 1 / 2 / 3>."
- Path (1): the plan file gets a `Sites:` row added and the commit's `Sites:` trailer lists `visibilitymap.c:NNN`.
- Path (2): the new site is named under "What this phase did NOT do" with a pointer to the follow-up.

**Step 5 — R9 citation chain stays linked.** Commit → `Plan:` trailer → plan file → corpus cites → `source/<path>:<line>`. If the plan now references a site not previously in the corpus, that's a corpus gap — fix it in a **separate** meta-repo commit (R10 two-repo separation; the `dev/` patch is one commit, the corpus update is a different commit in `postgres-claude/` using `meta-commit-style`).

**Why the rule exists.** Silent scope expansion is how patches grow from reviewable to un-reviewable. The phase boundary is what makes per-phase review possible. R7 + R10 together protect the reviewer's ability to read each commit on its own — and per SKILL.md §"Why per-phase = per-commit + per-test", that per-commit reviewability is what makes the series upstream-able at all.

### baseline

(Identical to iter-1.)

If a phase needs to touch a file the plan didn't anticipate, that's a sign the plan was incomplete. A few reasonable options:

- If it's a small, obviously-needed change (a helper that has to accept a new parameter), I'd just include it in the phase and call it out in the commit message.
- If it's bigger, I'd stop, ping the user, and ask whether to update the plan or punt the new file to a separate follow-up patch.
- I would **not** push through silently. Surprises in code review are bad.
- I'd note this in whatever working log I'm keeping.

Practically: the commit message should mention the unplanned site; if posting upstream I'd probably split into two commits to keep each commit focused.

---

## Eval 3 — Why can't we commit phase 3 with a regress failure as TODO?

### with_skill

The proposal violates several non-negotiable rules and, per SKILL.md §"Why per-phase = per-commit + per-test" (newly inlined from the proposed edits), the operational rationale is now explicit:

**SKILL.md §"Why per-phase = per-commit + per-test" — the two operational reasons:**

1. **Bisectability.** `git bisect` across a multi-phase patch series is only useful if every commit individually builds and passes the declared phase-end check. A broken commit in the middle of the series poisons bisect for the lifetime of this code.
2. **Per-commit reviewability.** When the series eventually goes to pgsql-hackers via `format-patch`, reviewers read commits one at a time. Upstream PG convention is that **each commit in a posted series compiles and passes tests on its own** — a known-broken "WIP" commit, even tagged TODO, is grounds for the patch being bounced before review starts.

**Rules violated in order of immediacy:**

- **R4 — Phase-end check must pass before commit.** Verbatim: "The plan's 'Phase-end check' for phase N (regress / iso / TAP scope as specified) must run green. Failures are this phase's problem; don't commit broken state and 'follow up'." A red regression is a phase-end-check failure, full stop. R4 alone makes the proposal forbidden.

- **R3 — One phase at a time, no interleaving.** "Finish phase N (including the phase-end check + the commit) before opening phase N+1." If phase 3's tests are red, phase 3 is NOT finished. Starting phase 4 on top of a red phase 3 violates R3.

- **R5 — Per-phase commit must be plan-linked AND in upstream PG style.** Upstream PG style has no "TODO" or "WIP" idiom — commits in `dev/` may be `format-patch`-ed to pgsql-hackers, and a broken commit in the series is a non-starter for upstream review. The `Plan:` trailer claim "phase 3" implies "phase 3 done"; committing red contradicts that.

- **SKILL.md §Forbidden patterns / rules §Anti-patterns — "WIP" commits forbidden.** Verbatim: "Every commit in `dev/` is a complete phase. No 'wip: more of phase 3'." A TODO-tagged broken commit is a WIP commit by another name.

- **R6 — Vague claims forbidden in commit messages.** "fix the bug" is the example the rule cites as forbidden. A commit message containing "TODO: regress failure to fix later" is the same anti-pattern — vague language standing in for a specific cite.

- **R12 — End-of-implementation gate.** Step 1 requires full `meson test --no-rebuild` green; step 2 requires `git log --oneline <base>..HEAD` to show N commits for N phases each with a `Plan:` trailer. Carrying a broken phase forward means R12 cannot fire at the end either — the broken commit is now embedded in the series and the only way out is a `Fixes: <sha>` follow-up commit, which clutters history.

- **SKILL.md §Phase-end check step 9 (matches R4).** "If anything fails, fix-in-place — DON'T commit the breakage and 'follow up'. Failures during this phase belong to this phase."

**What the contributor should actually do.** Three legitimate options:

1. **Fix the failure now.** Time spent diagnosing now is shorter than untangling phase-3-broken-but-phase-4-built-on-top.
2. **Mark phase 3 as `partial` or `deferred` in `notes.md` and STOP.** R8's notes template has a `Status: done | partial | deferred` field exactly for this:
   - `partial` — known follow-ups inside the same phase scope (rare; requires user agreement per R7 path-1).
   - `deferred` — phase stopped before phase-end check went green; branch parks here until the blocker is resolved. The next session reads this status first.
   Then `memory-keeping` records the deferral in `progress/STATE.md` per R12 step 5. The branch sits idle until the failure is diagnosed.
3. **Escalate to the user.** SKILL.md §"When to escalate" lists "A test fails for reasons not in the plan's §13 risks" as an explicit trigger. Bring the user in; don't push through.

**Why the rules look hostile but aren't.** Time pressure produces broken commits; broken commits produce un-bisectable history (per SKILL.md's own rationale); un-bisectable history makes upstream reviewers reject the patch (the other half of that rationale). The discipline is what makes the work upstream-able. R4 is short-term painful and long-term cheap.

### baseline

(Identical to iter-1.)

Committing a phase with a known test failure is a bad idea. Reasons:

1. **Bisectability.** If someone later runs `git bisect`, every "broken" commit pollutes the bisect history.
2. **Review.** A reviewer shouldn't have to mentally subtract "this commit is known broken".
3. **Cascading failure.** Hard to tell whether a new failure in phase 4 is from phase 4 or leftover phase 3.
4. **It compounds.** "I'll fix it after phase 4" turns into "after merge" turns into "in a follow-up PR" turns into "never".

The right move: fix the failure now, or stop, mark the phase as incomplete, and come back before starting phase 4. PostgreSQL patches in particular are reviewed by humans who expect every commit in a series to compile and pass tests.

The "I'll just commit it with a TODO" pattern is a classic warning sign of pressure-induced corner-cutting. The professional answer is: this debt isn't free.
