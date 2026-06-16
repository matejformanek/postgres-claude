---
name: meta-commit-style
description: Write a commit message inside the postgres-claude META repo (knowledge corpus, skill / agent / command edits, planning artifacts, session logs, infra changes) — covers the meta style: `ft(scope):` / `hf(scope):` / `docs(scope):` prefix, a wrapped body, an optional `Plan:` trailer, and the global `Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` footer (lowercase trailer per real log — 45 lowercase vs 11 uppercase in last 50 commits). Distinct from the upstream PG commit-message-style (which forbids Co-authored-by and uses bare-imperative titles). Use whenever drafting a commit inside `postgres-claude/` (the meta repo) — corpus PR, skill rewrite, session log, planning doc, cloud-routine recipe, etc. Skip for upstream PG patches in `dev/` (use commit-message-style), Conventional Commits style (feat: / fix: / chore: across most non-PG projects), Linux-kernel Signed-off-by commits, Angular / Vue / React commit style, and the generic git-commit message question on any other project.
when_to_load: Draft a commit message inside postgres-claude (corpus, skill, planning, sessions, infra); a worktree branch off this repo about to land via PR.
companion_skills:
  - commit-message-style
  - memory-keeping
  - pg-implement
  - pg-feature-plan
  - pg-feature-brainstorm
---

# meta-commit-style — postgres-claude commit messages

The postgres-claude meta repo's commit style. **Distinct from the
upstream PG style** in `commit-message-style`:

