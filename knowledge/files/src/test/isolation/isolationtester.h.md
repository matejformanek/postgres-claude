---
path: src/test/isolation/isolationtester.h
anchor_sha: e18b0cb7344
loc: 93
depth: read
---

# src/test/isolation/isolationtester.h

## Purpose

Public header defining the AST of a parsed isolation-test `.spec` file.
The bison grammar `specparse.y` populates the global `parseresult` of
type `TestSpec`, and the driver in `isolationtester.c` walks that tree
to execute permutations. The structs declared here — `TestSpec`,
`Session`, `Step`, `Permutation`, `PermutationStep`,
`PermutationStepBlocker` — are the durable surface that the parser and
the executor share. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `typedef struct Step Step` | `isolationtester.h:22` | forward decl |
| `Session` | `isolationtester.h:24-31` | name, setup/teardown SQL, array of steps |
| `struct Step` | `isolationtester.h:33-40` | name + SQL; `session` and `used` filled post-parse |
| `PermutationStepBlockerType` | `isolationtester.h:42-47` | `PSB_ONCE`, `PSB_OTHER_STEP`, `PSB_NUM_NOTICES` |
| `PermutationStepBlocker` | `isolationtester.h:49-58` | a single `(*)`, `(stepname)`, or `(N notices from session)` annotation |
| `PermutationStep` | `isolationtester.h:60-67` | one step inside a permutation, with optional blockers |
| `Permutation` | `isolationtester.h:69-73` | array of `PermutationStep` |
| `TestSpec` | `isolationtester.h:75-84` | top-level: setup, teardown, sessions, permutations |
| `extern TestSpec parseresult` | `isolationtester.h:86` | global output of the parser |
| `extern int spec_yyparse(void)` | `isolationtester.h:88` | bison entry |
| `extern int spec_yylex(void)` | `isolationtester.h:90` | flex entry |
| `extern void spec_yyerror(const char *)` | `isolationtester.h:91` | bison error hook |

## Internal landmarks

- The grammar fills most fields at parse time; `check_testspec()` in
  `isolationtester.c` later fills the cross-link fields marked
  `/* These fields are filled by check_testspec(): */` in the struct
  comments (`Step.session`, `Step.used`, `PermutationStep.step`,
  `PermutationStepBlocker.step`).
- `PermutationStepBlocker.target_notices` (`:57`) is **runtime
  workspace** — the executor mutates it during a permutation. The
  rest of the AST is otherwise immutable post-parse.
- `PSB_ONCE` corresponds to spec syntax `step(*)` — force the step to
  wait at least once for observability.
- `PSB_OTHER_STEP` corresponds to `step(otherstep)` — block until
  `otherstep` completes.
- `PSB_NUM_NOTICES` corresponds to `step(N notices from session)` —
  block until N NOTICEs arrive from a specific session.

## Invariants & gotchas

- `parseresult` is a singleton global — `spec_yyparse()` is not
  reentrant.
- Step names must be unique across all sessions in a spec — enforced
  in `check_testspec()` (`isolationtester.c:277-286`).
- A blocker referencing a step from the SAME session is rejected
  (`isolationtester.c:362-367`).
- Fields are mostly `char *` strdup'd by the lexer; ownership is the
  parser's, never freed in normal flow (the process exits at the end
  of the run).

## Cross-refs

- `knowledge/files/src/test/isolation/isolationtester.c.md` — the
  executor that consumes these structs.
- `knowledge/files/src/test/isolation/isolation_main.c.md` — the
  runner that spawns isolationtester.
- `src/test/isolation/specparse.y` — the bison grammar that populates
  the AST.
- `src/test/isolation/specscanner.l` — the flex tokenizer.
