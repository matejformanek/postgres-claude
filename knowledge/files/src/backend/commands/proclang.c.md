# `src/backend/commands/proclang.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~238
- **Source:** `source/src/backend/commands/proclang.c`

Tiny file: implements `CREATE LANGUAGE` (no-arg form, the trusted
template lookup form is handled by extensions). Validates the handler,
inline, and validator function signatures, then inserts into
`pg_language`, recording the dependencies (handler, inline, validator,
owner, extension). [verified-by-code]

## API / entry points

- `CreateProceduralLanguage(stmt)` — handles `CREATE LANGUAGE` /
  `CREATE OR REPLACE LANGUAGE`. Returns the language's `ObjectAddress`.
  [verified-by-code]
- `get_language_oid(langname, missing_ok)` — `LANGNAME` syscache
  lookup with optional ereport. [verified-by-code]

## Notable invariants / details

- Permission: requires `superuser()` only (line 64-67). The trusted
  vs untrusted distinction is recorded but doesn't change permission;
  `pltrusted` is taken from the parser. [verified-by-code]
- Handler signature check (line 74-80): handler must return
  `LANGUAGE_HANDLEROID`. Inline function (if specified) takes
  `INTERNALOID`. Validator takes `OIDOID`. Return types of inline /
  validator are ignored. [from-comment]
- `replaces[]` array is initialized all-true (line 109) then specific
  fields are flipped false for the UPDATE path:
  `Anum_pg_language_oid`, `lanowner`, `lanacl` (lines 145-147). The
  trio means CREATE OR REPLACE preserves OID, ownership, and grants.
  [from-comment]
- On REPLACE: existing `pg_depend` entries deleted first
  (`deleteDependencyRecordsFor`), then re-recorded by the common code
  below. Shared deps (owner) untouched because ownership is preserved.
  [from-comment]
- Object-access hook fired post-create (line 213) for security label
  /sepgsql integration.

## Potential issues

- Lines 134-139. `#ifdef NOT_USED` block for an `object_ownercheck`
  call; comment "currently pointless, since we already checked
  superuser". Dead source; either delete or convert to a path that
  matters if non-superuser ever becomes allowed.
  [ISSUE-dead-path: NOT_USED ownership check (nit)]
- Replace path silently keeps `lanispl=true` and `lanpltrusted=stmt->
  pltrusted`; if a user OR REPLACEs to flip trusted, they can change
  it, but no permission re-check happens beyond the initial superuser
  gate. Probably intentional. [unverified]
- `LookupFuncName(stmt->plhandler, 0, NULL, false)` (line 74) passes
  `false` for missing_ok, which means a missing handler ereports
  somewhere down the stack. Standard pattern.

## Synthesized by
<!-- backlinks:auto -->