| Aspect | Upstream PG (`commit-message-style`) | Meta repo (this skill) |
|---|---|---|
| Title prefix | None (bare imperative) | `ft(scope):` / `hf(scope):` / `docs(scope):` / `[cloud:<routine>]` |
| `Co-authored-by` | **Forbidden** | **Required** (global default; lowercase form — 45/56 in real log) |
| `Plan:` trailer | N/A | Optional, when implementing a planned feature |
| `Sites:` trailer | N/A | Optional, when changes span multiple files |
| Wrap width | ~76 cols | ~76 cols (same) |
| Voice | Imperative | Imperative (same) |
| Emoji | Forbidden | Forbidden (same) |
| Ticket numbers | Forbidden | Forbidden (PR # via `(#NN)` from squash-merge is fine) |
| Bullet lists in body | Forbidden | Tolerated for multi-item commits |

## Side-by-side: same change, two styles

Same conceptual change ("document the lock-then-pin acquire-order
invariant"), two different homes — and two different commit-message
shapes:

**`dev/` patch (uses `commit-message-style`, upstream PG):**

```
Document lock acquire-before-pin invariant

The lock-then-pin sequence is not stated in lmgr.h; spell it out
here so extension authors do not regress it.

Author: Some One <some@one.example>
Reviewed-by: Other Person <other@example.com>
Discussion: https://postgr.es/m/CAB7nPq...
```

**postgres-claude meta repo (uses this skill):**

```
ft(corpus): synthesize lock-acquire-then-pin idiom (148 lines, 22 cites)

Distill the lock-then-pin sequencing pattern from
src/backend/storage/lmgr/ into knowledge/idioms/lock-acquire-then-pin.md.
22 file:line cites verified at HEAD.

Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Same intent, two homes, two trailer regimes. R10 ("two-repo
separation") in `.claude/rules/pg-implement-discipline.md` is what
makes this split necessary.

## When to use

Anywhere inside `postgres-claude/` (the meta repo). Examples:
- New / updated `knowledge/subsystems/X.md` doc.
- New / updated `.claude/skills/Y/SKILL.md`.
- New `.claude/commands/Z.md` slash command.
- New `.claude/agents/W.md` subagent.
- New `planning/<slug>/{brainstorm,plan,notes}.md`.
- New `sessions/<date>-<topic>.md` log.
- Updates to `progress/STATE.md` / `coverage.md` / `files-examined.md`.
- Infra changes (`.claude/settings.json`, `.claude/cloud/*.md` recipes, etc.).

## When NOT to use

- Commits inside `dev/` (the mutable PG clone) — use
  `commit-message-style` (upstream PG style; no `Co-authored-by`).
- Generic non-PG project commits.

## Format

```
<prefix>(<scope>): <imperative title, max ~72 cols>

<one or two paragraphs explaining the WHY, wrapped at ~76 cols. The
WHAT belongs in the diff. Mention what surprised you, what tradeoffs
you accepted, what you considered and rejected.>

[Plan: planning/<slug>/plan.md (phase <N>: <title>)]
[Sites: <file:line>, <file:line>, ...]

Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

> **Note on `Co-authored-by:` casing.** Use **lowercase**
> `Co-authored-by:` (matches git's own canonicalization and the
> dominant form in this repo's log — 45 lowercase vs 11 GitHub-style
> uppercase `Co-Authored-By:` in the most-recent 50 commits with a
> co-author trailer). GitHub renders both identically, but lowercase
> is the house form here.

### Prefix vocabulary

Match what's already in `git log` of this repo. The canonical set:

| Prefix | Meaning | Example |
|---|---|---|
| `ft(corpus):` | new knowledge doc (subsystem/idiom/data-structure/files) | `ft(corpus): synthesize tcop spine (770 lines, 39 cites)` |
| `ft(dev):` | new dev-loop infra (commands, dev-cluster tooling) | `ft(dev): MCP + psql skill + ASan profile` |
| `ft(skills):` | new or revised skill (plural — matches real log, 23 occurrences in last 200; 0 singular) | `ft(skills): add pg-implement skill for plan execution` |
| `ft(meta):` | repo-wide metadata (README, CONTRIBUTING, llms.txt, .github/) | `ft(meta): discoverability quick wins` (anchor: `82ebf2e`) |
| `ft(cloud):` | new cloud routine or routine infra | `ft(cloud): repoint pg-user-question-harvester to pgsql mailing-list archives` |
| `ft(plan):` | new planning artifact (brainstorm or plan) | `ft(plan): brainstorm server-side variables` |
| `hf(<scope>):` | hotfix for an existing thing in <scope> | `hf(corpus): refresh bufferdesc-state for PG18 atomic state-word` |
| `docs(<scope>):` | docs-only updates (STATE.md narrative, cloud-routine logs, community digests) | `docs(state): prepend 2026-06-16 entry` (anchor: `b707ab2`); also `docs(cloud):` (8x), `docs(community):` (2x), `docs(queue):`, `docs(progress):` |
| `[cloud:<routine>]` | auto-generated by a cloud routine (NOT manual) | `[cloud:pg-evening-merger] merge 8 cloud/* PRs` |

If unsure: `ft(corpus):` for any `knowledge/*` write; `ft(skills):`
(plural) for any `.claude/skills/*` write; `ft(meta):` for repo-wide
metadata; `ft(dev):` for any other infra.

**Real-log frequency reference** (last 200 commits): `ft(corpus):` 122,
`ft(skills):` 23, `docs(cloud):` 8, `hf(corpus):` 6, `ft(cloud):` 5,
`ft(meta):` 2, `docs(community):` 2; plus `[cloud:<routine>]` form
for routine-generated commits. Match the established vocabulary;
don't invent new scopes without precedent.

### Title rules

- Imperative present-tense: "add", "refactor", "fix" (NOT "added" /
  "adding" / "added the").
- Max ~72 cols including the prefix.
- No trailing period.
- No quoting the PR number — squash-merge appends `(#NN)`; don't
  pre-empt.

### Body rules

- One or two short paragraphs.
- Plain prose preferred; bullets tolerated when the commit truly is
  multi-item (e.g. a session that landed 4 syntheses in one commit).
- Explain the **why**, not the what. The diff shows the what.
- Mention scope boundaries: "this commit does X but NOT Y; Y is in a
  follow-up".
- Cite specific anchors when relevant: `nbtinsert.c:1907-1911`,
  `knowledge/subsystems/storage-buffer.md §5`. Helps future archaeology.
- If the commit was prompted by a session, name it:
  `(see sessions/2026-06-02-cf6402-review-validation.md)`.
- For corpus commits: include the line count + cite count for each new
  synthesis doc, so STATE.md updates and commit messages stay in sync.

### Trailers

Trailers go at the bottom in this order:

1. `Plan:` — link back to whatever drove this commit. Two accepted
   shapes:
   - **Phased plan (canonical, required when applicable):** `Plan:
     planning/<slug>/plan.md (phase <N>: <title>)`. Required when
     this commit implements a phase of a `planning/<slug>/plan.md`
     per R5 of `.claude/rules/pg-implement-discipline.md`.
   - **Loose pointer (recipe / trio / one-off):** `Plan: <freeform>`
     — e.g. `Plan: cloud routine .claude/cloud/pg-quality-auditor.md`,
     `Plan: catalog trio "trigger system depth"`. Use the canonical
     form whenever a `planning/<slug>/plan.md` actually exists; the
     loose form is for commits where the "plan" is a recipe, thread,
     or session, not a planner artifact.
2. `Sites:` — if the commit spans multiple non-obvious sites. Format:
   `Sites: <file:line>, <file:line>`. Skip if the diff makes the sites
   obvious (single-file commits, etc.).
3. `Session:` — optional, link to a session log if the work was
   significant enough to log. Format:
   `Session: sessions/2026-06-02-cf6402-review-validation.md`.
4. `Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
   — **required for every meta-repo commit** (per the user's global
   default). Always last. **Lowercase** — see the casing note under
   §"Format" above.

Trailers are separated from the body by a blank line. Each on its own
line.

### Examples (canonical)

#### Knowledge corpus, single subsystem

```
ft(corpus): synthesize tcop spine (770 lines, 39 cites)

Distill the 7 per-file tcop docs + 6 header docs into
knowledge/subsystems/tcop.md. Closes the priority-15 spine gap from
pg-claude-plan.md §5.3 — the fourth and final synthesis of the
2026-06-02 interactive batch.

Covers per-backend lifecycle (BackendMain → BackendInitialize
(no-shmem invariant) → InitProcess → PostgresMain sigsetjmp + main
loop), first-byte dispatch table, simple vs extended query, portal
runner (5 strategies), ProcessUtility two-tier split, DestReceiver
abstraction, HandleFunctionRequest, CommitTag registry. 23 invariants.
All line numbers verified via grep -n at 4b0bf0788b0.

Sites: knowledge/subsystems/tcop.md, progress/STATE.md, progress/coverage.md
Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

(real-log anchor: `4925200` — `ft(corpus): memory contexts depth trio …`)

#### Planner suite, multi-file new skill set

```
ft(skills): add two-phase planner + pg-implement + meta-commit-style

The Phase-D validation run (CF #6402 review) proved the corpus + skills
compose for review work. This commit adds the upstream pieces of the
implementation pipeline: pg-feature-brainstorm (Phase 1), pg-feature-plan
(Phase 2), pg-implement (Phase 3). Plus meta-commit-style (for THIS
repo) split from the existing upstream-only commit-message-style.
Plus .claude/rules/pg-implement-discipline.md as the strict invariant
layer above the procedural skills.

The chain: /pg-brainstorm <idea> → planning/<slug>/brainstorm.md →
/pg-plan <slug> → planning/<slug>/plan.md → /pg-implement <slug> →
per-phase commits + planning/<slug>/notes.md.

Plan: (none — this is the planner itself)
Session: sessions/2026-06-02-planner-suite.md
Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

(real-log anchor: `62da1c2` — `ft(skills): skill-creator heavy pass round 1 …`)

#### Per-phase commit during /pg-implement (this style)

```
ft(dev): add server_side_vars catalog table

Phase 1 of the server-side-variables plan: add the pg_variable
catalog table that stores per-session variables. Bumps catversion.
genbki regenerates pg_proc.dat and the BKI bootstrap file.

The table holds (varname, vartype, varvalue, varisset) — minimal
fields per the brainstorm decision to ship the MVP without DEFAULT
clauses. Type coercion happens at SET time, not at definition.

Plan: planning/server_side_vars/plan.md (phase 1: catalog table)
Sites: src/include/catalog/pg_variable.h, src/include/catalog/catversion.h,
       src/backend/catalog/Makefile, src/backend/catalog/genbki.pl
Co-authored-by: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

> Caveat: this example commit would actually live in `dev/`, not the
> meta repo (it touches `src/...`), so per R5 it'd use the upstream
> **`commit-message-style`** (no `Co-authored-by`). The shape above is
> illustrative of the meta-style trailer block; the **per-phase
> `notes.md` append** in the meta repo is the real meta-repo commit
> in a phased plan.

## Forbidden in meta-repo commits

- Conventional-commits flavor `feat:` / `fix:` — we use `ft(scope):`
  / `hf(scope):` instead. The scope is mandatory.
- Bare title without a prefix.
- Missing `Co-authored-by:` footer (lowercase).
- GitHub-style **uppercase** `Co-Authored-By:` — git canonicalizes to
  lowercase and the meta-repo log is dominantly lowercase (45 vs 11
  in last 50 with a co-author trailer). Use lowercase.
- Inline ticket numbers like `(closes #42)` — let GitHub squash-merge
  append the PR ref.
- Trailing period on title.
- Emoji.
- `Signed-off-by` — that's kernel-style; we don't use DCO here.

## Cross-skill notes

- The full chain for a planned feature:
  `pg-feature-brainstorm` → `pg-feature-plan` → `pg-implement`
  (each phase commits in `dev/` using `commit-message-style` —
  upstream PG style). Then meta-repo commits to update knowledge or
  planning artifacts use **this** skill.
- If a single conceptual change has BOTH meta-repo writes AND `dev/`
  edits, split into two commits — one in each repo with the appropriate
  style.

## Where this applies

`/Users/matej/Work/postgres/postgres-claude/` — the meta repo. Both at
top level and inside `.claude/worktrees/*` (which are still meta-repo
worktrees, just on feature branches).

## Cross-references

- `.claude/skills/commit-message-style/SKILL.md` — the *other* style (upstream PG, dev/, no `Co-authored-by`).
- `.claude/skills/memory-keeping/SKILL.md` — pairs with this skill at session wrap; STATE.md updates land via this style.
- `.claude/skills/pg-implement/SKILL.md` — invokes this for per-phase notes.md appends; pairs with `commit-message-style` for per-phase dev/ commits.
- `.claude/skills/pg-feature-plan/SKILL.md` — planning artifacts (brainstorm.md, plan.md) land via this style.
- `.claude/rules/pg-implement-discipline.md` — R10 (two-repo separation) is what makes this style necessary.
