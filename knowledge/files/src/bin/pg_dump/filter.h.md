---
path: src/bin/pg_dump/filter.h
anchor_sha: 4b0bf0788b0
loc: 71
depth: read
---

# filter.h

- **Source path:** `source/src/bin/pg_dump/filter.h`
- **Lines:** 71
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `filter.c` (implementation), `lib/stringinfo.h` (for the `StringInfoData` line buffer).

## Purpose

Public surface for the `--filter=<file>` parser. Declares one struct (`FilterStateData`), two enums (`FilterCommandType`, `FilterObjectType`), one function-pointer typedef (`exit_function`), and five extern functions. [verified-by-code, filter.h:14-71]

## Public types

- `exit_function` (20) — `typedef void (*exit_function)(int status)` — the caller-supplied terminator. Lets `filter.c` exit on parse errors without linking to any specific application's `exit_nicely`. [verified-by-code, filter.h:20]
- `FilterStateData` (25-32) — `{FILE *fp; const char *filename; exit_function exit_nicely; int lineno; StringInfoData linebuff;}`. [verified-by-code, filter.h:25-32]
- `FilterCommandType` (37-42) — `NONE | INCLUDE | EXCLUDE`. [verified-by-code, filter.h:37-42]
- `FilterObjectType` (47-61) — 12 entries: `NONE`, `TABLE_DATA`, `TABLE_DATA_AND_CHILDREN`, `DATABASE`, `EXTENSION`, `FOREIGN_DATA`, `FUNCTION`, `INDEX`, `SCHEMA`, `TABLE`, `TABLE_AND_CHILDREN`, `TRIGGER`. [verified-by-code, filter.h:47-61]

## Public surface

- `filter_object_type_name(fot)` — enum → English.
- `filter_init(fstate, filename, f_exit)`.
- `filter_free(fstate)`.
- `pg_log_filter_error(fstate, fmt, …)` — declared with `pg_attribute_printf(2, 3)` for compile-time format-string checking. [verified-by-code, filter.h:66-67]
- `filter_read_item(fstate, **objname, *comtype, *objtype)`.

[verified-by-code, filter.h:63-69]

## Phase D — surfaces of concern

- **The `FilterStateData` is owned by the caller** and passed by pointer everywhere; this means workers can't share filter state across processes. Not a concern for pg_dump because filter parsing happens entirely in the leader before any fork. [verified-by-code, filter.h:25-32] [no concern]
- **`FilterObjectType` enum has no `MAX` sentinel.** `filter_object_type_name` is exhaustive against the current 12 values and trails with `pg_unreachable()`; adding a new enum value without updating the switch would generate a compile-time warning under `-Wswitch-enum`. [verified-by-code, filter.h:47-61, filter.c:81-114] [no concern]
- **`exit_function` is `void(*)(int)`** so a malicious caller could pass a no-op and turn parse errors into silent continuations. Trust boundary: same process. [verified-by-code, filter.h:20] [no concern]

## Cross-references

- Implementation: `knowledge/files/src/bin/pg_dump/filter.c.md`.

## Confidence tag tally
`[verified-by-code]=8 [no concern]=3`
