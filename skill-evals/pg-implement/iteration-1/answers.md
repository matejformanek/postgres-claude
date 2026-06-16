# Iteration 1 — answers

Two answers per eval: `with_skill` (assumes SKILL.md + `pg-implement-discipline.md` loaded) and `baseline` (general PG-internals + Claude Code workflow knowledge only — NO peek at SKILL.md).

---

## Eval 1 — Walk through phase 2 of sp2-pgstr-maxalloc

### with_skill

Phase 2 implementation against `planning/sp2-pgstr-maxalloc/plan.md`. The procedure lives in `.claude/skills/pg-implement/SKILL.md` §Method; the binding invariants are in `.claude/rules/pg-implement-discipline.md` (R1–R12).

**Pre-phase (5 min) — SKILL.md §Pre-phase, R2:**

1. Open `planning/sp2-pgstr-maxalloc/plan.md` and read the phase-2 sub-section: "Files this phase touches", "5–10 concrete edits", and "Phase-end check".
2. Spot-check 3–5 of the file:line citations from phase 2 against the current `source/` tree. Grep for each function/symbol cited and confirm line numbers within ±20. R2 is binding here: if drift > 10% (citations off by more than ~20 lines or naming a since-removed symbol), STOP — escalate to the user and re-run `/pg-plan` instead of pushing through with a stale plan.
3. Re-read the relevant `knowledge/subsystems/X.md` doc and any per-file docs for files in this phase. Note any `INV-*` invariants the phase touches.
4. Decide on cluster state: if phase 2 edits a catalog or adds a GUC, `/pg-stop` first because the postmaster will need a fresh start. Otherwise keep it running for fast feedback. (SKILL.md §Pre-phase step 4.)

**Edit (the main work) — SKILL.md §Edit:**

5. Make the 5–10 edits the plan names. Prefer `Edit` over `Write` so the surrounding context is preserved and the diff reviews cleanly.
6. After each edit in `src/backend`, run `cd dev/build-debug && ninja install 2>&1 | tail -5` to catch compile errors immediately — not at phase end.
7. Append to `planning/sp2-pgstr-maxalloc/notes.md` as you go: file + line range + one-sentence "what", plus any surprises (e.g. a comment that imposed an unexpected constraint) and any drift from the plan (e.g. "plan said 5 edits; needed 6 because of helper X"). This is R8: the per-phase notes log is mandatory.

**Phase-end check — SKILL.md §Phase-end check, R4:**

8. Run exactly the test scope named in the plan's phase-2 phase-end check. The default suites:
   - Most phases: `meson test --no-rebuild regress/regress`.
   - Catalog/WAL phases: regress + `meson test --no-rebuild --suite isolation`.
   - Replication phases: above + relevant TAP under `meson test --no-rebuild --suite recovery`.
9. R4: phase-end check must pass before commit. Failures during this phase belong to this phase — fix-in-place, do NOT commit broken state and "follow up".
10. Once green, run `git -C dev status` and verify the changed files match the plan's §3 file table for this phase. Flag any extras to the user before committing (this is the R7 scope-creep gate).

**Per-phase commit — SKILL.md §Per-phase commit, R5:**

