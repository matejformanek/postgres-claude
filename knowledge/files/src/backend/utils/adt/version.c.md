# src/backend/utils/adt/version.c

## Purpose

Implements the `version()` SQL function. One liner: returns the compile-time
`PG_VERSION_STR` macro as a `text` Datum.

## Role in PG

- `Datum pgsql_version(PG_FUNCTION_ARGS)` — sole entry point
  (`version.c:20-24`).
- Wired into `pg_proc.dat` under `version()`. Public, no role check.

## Key functions

- `pgsql_version` — `PG_RETURN_TEXT_P(cstring_to_text(PG_VERSION_STR));`
  Compile-baked string; cannot change at runtime.

## State / globals

None. Pure function of a compile-time macro.

## Phase D notes

- Information disclosure by design — `version()` is GRANT-able and
  intentionally shows full configure-time banner including OS, compiler
  version, and build options (`PG_VERSION_STR` is defined by
  `configure`/`meson`). For sites that need to hide this, the only
  remedy is to `REVOKE EXECUTE ON FUNCTION version() FROM PUBLIC`.
- No `current_setting('server_version')` consultation — `version()` and
  `SHOW server_version` can diverge (in principle); in practice they
  derive from the same configure value. [inferred]

## Potential issues

- [ISSUE-info-disclosure: full build banner exposed to PUBLIC by
  default; security scanners often flag this (low)]
