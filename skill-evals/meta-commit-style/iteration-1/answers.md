# Iter-1 answers — meta-commit-style

## E1 — knowledge/idioms commit

### with_skill

Prefix: `ft(corpus):` — the skill names this exact mapping for any `knowledge/*` write (§"Prefix vocabulary"). The doc lives under `knowledge/idioms/`, so it counts.

```
ft(corpus): synthesize lock-acquire-then-pin idiom (148 lines, 22 cites)

Distill the lock-then-pin sequencing pattern from src/backend/storage/lmgr/
into knowledge/idioms/lock-acquire-then-pin.md. Covers the canonical
acquire/pin/release/unpin ordering rule that surfaces across heapam,
btree, and the buffer manager, plus the two places we observed it
violated in third-party extensions (Multigres lesson). 22 file:line
cites verified at HEAD.

Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Convention notes per skill:
- Body explains the *why*; the diff shows the *what*.
- Include line + cite counts in title parenthetical for new corpus syntheses (per §"Body rules" — keeps STATE.md in sync).
- No Plan: trailer (no `planning/<slug>/plan.md`).
- No Sites: trailer needed (single-file write — diff makes the site obvious).
- Wrap body ~76 cols.
- Trailers separated from body by a blank line.
- Lowercase `Co-authored-by:` — that's the exact identity required by global default.

### baseline (no SKILL.md)

Looking at general open-source commit conventions, I'd probably write:

```
feat(knowledge): add lock-acquire-then-pin idiom doc

Adds a new 148-line idiom file documenting the acquire-then-pin
pattern across PG storage code, with 22 source citations.

Co-Authored-By: Claude <noreply@anthropic.com>
```

I'd use Conventional Commits since that's the dominant convention I've seen across most repos, and use uppercase `Co-Authored-By: Claude` since that's what GitHub generates by default.

---

## E2 — phase-3 commit with Plan: + Sites:

### with_skill

Per §"Trailers" the order is `Plan:` → `Sites:` → optional `Session:` → `Co-authored-by:` (last). Plan: format is exact: `planning/<slug>/plan.md (phase <N>: <title>)`. Sites: lists non-obvious files comma-separated.

Prefix choice: this is multi-domain (4 files in `.claude/skills/`, 2 in `knowledge/scenarios/`). The skill's "if unsure" rule says `ft(skills):` for any `.claude/skills/*` write — and skills dominates the diff. Use plural `ft(skills):` to match the real log (122 ft(corpus) / 23 ft(skills) in recent 200 commits).

```
ft(skills): phase 3 server-side-vars planner companions

Phase 3 of the server-side-variables plan: add two new skills
(server-side-var-design, server-side-var-impl) and refresh the
scenarios playbook that drives the plan's §3 file checklist. The
scenarios edit pins the planner-suite contract — when a scenario
exists, /pg-feature-plan pins the §3 table from it instead of
re-deriving from source.

Body explains why: phase 3 closes the loop between the brainstorm
(captured as a skill pair) and the planner (consuming via
scenarios/_index.md).

Plan: planning/feature_server_side_vars/plan.md (phase 3: planner companions)
Sites: .claude/skills/server-side-var-design/SKILL.md,
       .claude/skills/server-side-var-impl/SKILL.md,
       knowledge/scenarios/add-server-side-var.md,
       knowledge/scenarios/_index.md
Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Note: the skill's example uses `ft(skill):` (singular) but the real log uses plural `ft(skills):` (23 occurrences) — picking plural to match the established log. (This is a small drift in the skill — see proposed edits.)

### baseline

```
feat(skills): finish phase 3 of server-side variables plan

Implements phase 3 (planner companions) for the server-side
variables work. Touches the new skill files and the scenarios
playbook.

Refs: planning/feature_server_side_vars/plan.md phase 3
Co-Authored-By: Claude <noreply@anthropic.com>
```

I'd use Conventional Commits `feat(skills):`, and a free-form `Refs:` line instead of the project's `Plan:` trailer format. I wouldn't know to list each touched file under a `Sites:` trailer. I'd use uppercase `Co-Authored-By:`.

---

## E3 — prefix correctness probe

### with_skill

None of those three forms are right for the meta repo. Specifically:

1. **`feat(skills): add new lock-budget skill`** — wrong. The skill's §"Forbidden in meta-repo commits" explicitly bans `feat:` / `fix:` Conventional Commits flavoring. The meta repo uses `ft(scope):` / `hf(scope):` / `docs(scope):` instead. The vocabulary is project-specific by design — `ft` reads as "feature", `hf` as "hotfix", matching what's in `git log` here.

2. **`feat: add new lock-budget skill`** — also wrong, twice over: (a) `feat:` is forbidden as above, and (b) bare prefix with no scope is forbidden — the scope is mandatory in this style (see §"Forbidden": "we use `ft(scope):` / `hf(scope):` instead. The scope is mandatory.")

3. **`Add new lock-budget skill`** — wrong for *this* repo, but this IS correct for the upstream PG repo (`commit-message-style` skill). The contrast table at the top of the meta skill makes this distinction explicit: upstream PG = bare imperative, no prefix; meta repo = `ft(scope):` prefix.

Canonical form for the meta repo:

```
ft(skills): add lock-budget skill

Body explaining what the skill captures and why it justifies a
new file rather than an extension to locking.

Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Specifically:
- Prefix `ft(skills):` (plural, matching real log).
- `Co-authored-by:` (lowercase) trailer is required — the global default.
- No emoji, no trailing period on title, no inline ticket numbers (squash-merge appends `(#NN)` on its own).
- No `Signed-off-by:` — that's Linux kernel DCO style, not used here.

### baseline

`feat(skills):` actually looks fine to me — Conventional Commits is widely-used, the scope is filled in, the title is imperative. Bare-prefix `feat:` is also valid Conventional Commits (scope is technically optional in the spec). And a bare imperative title `Add new lock-budget skill` is the classic Linux kernel style — also valid.

If I had to pick one I'd go with `feat(skills): add new lock-budget skill` since Conventional Commits is the most common modern convention. Co-Authored-By: Claude trailer if claude helped.
