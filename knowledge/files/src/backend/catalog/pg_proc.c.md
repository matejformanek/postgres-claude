# pg_proc.c

- **Source path:** `source/src/backend/catalog/pg_proc.c`
- **Lines:** ~1 220
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_proc relation." Centred on `ProcedureCreate`, the universal entry called by CREATE FUNCTION / CREATE PROCEDURE / CREATE AGGREGATE / CREATE OPERATOR (which all generate underlying pg_proc rows). Plus the three language validators (internal, C, sql) and the SQL-function parse-error position translator.

## Public surface

- `ProcedureCreate` (99) — **the main entry.** Takes function name, namespace, argument types, return type, language, prosrc, probin, prokind ('f','p','a','w'), volatility, parallel-safety, leakproof, strict, retset, security_definer, isWindow, args' default expressions, etc. Validates uniqueness against existing functions, performs OR REPLACE semantics, writes the pg_proc row, records dependencies (NORMAL on arg/return types, namespace, language; AUTO on the trigger if `prokind='t'`), and invokes the language validator. Returns the new function's ObjectAddress.
- `fmgr_internal_validator` (771) — language=internal: check that prosrc names a known internal symbol via fmgr lookup.
- `fmgr_c_validator` (814) — language=C: try to load the symbol; permission-check that current user is superuser (or has special privilege) and the file is on the allowed list.
- `fmgr_sql_validator` (857) — language=sql: parse-check the body without executing.
- `sql_function_parse_error_callback` (1024), `function_parse_error_transpose` (1048), `match_prosrc_to_query` (1115), `match_prosrc_to_literal` (1173) — translate a syntax-error position inside `prosrc` back to the original source-text position the user typed (so error messages point inside the CREATE FUNCTION body).
- `oid_array_to_list` (1230) — `oidvector` → List<Oid> helper used by callers.

## Confidence tag tally

`[verified-by-code]=4`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
