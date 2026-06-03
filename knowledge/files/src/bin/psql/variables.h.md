---
path: src/bin/psql/variables.h
anchor_sha: 4b0bf0788b0
loc: 100
depth: read
---

# variables.h

- **Source path:** `source/src/bin/psql/variables.h`
- **Lines:** 100
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `variables.c` (implementation), `startup.c` (where `SetVariableHooks` is called for the dozens of special variables), `psql/command.c` (`\set`/`\unset` consumers).

## Purpose

Defines the psql variable repository — a name-keyed associative store with optional `substitute` and `assign` hooks. A "variable space" is just a header `_variable` node whose `next` chain holds the actual entries, kept sorted by `strcmp` of `name`. [from-comment, variables.h:6-10, 56-72]

## Public surface

- `typedef bool (*VariableAssignHook)(const char *newval)` (31) — return false to refuse an assignment after printing the rationale via `pg_log_error`. Called both on user-driven assignment AND once on hook install. Return value ignored on install. [from-comment, variables.h:16-30]
- `typedef char *(*VariableSubstituteHook)(char *newval)` (54) — gets ownership of a malloc'd string, returns either the same pointer or a different malloc'd string (frees the original if returning a new one). Runs BEFORE the assign hook. Used e.g. to coerce `\unset BOOL` into `\set BOOL off`. [from-comment, variables.h:33-52]
- `struct _variable` (62) — `{ name, value, substitute_hook, assign_hook, next }`. Linked-list node. Header node has `name == NULL` and serves as list-head sentinel.
- `VariableSpace` (72) — typedef alias for `struct _variable *`.
- `CreateVariableSpace`, `GetVariable`, `ParseVariableBool`/`Num`/`Double`, `PrintVariables`, `SetVariable`, `SetVariableBool`, `DeleteVariable`, `SetVariableHooks`, `VariableHasHook`, `PsqlVarEnumError`. [verified-by-code, variables.h:75-98]

## Phase D notes

- **Hook lifecycle.** Per the comment at 22-30, the assign hook may legitimately *refuse* a value (used for the boolean enum-style values: `AUTOCOMMIT`, `ON_ERROR_STOP`, `ECHO_HIDDEN`, etc.). The hook is the only gatekeeper. If a hook forgets to validate, a `\set BAD_VALUE foo` typo silently corrupts internal C state. [from-comment, variables.h:16-30] [no concern — design contract]
- **Substitute hook can rewrite NULL→string.** A substitute hook running on `\unset FOO` can decide to install a default rather than letting the variable go unset. This is how `BOOL` variables behave. Side effect: `\unset FOO` may not actually unset FOO. The header comment calls this out. [from-comment, variables.h:33-52] [no concern — design contract]

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=5 [no concern]=2`
