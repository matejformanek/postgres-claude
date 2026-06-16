---
path: src/bin/psql/variables.c
anchor_sha: 4b0bf0788b0
loc: 492
depth: deep
---

# variables.c

- **Source path:** `source/src/bin/psql/variables.c`
- **Lines:** 492
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `variables.h` (API + hook typedefs), `startup.c` (installs all the assign/substitute hooks for special variables: AUTOCOMMIT, ECHO, FETCH_COUNT, PROMPT*, etc.), `command.c` (`\set`/`\unset` consumers), `psqlscan.l` and `psqlscanslash.l` (the SQL-side `:var` / `:'var'` / `:"var"` interpolation).

## Purpose

The `\set` variable store. A singly-linked list of `{name, value, substitute_hook, assign_hook, next}` kept sorted by `strcmp(name)`. Provides set/get/parse helpers plus the hook-install mechanism that lets `startup.c` wire the dozens of special variables to their C-state shadows in `pset`.

## Public surface

- `valid_variable_name(name)` (23, static) — ASCII letters/digits/underscore plus any high-bit byte (so non-ASCII identifiers work, modulo encoding sanity which is NOT checked here). **Must stay in sync with `variable_char` in `psqlscan.l` and `psqlscanslash.l`** per the comment at 18-22. [from-comment, variables.c:18-22]
- `CreateVariableSpace()` (52) — allocates the header sentinel `{NULL, NULL, NULL, NULL, NULL}`. [verified-by-code, variables.c:52-65]
- `GetVariable(space, name)` (72) — linked-list linear scan. Returns the variable's `value` (which may be NULL if the variable has hooks but no value). Returns NULL if not present. Early-exit when `strcmp(current->name, name) > 0` (list is sorted). [verified-by-code, variables.c:72-94]
- `ParseVariableBool(value, name, *result)` (108) — accepts true/false/yes/no/on/off/1/0 and unique prefixes (`o` is ambiguous; `on`/`off` require ≥2 chars). On parse failure, error-logs (unless `name == NULL`) and leaves `*result` unchanged. [verified-by-code, variables.c:108-146]
- `ParseVariableNum(value, name, *result)` (157) — `strtol(value, &end, 0)`; full string must be consumed; must fit in `int`. [verified-by-code, variables.c:157-182]
- `ParseVariableDouble(value, name, *result, min, max)` (194) — `strtod`. Empty string is explicitly rejected (platforms vary). Range-checked. [verified-by-code, variables.c:194-251]
- `PrintVariables(space)` (256) — `\set` with no args. Honors `cancel_pressed`. Variables with NULL value are silently skipped. [verified-by-code, variables.c:256-271]
- `SetVariable(space, name, value)` (281) — sets or deletes (when `value == NULL`). Calls substitute hook then assign hook. If assign hook returns false, the value is `pg_free`'d and the slot is untouched. If both value and hooks are NULL after assignment, the slot is removed from the list. Returns the assign hook's bool (or true if no hook). [verified-by-code, variables.c:281-366]
- `SetVariableHooks(space, name, shook, ahook)` (385) — install hooks; creates the slot if absent. After installing, runs `shook(current->value)` then `ahook(current->value)` (assign return ignored). [verified-by-code, variables.c:385-431]
- `VariableHasHook(space, name)` (438) — used by `\unset` logic in `command.c` to decide whether a true delete is allowed. [verified-by-code, variables.c:438-457]
- `SetVariableBool(space, name)` (463) — shortcut for `SetVariable(space, name, "on")`.
- `DeleteVariable(space, name)` (475) — shortcut for `SetVariable(space, name, NULL)`.
- `PsqlVarEnumError(name, value, suggestions)` (487) — standardized enum-rejection error message.

## Hook lifecycle

The store stores names sorted; inserts use a `previous`/`current` pair walk so a new slot is linked between `previous` and `current` (line 357-364). Deletion drops `current` after freeing `name` (337-343). The hook-driven path at 316-348 is delicate:

1. `pg_strdup` the proposed value (so substitute hooks can `free` or return it; assign hooks may retain it). [verified-by-code, variables.c:316]
2. Run substitute hook; new pointer becomes the canonical proposal.
3. Run assign hook; if false, `pg_free(new_value)` (`current->value` is untouched).
4. On success, free old `current->value`, install `new_value`.
5. If now NULL and no hooks, unlink + free slot.

