---
path: src/interfaces/ecpg/test/regression.h
anchor_sha: e18b0cb7344
loc: 5
depth: read
---

# src/interfaces/ecpg/test/regression.h

## Purpose

Shared definitions header included by every `.pgc` ecpg test source. It is
*not* a C header — it is an **embedded-SQL fragment** consumed by the ecpg
preprocessor, defining the four symbolic names the regression suite uses for
its two throwaway databases and two throwaway roles:

- `REGRESSDB1` → `ecpg1_regression`
- `REGRESSDB2` → `ecpg2_regression`
- `REGRESSUSER1` → `regress_ecpg_user1`
- `REGRESSUSER2` → `regress_ecpg_user2`

`[verified-by-code]` (`regression.h:1-5`)

Tests `EXEC SQL CONNECT TO :REGRESSDB1 USER :REGRESSUSER1` against these
names so the actual database/role names are decided in one place and so the
PostgreSQL "all test roles must be named `regress_*`" rule (enforced by
`pg_regress.c`) is honored.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `REGRESSDB1` / `REGRESSDB2` | `regression.h:1-2` | ecpg `EXEC SQL define` macros, expanded at preprocess time |
| `REGRESSUSER1` / `REGRESSUSER2` | `regression.h:4-5` | role names, prefix-matched by pg_regress's role-cleanup |

## Internal landmarks

There are no C tokens. Each line is the ecpg directive
`EXEC SQL define <name> <value>;` — the preprocessor substitutes the value
wherever the name appears as a connect-target or role-id in the host `.pgc`.

## Invariants & gotchas

- **Not a C header.** Including it from a plain `.c` file is meaningless;
  only `.pgc` sources before ecpg preprocessing recognize the syntax.
- **Role names must start with `regress_`** — `pg_regress.c` refuses test
  roles that don't, to prevent collisions with real users.
  `[from-comment]`
- The whitespace inside `exec\t\tsql` is significant only to humans; ecpg's
  scanner treats it as a single token sequence.

## Cross-refs

- `knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md` — driver
  that builds and runs the `.pgc` programs that include this header.
- `knowledge/files/src/interfaces/ecpg/preproc/` — the ecpg preprocessor
  that consumes `EXEC SQL define`.
- `knowledge/files/src/test/regress/pg_regress.c.md` — the base regression
  framework that enforces the `regress_*` role-name rule.
