# parse_oper.h

- **Source:** `source/src/include/parser/parse_oper.h` (~70 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Operator-resolution surface.

## Exported entries

- `oper`, `right_oper`, `compatible_oper`, `compatible_oper_opid`,
  `left_oper` (prefix, only kept for backward compat / docs).
- `make_op`, `make_scalar_array_op`.
- `oprid` / `oprfuncid` shortcut helpers.
- `OpernameGetOprid` / `LookupOperName` / `LookupOperNameTypeNames` —
  DDL-side lookups.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
