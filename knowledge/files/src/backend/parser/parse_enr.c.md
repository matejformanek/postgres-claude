# parse_enr.c

- **Source:** `source/src/backend/parser/parse_enr.c` (29 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Tiny pass-through for parser-side lookups of **Ephemeral Named Relations**
— transient relations the executor sets up that the parser may need to
resolve as RTEs. The two canonical users are AFTER-trigger transition
tables (`OLD TABLE` / `NEW TABLE` in `CREATE TRIGGER`) and explicitly
registered ENRs (extensions / SPI callers).

## Functions

| Symbol | Role |
|---|---|
| `name_matches_visible_ENR` | predicate: is `refname` a visible ENR in this pstate's `QueryEnvironment`? |
| `get_visible_ENR` | lookup + return metadata (TupleDesc, est. rowcount, etc.) |

Both delegate immediately to `pstate->p_queryEnv` → `get_visible_ENR_metadata`
in `src/backend/utils/misc/queryenvironment.c`.

## Caveats

- ENRs are *not* in the system catalogs; they live in the per-query
  `QueryEnvironment`. If you forget to wire `p_queryEnv` into the
  pstate (e.g. when re-running parse analysis on a stored rule action),
  trigger transition tables become invisible and parse analysis errors
  with "relation does not exist".

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
