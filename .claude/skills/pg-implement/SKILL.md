---
name: pg-implement
description: Execute a PostgreSQL `planning/<slug>/plan.md` phase-by-phase under upstream-grade discipline — Phase 3 of the PG planner suite. Per-phase commits, per-phase regress/iso/TAP runs, plan-linked commit messages, and a running notes log; enforces .claude/rules/pg-implement-discipline.md (R1-R12 — every commit references the plan slug + phase number; every code claim has a file:line cite; phase-end check must pass before the next phase starts). Use when the user says "/pg-implement <slug>", "implement the plan", "let's start implementing the X plan", "execute the planning/<slug>/plan.md", or has a finalized planning/<slug>/plan.md ready to execute. Skip for ad-hoc coding without a plan (no phase structure), non-PG implementation (app code, infra, scripts), the generic /implement flow (multi-project, doesn't enforce PG R1-R12 rules), and exploratory hacking where the plan is still being shaped (use pg-feature-plan instead).
when_to_load: Execute a planning/<slug>/plan.md phase-by-phase; enforce R1–R12 discipline rules; per-phase commits, tests, notes.md appends in dev/.
companion_skills:
  - pg-feature-plan
  - pg-feature-brainstorm
  - commit-message-style
  - meta-commit-style
  - build-and-run
  - testing
  - patch-submission
  - review-checklist
  - memory-keeping
---

# pg-implement — Phase 3 of the PG planner suite

The third stage. Brainstorm narrowed the design space; Plan made it
implementable; **Implement walks the plan phase-by-phase** while
enforcing the discipline rules.

The pairing:
- Phase 1 — `pg-feature-brainstorm` (sketch)
- Phase 2 — `pg-feature-plan` (heavy plan)
- **Phase 3 — `pg-implement`** (this skill, executes the plan)

## When to use vs the generic `/implement`

| Project | Use |
|---|---|
| Anything PG-related with a `planning/<slug>/plan.md` | **`/pg-implement`** |
| Generic project plan, not PG | Generic `/implement` |
| Ad-hoc PG coding, no plan | Neither — write a plan first via `/pg-plan` |

The PG variant exists because PG implementation has unusual
constraints the generic `/implement` doesn't enforce:

- Per-phase test runs against the dev cluster
- File:line citation discipline (knowledge corpus must stay accurate)
- Plan-linked commit messages (commits reference the plan + phase)
- Upstream-vs-meta commit-message-style split
- Catalog/catversion/WAL-format pre-flight before any touching edit
- `/pg-restart` cadence after backend code changes

## Inputs

- **Slug** (required): the planning directory under `planning/<slug>/`.
  Examples in this repo: `sp2-pgstr-maxalloc`, `cb1-pgcrypto-bomb`,
  `sp7-tablefunc-quoting`. The `dev/` branch mirrors the slug
  (e.g. `feature_sp2_pgstr_maxalloc`, `feature_server_side_vars`).
- Must contain `plan.md` produced by `pg-feature-plan`.
- May contain `brainstorm.md` (Phase 1 sketch); read for context, not
  for procedure.
- May contain `notes.md` (running log; appended to during this run).

## Output

- Code changes inside `dev/` on a feature branch (NOT in
  `postgres-claude/`'s `knowledge/`).
- `planning/<slug>/notes.md` — one section per phase, appended as we
  go: what was edited, what tests ran, what surprised us, what's
  deferred.
- Per-phase commits with the plan-linked message format (§5 below).
- Optionally at the end: a draft commit / patch series under `dev/`
  ready for `patch-submission`.

## Strict rules — see `.claude/rules/pg-implement-discipline.md`

This skill is the procedure. The rules file is the constitution.
Read both. Where they disagree, the rules win. The non-negotiables:

1. **One phase at a time.** No interleaving phases. Each phase is
   self-contained per the plan's "Phase-end check".
2. **Verify before edit (R2).** Spot-check 3-5 file:line citations from
   the plan against current source before phase 1. **Drift signals:**
   citations off by more than ~20 lines, or naming a since-removed
   symbol. If drift > 10% of the spot-checked sample, STOP — re-run
   `/pg-plan` to refresh; do not push through with a stale plan.
3. **Phase-end check must pass** before the next phase starts. Don't
   carry breakage forward.
4. **Per-phase commit.** Each phase ends with a commit using the plan-
   linked message format. No phase ends uncommitted.
5. **Cite or don't claim** applies to commit messages too — any
   "fixes" / "addresses" claim must point to a specific file:line or
   plan-section.
6. **No scope creep (R7).** If a phase reveals a needed change outside
   the plan's §3 file table, STOP and pick from R7's three paths
   (small+coupled → update plan + `Sites:` trailer; separate concern →
   defer to follow-up + record in `notes.md`; invalidates the phase
   boundary → escalate for re-plan). Never silently expand scope.

### Why per-phase = per-commit + per-test

Two operational reasons every phase ends with a green-tested, plan-
linked commit (not "WIP" or "TODO"):

1. **Bisectability.** `git bisect` across a multi-phase patch series
   is only useful if every commit individually builds and passes the
   declared phase-end check. A broken commit in the middle of the
   series poisons bisect for the lifetime of this code.
2. **Per-commit reviewability.** When the series eventually goes to
   pgsql-hackers via `format-patch`, reviewers read commits one at a
   time. Upstream PG convention is that **each commit in a posted
   series compiles and passes tests on its own** — a known-broken
   "WIP" commit, even one tagged TODO, is grounds for the patch
   being bounced before review starts.

This is why R3 (no interleaving), R4 (phase-end check before commit),
and the anti-pattern list (no WIP commits, no `--amend` across
phases) act as one rule, not three.

### Forbidden patterns (mirrors rules §Anti-patterns)

- **"WIP" commits.** Every commit in `dev/` is a complete phase. No
  `wip: more of phase 3`.
- **`--amend` to fix a previous phase's commit.** Use a NEW commit
  with a `Fixes: <sha>` trailer if you genuinely need to correct.
- **Committing without a `Plan:` trailer in `dev/`.** If you're
  committing in `dev/`, you're implementing a plan — name it.
- **Cherry-picking individual phases.** All phases or none.
- **Mixing meta-repo + `dev/` writes in one bash invocation** (R10).

## Method

For each phase in `planning/<slug>/plan.md` §8 "Phased implementation":

### Pre-phase (5 min)

1. Read the phase's "Files this phase touches" + "5-10 concrete edits"
   + "Phase-end check".
2. Spot-check the file:line citations against current source. Grep for
   any function name or symbol cited; verify line numbers within ±20.
   If drift, escalate to user before continuing.
3. Re-read the relevant subsystem doc (`knowledge/subsystems/X.md`) and
   the per-file docs for files being edited. Note any invariants
   (`INV-*` tags) that the phase touches.
4. Confirm the dev cluster is stopped if a postmaster restart will be
   needed (catalog edits, GUC additions). Otherwise leave it running
   for fast feedback.

### Edit (the main work)

5. Make the 5-10 edits per the phase plan. Use `Edit` (not Write)
   wherever possible — preserves surrounding context and reviews
   cleanly.
6. After each edit, run a quick build if the file is in `src/backend`:
   `cd dev/build-debug && ninja install 2>&1 | tail -5`. Catch
   compile errors immediately, not at phase end.
7. Track every edit in `planning/<slug>/notes.md` as you go:
   - File + line range + one-sentence what.
   - Anything that surprised you (e.g. "comment at line 234 mentioned
     a constraint I had to honor").
   - Anything that drifted from the plan (e.g. "plan said 5 edits;
     I needed 6 because of helper X").

### Phase-end check

8. Run the test scope named in the plan's phase-end check:
   - Most phases: `meson test --no-rebuild regress/regress`.
   - Catalog/WAL phases: regress + `meson test --no-rebuild --suite
     isolation`.
   - Replication phases: above + the relevant TAP test under
     `meson test --no-rebuild --suite recovery`.
9. If anything fails, fix-in-place — DON'T commit the breakage and
   "follow up". Failures during this phase belong to this phase.
10. Once green, run `git -C dev status` and verify the changed files
    match the plan's §3 file table for this phase. Flag any extras to
    the user before committing.

### Per-phase commit

11. Stage the phase's files: `git -C dev add <files>`.
12. Compose the commit message per the format below.
13. Use `commit-message-style` (upstream PG style — no Co-Authored-By,
    imperative, wrapped at 76 cols) since this commit lives in `dev/`
    and may eventually be format-patched upstream.

### Plan-linked commit message format

```
<one-line imperative title, max ~72 cols, no prefix>

<wrapped paragraph body, explaining the WHY of this phase>

Plan: planning/<slug>/plan.md (phase <N>: <phase title>)
Sites: <file:line>, <file:line>, ...
```

- Title is for the phase, NOT for the whole feature.
- Body is one or two paragraphs, plain prose, no bullets.
- `Plan:` trailer is **required** and points to the plan + phase.
- `Sites:` trailer lists the principal sites touched (3-5 max; don't
  enumerate every line).
- No `Co-Authored-By` (this is upstream style).
- No emoji, no conventional-commits prefix, no ticket numbers.

### Phase-end log

14. Append to `planning/<slug>/notes.md`:

    ```markdown
    ## Phase <N> — <title> — <date> <time>

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

    **Status field values (R8):**
    - `done` — phase-end check green, commit landed.
    - `partial` — phase ended with known follow-ups inside the same
      phase scope (rare; requires user agreement per R7 path-1).
    - `deferred` — phase stopped before its phase-end check could run
      green; branch parks here until the blocker is resolved. The
      next session reads this status first.

15. Tell the user the phase is done, name the next phase, ask whether
    to continue immediately or pause. Some phases naturally end the
    session.

## End-of-implementation (after all phases done)

16. Final `meson test --no-rebuild` (full suite). Document any
    pre-existing flakes (e.g. macOS `recovery/040_*` etc.).
17. Run `git -C dev log --oneline <base>..HEAD` and verify N commits
    for N phases, each with a `Plan:` trailer.
18. If destined upstream: hand off to `patch-submission` skill.
19. If staying local: tell the user, leave the branch, append a
    final summary to `notes.md`.
20. End-of-session: invoke `memory-keeping` to update `progress/STATE.md`
    with the planning slug + status (done / deferred / abandoned).

## Boundaries vs other skills

- **`pg-feature-plan`** (Phase 2): the upstream. If scope shifts, escalate
  back — don't reshape the plan mid-implementation.
- **`commit-message-style`** (upstream PG style): used for every per-phase
  commit (since these may go upstream).
- **`meta-commit-style`** (meta-repo style): NOT used here. Reserved for
  commits inside `postgres-claude/`. If implementation reveals a knowledge
  corpus gap, fix it in a SEPARATE meta-repo commit using that style.
- **`patch-submission`**: takes over at the end for upstream-bound work.
- **`review-checklist`**: pre-submission gate. Run at the end before
  format-patching.
- **`memory-keeping`**: end-of-session bookkeeping.
- **`testing`**: when adding test cases mid-phase, consult for the right
  flavor (regress vs isolation vs TAP).
- **`build-and-run`** + **`/pg-restart`** + **`/pg-test`** + **`/pg-psql`**:
  the dev-loop commands.

## When to escalate to the user

- Plan drift > 10% (file:line citations significantly stale).
- A phase reveals a needed change outside §3 file table (scope creep).
- A test fails for reasons not in the plan's §13 risks.
- Catalog or WAL format change wasn't anticipated by the plan.
- The change touches an invariant tagged in a subsystem doc.

In every escalation: stop, propose the resolution path (update plan,
defer to follow-up, abandon phase), ask. Don't push through.

## Style

- Be terse in `notes.md`. It's a working log, not a write-up.
- Be specific in commit messages (R6). "fix bug" is forbidden; "set
  `dropPin = false` for non-MVCC scans (plan phase 2, site
  `nbtree.c:421`)" is right. Any "addresses" / "fixes" / "implements"
  claim must point to a file:line in `source/` (for plan-cited sites)
  or a specific plan section (`§4 Catalog impact`, etc.).
- Cite the plan from the commit; cite the corpus from the plan; cite
  source from the corpus. The full chain stays linked.

## Where the artifacts live

- Code: `dev/` on a feature branch (e.g. `feature_server_side_vars`).
- Working log: `planning/<slug>/notes.md` (in `postgres-claude/`).
- Plan-linked commits: the `Plan:` trailer is the link from commit
  back to plan.

## Cross-references

- `.claude/rules/pg-implement-discipline.md` — **the binding constitution.** This skill is the procedure; the rules are the invariants. R1–R12 win wherever they disagree with this skill.
- `.claude/skills/pg-feature-plan/SKILL.md` — Phase 2 upstream. If scope shifts, escalate back; don't reshape the plan mid-implementation.
- `.claude/skills/pg-feature-brainstorm/SKILL.md` — Phase 1 read for context, not procedure.
- `.claude/skills/commit-message-style/SKILL.md` — per-phase commit format (upstream PG style; no `Co-Authored-By` because these commits may go upstream).
- `.claude/skills/meta-commit-style/SKILL.md` — used for the *separate* meta-repo commit if implementation surfaces a corpus gap (R10 two-repo separation).
- `.claude/skills/build-and-run/SKILL.md` — dev-loop fundamentals (`ninja install`, `/pg-restart`, build profiles).
- `.claude/skills/testing/SKILL.md` — pick the right test flavor for each phase's phase-end check.
- `.claude/skills/patch-submission/SKILL.md` — invoked at end-of-implementation if upstream-bound.
- `.claude/skills/review-checklist/SKILL.md` — pre-submission gate (R12).
- `.claude/skills/memory-keeping/SKILL.md` — end-of-implementation STATE.md update (R12 invokes this explicitly).
- `.claude/commands/pg-implement.md` — slash-command wrapper.
