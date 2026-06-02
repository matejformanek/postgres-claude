# planning/ — work-in-progress design docs

This directory holds **forward-looking design artifacts** for PG
features that haven't landed yet. One subdirectory per feature, slug-
named.

## How this differs from `knowledge/` and `sessions/`

| Directory | Purpose | Lifespan |
|---|---|---|
| `knowledge/` | Distilled, durable reference about PG internals as they are NOW | Lives until the corresponding source is refactored |
| `sessions/` | Append-only log of what HAPPENED in past sessions | Permanent record (audit trail) |
| **`planning/`** | Forward-looking design for what SHOULD happen | Lives until the feature lands or is abandoned |

A planning doc is **explicitly tentative**. It can be wrong, it can
change, it can be abandoned. The knowledge corpus is *spec*; the
planning corpus is *proposal*.

## Per-slug layout

```
planning/<slug>/
├── brainstorm.md   # Phase 1 — sketch (from /pg-brainstorm)
├── plan.md         # Phase 2 — heavy plan (from /pg-plan)
└── notes.md        # Phase 3 — running log (from /pg-implement, per-phase)
```

Not every slug has all three files:
- A brainstorm without a plan = the user hasn't committed yet.
- A plan without notes = the implementation hasn't started.
- A plan + notes mid-flight = a paused implementation; `notes.md`
  tells you where to resume.

## Slug naming

Snake_case, ≤30 chars, descriptive. Examples:
- `server_side_vars` — for "add server-side variables to PostgreSQL"
- `explain_pins` — for "make EXPLAIN show buffer-pin counts"
- `nbtree_skip_arrays_review` — for review work on a specific area

When auto-derived from a free-form idea, the slug is the first 3-4
significant words snake_cased.

## The three-phase pipeline

```
idea
  │
  │  /pg-brainstorm <idea>
  ▼
planning/<slug>/brainstorm.md
  │       └─ 2-3 candidate approaches + DECISION: questions
  │
  │  user picks approach + answers decisions
  │
  │  /pg-plan <slug>
  ▼
planning/<slug>/plan.md
  │       └─ implementable plan: §3 files, §4 catalog, §5 WAL,
  │          §6 locking, §7 memory, §8 phased impl, §9 tests, etc.
  │
  │  user reviews + approves plan
  │
  │  /pg-implement <slug>
  ▼
dev/ feature branch + planning/<slug>/notes.md
        └─ per-phase commits in dev/ with Plan: trailers;
           per-phase notes appended here
```

Each phase produces a durable artifact. Mid-pipeline pauses are
expected — `notes.md` is the resume point.

## Authoritative files

The three skills + their command wrappers + the rules file together
define the pipeline:

- `.claude/skills/pg-feature-brainstorm/SKILL.md` — Phase 1 procedure
- `.claude/skills/pg-feature-plan/SKILL.md` — Phase 2 procedure
- `.claude/skills/pg-implement/SKILL.md` — Phase 3 procedure
- `.claude/rules/pg-implement-discipline.md` — binding rules (R1-R12)
- `.claude/commands/pg-brainstorm.md` — `/pg-brainstorm` wrapper
- `.claude/commands/pg-plan.md` — `/pg-plan` wrapper
- `.claude/commands/pg-implement.md` — `/pg-implement` wrapper

Plus `meta-commit-style` for any `postgres-claude/` commit
(planning artifacts included).

## Cleanup policy

- **Feature lands upstream:** keep `plan.md` and `notes.md` indefinitely
  — they're the design archaeology a future maintainer (or future
  Claude session) needs to understand WHY the patch looks the way it
  does. `brainstorm.md` can be archived or kept; either is fine.
- **Feature abandoned:** add a `STATUS: abandoned (date, reason)` line
  at the top of `plan.md` and leave in tree for ~3 months as a
  cautionary note, then remove.
- **Slug is stale (brainstorm only, no progress in 30+ days):** if the
  user moves on, just `git rm -r planning/<slug>/`. The session log
  preserves that it happened.

## Slugs currently in flight

(none — this directory was just created on 2026-06-02.)

To list active slugs at any time:

```bash
ls planning/
```

To see which have plans (and are ready for `/pg-implement`):

```bash
for d in planning/*/; do
  [ -f "$d/plan.md" ] && echo "$(basename "$d")"
done
```

To see which have notes (and are mid-implementation):

```bash
for d in planning/*/; do
  [ -f "$d/notes.md" ] && echo "$(basename "$d"): $(grep -c '^## Phase' "$d/notes.md") phases logged"
done
```
