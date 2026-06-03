---
path: src/bin/psql/describe.h
anchor_sha: 4b0bf0788b0
loc: 153
depth: shallow
---

# describe.h

- **Source path:** `source/src/bin/psql/describe.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 153

## Purpose

Public surface of `describe.c` — one `extern bool` per `\d*` family
backslash command. Every entry comment names the meta-command that
calls it, so the file doubles as the canonical `\d*` → function index.
[verified-by-code, describe.h:12-150]

## Signature shape

Three argument-shape patterns dominate:

- **`(pattern, verbose, showSystem)`** — the most common; `pattern`
  matches `processSQLNamePattern` syntax (`schema.name`, glob/regex).
  Examples: `describeAggregates`, `describeTypes`, `describeRoles`,
  `listSchemas`. [verified-by-code]
- **`(types, pattern, verbose, showSystem)`** — when one slash command
  family covers multiple `relkind`/`prokind`/`relkind` selectors.
  `describeFunctions(functypes, …)` for `\df[anptw]`,
  `listTables(tabtypes, …)` for `\dt|i|s|v|m`,
  `listPartitionedTables(reltypes, …)` for `\dP[it]`. [verified-by-code]
- **`(am_pattern, type_pattern[, …], verbose)`** — for `\dAc/\dAf/\dAo/\dAp`,
  which take TWO pattern arguments (access-method + type/family).
  `describeFunctions` and `describeOperators` also take `char
  **arg_patterns, int num_arg_patterns` — a small array for the
  argument-type patterns in `\df FOO(int, text)`. [verified-by-code,
  describe.h:22-32, 132-147]

## Return convention

All functions return `bool`. Convention (cross-checked against
`describe.c`): `true` on success OR on "nothing to display"; `false`
only on actual error paths (PQexec failure, OOM, bad pattern through
`validateSQLNamePattern`). Callers in `command.c` propagate that bool
to `exec_command`'s return path. [inferred from describe.c:131-142
pattern]

## Cross-references

- Implementation: `describe.c` (every function defined there).
- Dispatch: `command.c` (`exec_command_d`, `exec_command_l`, etc.).
- Pattern parsing: `fe_utils/string_utils.c::processSQLNamePattern`.

## Phase D notes

No security surface in the header itself — string `pattern` arguments
are passed-through opaque. All quoting/escaping discipline lives in
`describe.c` callers and in `processSQLNamePattern`. [verified-by-code]

## Confidence tag tally
`[verified-by-code]=5 [inferred]=1`
