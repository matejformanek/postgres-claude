# Iter-2 answers — meta-commit-style (post-edits SKILL.md)

## E1 — knowledge/idioms commit

### with_skill (iter-2)

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

Prefix: `ft(corpus):` per the "If unsure" rule and the real-log
frequency reference now in §"Prefix vocabulary" (122/200 commits).
Title carries the `(N lines, N cites)` parenthetical per §"Body
rules". No `Plan:`/`Sites:` trailer — single-file diff, no plan.md.
Lowercase `Co-authored-by:` per the casing note added in iter-1 →
iter-2 edits.

### baseline — unchanged from iter-1

```
feat(knowledge): add lock-acquire-then-pin idiom doc

Adds a new 148-line idiom file documenting the acquire-then-pin
pattern across PG storage code, with 22 source citations.

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## E2 — phase-3 commit with Plan: + Sites:

### with_skill (iter-2)

Updated SKILL.md now uses plural `ft(skills):` consistently and the
Plan: trailer's canonical form is explicit. Multi-domain commit
covering 4 `.claude/skills/` + 2 `knowledge/scenarios/` files.

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

Order Plan → Sites → Co-authored-by; trailers blank-line separated
from body; lowercase Co-authored-by; plural `ft(skills):` matching
real-log convention (now also the SKILL.md example after Edit 2).

### baseline — unchanged from iter-1

```
feat(skills): finish phase 3 of server-side variables plan

Implements phase 3 (planner companions) for the server-side
variables work. Touches the new skill files and the scenarios
playbook.

Refs: planning/feature_server_side_vars/plan.md phase 3
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## E3 — prefix correctness probe

### with_skill (iter-2)

All three forms in the question are wrong for the meta repo:

1. **`feat(skills): add new lock-budget skill`** — wrong. The skill's
   §"Forbidden in meta-repo commits" explicitly bans Conventional
   Commits (`feat:` / `fix:`). Meta uses `ft(scope):` / `hf(scope):`
   / `docs(scope):` — vocabulary is project-specific by design,
   matching real `git log` here (123 ft / 6 hf / 12 docs in the
   recent 200 commits).

2. **`feat:` with no scope** — wrong twice over: (a) Conventional
   Commits is banned, and (b) scope is mandatory in this style
   ("we use `ft(scope):` / `hf(scope):` instead. The scope is
   mandatory.").

3. **`Add new lock-budget skill`** (no prefix) — wrong for THIS repo
   but correct for the upstream PG repo / `dev/`. The §"Side-by-side"
   block now makes this contrast concrete: the same conceptual change
   (document something) gets a bare imperative under
   `commit-message-style`, and a `ft(corpus):` prefix under
   `meta-commit-style`.

Canonical form:

```
ft(skills): add lock-budget skill

Body explaining what the skill captures and why it justifies a
new file rather than an extension to locking.

Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Specifically:
- `ft(skills):` plural — matches real log (23 occurrences; 0
  singular). The SKILL.md example now uses plural too.
- `Co-authored-by:` **lowercase** — matches the dominant form (45 vs
  11 uppercase in last 50 with a co-author trailer) and git's own
  canonicalization. Required as the global default.
- No emoji, no trailing period, no inline `(closes #N)` — squash
  appends `(#NN)`.
- No `Signed-off-by:` — not a DCO project.

### baseline — unchanged from iter-1

`feat(skills):` looks fine to me. Conventional Commits is widely
used. I'd pick that form with uppercase `Co-Authored-By: Claude`.
