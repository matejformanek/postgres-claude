---
path: src/test/modules/test_ddl_deparse/test_ddl_deparse.c
anchor_sha: e18b0cb7344
loc: 338
depth: read
---

# src/test/modules/test_ddl_deparse/test_ddl_deparse.c

## Purpose

SQL-visible helpers that crack open the `CollectedCommand` struct
produced by the **event trigger** ddl-command-end facility, surfacing
the command-type tag, the canonical command tag, and a per-subcommand
breakdown for `ALTER TABLE`. Lets the regression suite for the
DDL-deparse infrastructure inspect exactly what the collection step
captured for each DDL statement. `[verified-by-code]`
`test_ddl_deparse.c:26-29,67-69,82-85`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `get_command_type(internal) returns text` | `:31` | Maps `CollectedCommand->type` enum to text |
| `get_command_tag(internal) returns text` | `:72` | Wraps `CreateCommandName(cmd->parsetree)`; NULL if no parsetree |
| `get_altertable_subcmdinfo(internal) returns setof record` | `:87` | Materialized SRF: one row per `AlterTableCmd` sub-step with `(subtype_text, object_description)` |

## Internal landmarks

- `get_command_type` (`:31`) — switch over `SCT_*` enum: `Simple`,
  `AlterTable`, `Grant`, `AlterOpFamily`, `AlterDefaultPrivileges`,
  `CreateOpClass`, `AlterTSConfig`, plus default `"unknown command
  type"`.
- `get_altertable_subcmdinfo` (`:87`) — uses `InitMaterializedSRF` to
  set up the tuplestore; for each `CollectedATSubcmd` in
  `cmd->d.alterTable.subcmds`, maps the `AlterTableCmd->subtype` to a
  human label via a 60+-arm switch covering every `AT_*` operation, and
  appends `(and recurse)` when `subcmd->recurse` is set (`:320-321`).
  Object description via `getObjectDescription(&sub->address, false)`.
- Errors out if called on a non-AlterTable collected command (`:93-94`)
  or if the subcommand list is empty (`:98-99`).

## Invariants & gotchas

- TEST MODULE — meant for use from event-trigger SQL functions where
  the `CollectedCommand` pointer is passed via `internal`-typed argument.
- The switch in `get_altertable_subcmdinfo` is **the contract**: any new
  `AlterTableType` enum value added in core must be added here too, or
  the row prints `"unrecognized"` (`:105`). Acts as a forcing function
  in code review.
- Returns `(and recurse)` suffix for `recurse = true` so the regression
  output disambiguates the recursive-vs-non-recursive variants of
  ALTER TABLE subcommands.

## Cross-refs

- `source/src/include/tcop/deparse_utility.h` — `CollectedCommand` and
  `CollectedATSubcmd` structs.
- `source/src/backend/tcop/utility.c` — `CreateCommandName` mapping
  parsetrees to command tag names.
- `source/src/include/nodes/parsenodes.h` — `AlterTableType` enum
  (the `AT_*` values).
- `knowledge/subsystems/parser-and-nodes.md` — context on
  `AlterTableCmd` node lifecycle.
