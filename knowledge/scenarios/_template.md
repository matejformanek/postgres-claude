---
scenario: <kebab-case-slug-matching-filename>
when_to_use: <one-sentence trigger — the user-facing "I want to ..." phrase>
companion_skills: [skill-1, skill-2]
related_scenarios: [sibling-scenario-1]
canonical_commit: <SHA of a representative historical PG patch>
last_verified_commit: e18b0cb7344
---

# Scenario — <Imperative title>

## Scope — what's in / out

**In scope:**
- Bullet what this scenario covers.
- One change-class per scenario; if a real feature spans two, the
  planner unions them.

**Out of scope:**
- Closely-related change-classes that have their own scenario.
- Niche edge cases — call them out and link to the issue register
  if applicable.

## Pre-flight

- **Companion skills:** load `skill-1`, `skill-2`. Each names a
  procedural rule this playbook depends on.
- **Canonical commit:** `<short-sha>` — `<one-line commit subject>`.
  Read it before starting; it's the reference example for this
  change-class.
- **Common pitfalls (one-line each):**
  - Pitfall 1 (link to `knowledge/issues/<subsystem>.md` if recorded).
  - Pitfall 2.

## File checklist (the FULL sweep)

Every row is mandatory unless explicitly noted "optional". `pg-feature-plan`
will refuse to drop these without a user override.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `src/include/catalog/pg_proc.dat` | … | [pg_proc.dat.md](../files/src/include/catalog/pg_proc.dat.md) | catalog-conventions |
| 2 | `src/backend/utils/adt/<name>.c` | … (NEW file) | — | fmgr-and-spi |
| 3 | `src/include/catalog/catversion.h` | bump CATALOG_VERSION_NO | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| … | … | … | … | … |

(Use `—` in the per-file doc column for genuinely-new files; otherwise
the entry should exist in `knowledge/files/` and link.)

## Phases — suggested split for `pg-feature-plan`

The planner will use this as the §8 starting point. Each phase is a
self-contained chunk; the tree must build at the end of each phase.

1. **Phase 1 — <title>.** Files: [1, 3, …]. Edits: … . Phase-end
   check: …
2. **Phase 2 — <title>.** Files: [2, …]. Edits: … . Phase-end check:
   …
3. **Phase 3 — Tests + docs.** Files: [test files, SGML]. Phase-end
   check: regress + iso + TAP scope per §9 of the plan template.

## Pitfalls

- Trap 1 — describe + cite (`source/<path>:<line>` or
  `knowledge/issues/<subsystem>.md` row).
- Trap 2 — …
- **Synchronization traps** (sibling files that must change together):
  list any "if you edit X you MUST also edit Y" pairs here.

## Verification (exact test invocations)

```bash
# Regression scope this scenario expects to exercise
meson test -C dev/build-debug --suite regress --test <name>

# Isolation, if applicable
meson test -C dev/build-debug --suite isolation --test <name>

# TAP, if applicable
meson test -C dev/build-debug --suite recovery --test <name>
```

If the change adds a brand-new test, name it explicitly here.

## Cross-refs

- Companion skills: `.claude/skills/<skill-1>/SKILL.md`,
  `.claude/skills/<skill-2>/SKILL.md`.
- Related scenarios: `scenarios/<sibling>.md`.
- Idioms: `knowledge/idioms/<relevant>.md`.
- Subsystems: `knowledge/subsystems/<relevant>.md`.
- Issues: `knowledge/issues/<subsystem>.md`.
- Reference patch (canonical_commit): `git -C source show <sha>`.