The contract: substitute hook **must** free its input if returning a different pointer, otherwise we leak (variables.h:42-46 documents this).

## State owned

- The variable list itself — every `\set NAME VALUE` creates / mutates a node.
- Hook function pointers (set by `startup.c::EstablishVariableSpace`-style code).
- **Does not own** the `pset` C scalars that hooks update — those live in `settings.h`.

## Phase D notes

- **`:var` SQL interpolation safety lives in `psqlscan.l`, NOT here.** This file is just the name→value store. The substitution `:'var'` (quote literal) and `:"var"` (quote identifier) is implemented inside the flex SQL scanner; bare `:var` is unsanitized text substitution. For a malicious psql variable, only the quoted forms are safe. The corpus needs a per-file doc for `psqlscan.l` to fully cover this; from `variables.c` we only see that **`GetVariable` returns the raw string verbatim with no escaping**, leaving safety entirely to the caller. [verified-by-code, variables.c:72-94] [ISSUE-injection: `:var` (bare form) does no quoting; user/server must use `:'var'` or `:"var"` to defend against injection from variable contents (high — but this is a caller contract, not a bug in variables.c)]
- **Variable contents can be server-influenced.** `\gset` (and `\gset prefix_`) populates psql variables from query result columns. A `SELECT '; DROP TABLE users;--' AS x \gset` puts that string in `:x`. Subsequent use of bare `:x` in a query is injection. The `\gset` path is in `command.c`; variables.c is just the storage. [inferred, variables.c:281] [ISSUE-injection: `\gset` lets server-controlled strings become psql variables; bare `:var` use is then a server-to-client injection vector (high — caller contract)]
- **Special variable hooks live in `startup.c::EstablishVariableSpace`** (not in this batch). The hook-managed variables include AUTOCOMMIT, ON_ERROR_STOP, ECHO, ECHO_HIDDEN, ON_ERROR_ROLLBACK, COMP_KEYWORD_CASE, HISTCONTROL, HISTFILE, HISTSIZE, IGNOREEOF, FETCH_COUNT, PROMPT1/2/3, VERBOSITY, SHOW_CONTEXT, SINGLELINE, SINGLESTEP, QUIET, HIDE_TABLEAM, HIDE_TOAST_COMPRESSION, SHOW_ALL_RESULTS, WATCH_INTERVAL. Each maps a string to a C scalar in `pset`. [inferred — confirmed against settings.h:162-186 field list] [no concern]
- **Server-controllable assignment?** No — variables.c has no network code. The only path from server-data to a variable is via `\gset` / `\gexec` / `\set :foo` patterns, all driven by client-side code. [verified-by-code, variables.c:1-492] [no concern]
- **`valid_variable_name` accepts any high-bit byte without encoding check.** A multi-byte sequence is treated as N independent valid bytes; an invalid UTF-8 sequence still passes. Probably fine because the scanner accepts the same alphabet, so the round-trip works. [verified-by-code, variables.c:34] [no concern]
- **Linked-list O(N).** Every `GetVariable` is linear. With ~50 special vars plus user vars, this is fine. A `\set FOO bar` in a tight loop is O(N^2). [verified-by-code, variables.c:80-91] [no concern — psql scale]
- **`PrintVariables` silently skips NULL-valued slots.** A slot with hooks but no value (e.g. `\unset BOOL` then no resetting hook applied) doesn't appear in `\set` output but does respond to `GetVariable`. Surprising but not exploitable. [verified-by-code, variables.c:264-270] [no concern]
- **`ParseVariableBool`'s prefix matching.** `\set ECHO o` is ambiguous (on/off both start with `o`). The code special-cases `o` to require ≥2 chars. But `\set ECHO t` matches `true`, `\set ECHO f` matches `false`, etc. — short prefixes are accepted. A typo of `\set FOO ye` for `yes` works; `\set FOO ne` doesn't match anything. Documented but surprising. [verified-by-code, variables.c:120-132] [no concern]

## Cross-references

- `:var` interpolation: `psqlscan.l` (not in this batch — corpus gap).
- `\gset`/`\gexec`: `command.c` (not in this batch).
- Special variable wiring: `startup.c` (not in this batch).
- C scalars shadow store: `settings.h.md`.

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=15 [from-comment]=1 [inferred]=2 [no concern]=6 [ISSUE]=2`
