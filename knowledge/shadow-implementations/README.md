# `knowledge/shadow-implementations/` — Phase E calibration runs

Per-run output of the shadow-implementation calibration loop. Each
`<slug>/` subdir holds:

- `spec.md` — extracted from the pgsql-hackers thread COVER
- `plan.md` — `pg-feature-plan` output (what we'd build)
- `notes.md` — `pg-implement` per-phase notes (when implementation
  is in scope)
- `comparison.md` — design + (when available) code diff vs upstream
- `skill-gaps.md` — gaps surfaced; input to next skill-creator pass

After 3-5 runs, `gap-catalog.md` aggregates the recurring findings
(like Phase C's gap-catalog).

## Runs to date

| Slug | Date | Target | Verdict | Grade |
|---|---|---|---|---|
| money-fx-exchange | 2026-06-12 | Joel Jacobson's "Add fx exchange support to money type" | REJECT (design unimplementable) | A |

## Methodology
See `knowledge/calibration/shadow-implementation-methodology.md`.

## How to add a run
1. Pick a candidate thread (per methodology Step 1).
2. Create `knowledge/shadow-implementations/<slug>/`.
3. Follow methodology Steps 2-6.
4. Add a row to the table above.
5. PR title: `ft(corpus): Phase E shadow run — <slug>`.