11. Stage the phase's files: `git -C dev add <files>`.
12. Compose the commit using the upstream PG style via the `commit-message-style` skill: no `Co-Authored-By` (these commits may go upstream via `format-patch`); imperative title scoped to **the phase**, not the whole feature; wrap body near 76 cols.
13. The required trailers per R5 / SKILL.md §"Plan-linked commit message format":
    - `Plan: planning/sp2-pgstr-maxalloc/plan.md (phase 2: <phase title>)` — **required**, this is the link back to the plan.
    - `Sites: <file:line>, <file:line>, ...` when the diff spans more than one non-obvious file (3–5 max; don't enumerate every line).
    - No emoji, no conventional-commits prefix, no ticket numbers, no Signed-off-by.
    - R6: any "fixes" / "addresses" / "implements" claim in the body must point to a file:line in `source/` or a specific plan section (e.g. `§4 Catalog impact`). Vague language like "fix the bug" is forbidden.

**Phase-end log — SKILL.md §Phase-end log, R8:**

14. Append a section to `planning/sp2-pgstr-maxalloc/notes.md` using the template:

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

15. Tell the user phase 2 is done, name phase 3, and ask whether to continue immediately or pause. Per R3, no interleaving — finish phase 2 (including the commit + notes append) before opening phase 3.

**Anti-patterns explicitly forbidden** (from `pg-implement-discipline.md` "Anti-patterns"):
- No `wip: more of phase 2` commits — every commit in `dev/` is a complete phase.
- No `--amend` to fix a previous phase's commit; use a NEW commit with a `Fixes: <sha>` trailer.
- No committing without a `Plan:` trailer.
- No mixing meta-repo + `dev/` writes in one bash invocation (R10 two-repo separation).

### baseline

To implement phase 2 of the plan, I'd start by opening the plan file and re-reading the phase-2 section so I know what's in scope. Then:

1. Make sure phase 1 is committed cleanly and tests still pass on that branch.
2. Read through the file:line references in phase 2 and sanity-check them — code drifts.
3. Make the edits one by one. After each meaningful change, run `ninja` (or `make`) in the build directory to make sure the tree still compiles. Catching compile errors early is much cheaper than catching them at the end.
4. Once edits are done, run the regression test suite — `meson test` or `make check` — to make sure nothing broke. If there are isolation or TAP tests relevant to this area, run those too.
5. If tests fail, fix them before committing. Don't ship broken phases.
6. Commit. Use a reasonable PostgreSQL-style commit message: imperative subject line, wrapped body explaining the why, no emoji. Mention the phase in the message so reviewers can correlate with the plan.
7. Update any notes / changelog you're keeping for this work.
8. Move on to phase 3 only after phase 2 is fully done.

A few standard cautions: don't mix unrelated changes into one phase; if you discover the plan was wrong about a file, stop and talk to the planner rather than silently expanding scope; and if the phase involves catalog changes you'll need to restart the postmaster and probably reinitdb the dev cluster.

---

## Eval 2 — Mid-phase need to touch a file outside §3

### with_skill

This is the textbook scope-creep case that **R7** in `.claude/rules/pg-implement-discipline.md` exists for. Procedure:

**Step 1 — STOP editing.** R7 is unambiguous: "If a phase reveals a needed change outside the plan's §3 'Files that change' table, STOP." Do NOT silently add `visibilitymap.c` to the diff and commit it. Silent scope expansion is one of the anti-patterns the rules file forbids.

**Step 2 — Classify the new site.** R7 enumerates three resolution paths in order of preference:

1. **Small + tightly coupled to the in-flight phase** → update the plan (add `visibilitymap.c` to §3 with a one-line "added during phase 3 — see notes.md") AND add it to the commit's `Sites:` trailer. Continue the phase. This is the cheapest path and is appropriate when the new site is a 1–5 line edit that's intrinsic to making the phase compile or pass tests.
2. **Separate concern** → defer to a follow-up patch. Note the deferral in `planning/<slug>/notes.md` under "Surprises / drift" per R8's template. Do NOT touch `visibilitymap.c` in this phase; do NOT carry stash. Finish phase 3 as planned.
3. **The new site invalidates the phase boundary** (i.e. phase 3 doesn't actually make sense without `visibilitymap.c` work that's substantial) → escalate to the user for a re-plan. The phase as scoped is wrong; pushing through corrupts the plan structure.

**Step 3 — Pick a path, but only with the user's go-ahead if it's not (1).** SKILL.md §"When to escalate to the user" lists "A phase reveals a needed change outside §3 file table (scope creep)" as one of the explicit escalation triggers. Tell the user what you found, propose which of the three paths fits, and wait. Do not push through.

**Step 4 — Document.** Regardless of path chosen, the `notes.md` append for phase 3 (per R8) must include the surprise. Required entries:
- "Surprises / drift" section: "phase 3 needed an edit in `visibilitymap.c:NNN` that wasn't in §3. Resolved by <path 1 / 2 / 3>."
- If path (1) was taken: the plan file gets a `Sites:` row added and the commit's `Sites:` trailer lists `visibilitymap.c:NNN`.
- If path (2): the new site is named under "What this phase did NOT do" with a pointer to the follow-up.

**Step 5 — R9 citation chain still has to hold.** Whatever path you take, the chain stays linked: commit → `Plan:` trailer → plan file → corpus cites → `source/<path>:<line>`. If the plan now references a site not previously in the corpus, that's a corpus gap — fix it in a **separate** meta-repo commit (R10: two-repo separation; the `dev/` patch is one commit, the corpus update is a different commit in `postgres-claude/` using `meta-commit-style`).

**Why the rule exists.** Silent scope expansion is how patches grow from reviewable to un-reviewable. The phase boundary is what makes per-phase review possible. R7 + R10 together protect the reviewer's ability to read each commit on its own.

### baseline

If a phase needs to touch a file the plan didn't anticipate, that's a sign the plan was incomplete. A few reasonable options:

- If it's a small, obviously-needed change (say, a helper that has to be updated to accept a new parameter), I'd just include it in the phase and call it out in the commit message. The reviewer will see the diff regardless.
- If it's bigger, I'd stop, ping the user, and ask whether to update the plan or punt the new file to a separate follow-up patch.
- I would **not** push through silently. Surprises in a code review are bad, and the planner needs to know the plan is drifting so future plans are sharper.
- I'd note this in whatever working log I'm keeping for the implementation.

Practically: the commit message should mention the unplanned site, and if I were posting upstream I'd probably split the change into two commits — one for the planned phase, one for the visibilitymap touch — to keep each commit focused.

---

## Eval 3 — Why can't we commit phase 3 with a regress failure as TODO?

### with_skill

The proposal violates several non-negotiable rules in `.claude/rules/pg-implement-discipline.md`. In order of immediacy:

**R4 — Phase-end check must pass before commit.** Verbatim: "The plan's 'Phase-end check' for phase N (regress / iso / TAP scope as specified) must run green. Failures are this phase's problem; don't commit broken state and 'follow up'." A red regression is a phase-end-check failure, full stop. R4 alone makes the proposal forbidden.

**R3 — One phase at a time, no interleaving.** "Finish phase N (including the phase-end check + the commit) before opening phase N+1." If phase 3's tests are red, phase 3 is NOT finished. Starting phase 4 on top of a red phase 3 violates R3.

**R5 — Per-phase commit must be plan-linked AND in upstream PG style.** Upstream PG style does not have a "TODO" or "WIP" idiom — commits in `dev/` may end up being `format-patch`-ed to pgsql-hackers, and a broken commit in the series is a non-starter for upstream review. The `Plan:` trailer claim "phase 3" implies "phase 3 done"; committing red contradicts that.

**Anti-pattern list — "WIP commits forbidden.** `pg-implement-discipline.md` "Anti-patterns" section says explicitly: "**'WIP' commits.** Every commit in `dev/` is a complete phase. No 'wip: more of phase 3'." A TODO-tagged broken commit is a WIP commit by another name.

**R6 — Vague claims forbidden in commit messages.** "fix the bug" is the example the rule cites as forbidden. A commit message containing "TODO: regress failure to fix later" is the same anti-pattern — vague language standing in for a specific cite.

**R12 — End-of-implementation gate explicitly requires all phases green.** Step 2 of R12 says `git -C dev log --oneline <base>..HEAD` must show N commits for N phases, each with a `Plan:` trailer, AND step 1 requires full `meson test --no-rebuild` green. Carrying a broken phase forward means R12 cannot fire at the end either — the broken commit is now embedded in the series and the only way out is a `Fixes: <sha>` follow-up commit, which clutters history.

**SKILL.md §Phase-end check, step 9 (matches R4).** "If anything fails, fix-in-place — DON'T commit the breakage and 'follow up'. Failures during this phase belong to this phase."

**What the contributor should actually do.** Three legitimate options:

1. **Fix the failure now.** If it's tractable, the time spent diagnosing the failure now is shorter than the time spent later untangling phase-3-broken-but-phase-4-built-on-top.
2. **Mark phase 3 as `partial` or `deferred` in `notes.md` and STOP.** R8's notes template has a `Status: done | partial | deferred` field exactly for this. Then `memory-keeping` records the deferral in `progress/STATE.md` per R12 step 5. The branch sits idle until the failure is diagnosed.
3. **Escalate to the user.** SKILL.md §"When to escalate" lists "A test fails for reasons not in the plan's §13 risks" as a trigger. Bring the user in; don't push through.

**Why the rules look hostile but aren't.** Time pressure produces broken commits; broken commits produce un-bisectable history; un-bisectable history makes upstream reviewers reject the patch. The discipline is what makes the work upstream-able. R4 is short-term painful and long-term cheap.

### baseline

Committing a phase with a known test failure is a bad idea. Reasons:

1. **Bisectability.** If someone later runs `git bisect` to track down a regression, every "broken" commit pollutes the bisect history.
2. **Review.** A reviewer reading the patch series shouldn't have to mentally subtract "the phase 3 commit is known broken; ignore for now." That's how real bugs slip past review.
3. **Cascading failure.** If phase 4 builds on phase 3, you can't tell whether a new failure in phase 4 is from phase 4 or leftover from phase 3.
4. **It compounds.** "I'll fix it after phase 4" turns into "I'll fix it before merge" turns into "I'll fix it in a follow-up PR" turns into "this never gets fixed."

The right move: fix the failure now, or stop, mark the phase as incomplete in whatever tracking system you're using, and come back to it before starting phase 4. PostgreSQL patches in particular are reviewed by humans who expect every commit in a series to compile and pass tests — that's a near-universal expectation in OSS projects with a high quality bar.

The "I'll just commit it with a TODO" pattern is one of the classic warning signs that someone is being pressured into corner-cutting. The professional answer is: this kind of debt isn't free, and the cost of paying it down later is reliably higher than fixing it now.
