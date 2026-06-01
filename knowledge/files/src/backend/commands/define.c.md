# define.c

- **Source path:** `source/src/backend/commands/define.c`
- **Lines:** 376
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `defrem.h` (the public defGet* prototypes), every `*cmds.c` file (consumes these helpers).

## Purpose

"Support routines for dealing with DefElem nodes." [from-comment, define.c:13] The grammar produces `DefElem` nodes (name + value + action) for any clause shaped like `OPTION = value` — used by CREATE TYPE/OPERATOR/AGGREGATE/FUNCTION/INDEX/SEQUENCE/EXTENSION/SERVER/USER MAPPING/etc. This file is the central typesafe-extractor library so each commands/*.c doesn't reinvent the parsing.

## Public surface

- `defGetString` (34) — `Value` (T_String, T_Integer cast, T_Float cast) → C string; errors with `ERRCODE_SYNTAX_ERROR` if missing.
- `defGetNumeric` (67) — extract a numeric, accepting integer or float.
- `defGetBoolean` (93) — `true`/`false`/`on`/`off`/`0`/`1`/`yes`/`no`; the canonical bool parser.
- `defGetInt32` (148), `defGetInt64` (172), `defGetObjectId` (205) — bounded-integer extractors.
- `defGetQualifiedName` (238) — multi-element identifier (e.g. `schema.name`).
- `defGetTypeName` (270), `defGetTypeLength` (298) — type-system extractors for CREATE TYPE.
- `defGetStringList` (342) — parenthesised list of strings.
- `errorConflictingDefElem` (370) — canonical "option X specified more than once" error helper, used everywhere DefElems are consumed.

## Why this file matters

Every CREATE command uses these. Errors here surface to users as syntax errors; the canonical messages live here so wording stays consistent across the whole DDL surface.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
