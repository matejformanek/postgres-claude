# `src/backend/utils/adt/format_type.c`

- **File:** `source/src/backend/utils/adt/format_type.c` (488 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

SQL function `format_type(type_oid, typemod) → text` and the C entry
point `format_type_extended()` used everywhere a type needs to be
rendered for human/SQL consumption (psql `\d`, `pg_dump`, error
messages, `ruleutils.c`). Handles the **canonical SQL spelling**
(`integer` vs `int4`, `character varying(N)` vs `varchar`) and the
double-quoting of user types whose names match keywords.
(`format_type.c:33-58` [from-comment])

## Key functions

- `format_type(PG_FUNCTION_ARGS)` (`:60`) — SQL binding. Non-strict
  so it can handle NULL typemod (`:67-79`); NULL typemod is a distinct
  case from typemod = -1, see header comment.
- `format_type_extended(type_oid, typemod, flags)` (`:111`) — C entry
  point. Flags:
  - `FORMAT_TYPE_TYPEMOD_GIVEN` — emit `(N)` when typemod ≥ 0.
  - `FORMAT_TYPE_ALLOW_INVALID` — `"???"` or `"-"` instead of error.
  - `FORMAT_TYPE_INVALID_AS_NULL` — return NULL instead.
  - `FORMAT_TYPE_FORCE_QUALIFY` — always schema-qualify, ignoring
    search_path.
- `printTypmod(typname, typemod, typmodout)` (`:30`, defn near end of
  file) — invokes the type's typmodout function via fmgr to render
  the parenthesized typmod.

## Special-case table (`:186-323`)

A long `switch (type_oid)` for built-in types that need to be reported
with the SQL-standard spelling rather than the catalog `typname`:
- `bit` / `varbit` → `bit` / `bit varying`
- `bpchar` → `character`
- `bool` → `boolean`
- `float4` / `float8` → `real` / `double precision`
- `int2` / `int4` / `int8` → `smallint` / `integer` / `bigint`
- `time*` / `timestamp*` → SQL spellings
- `varchar` → `character varying`
- Plus special handling for "bit with typmod -1 is not BIT" (`:194-198`,
  comment is precise about gram.y interaction).

Anything not in the switch falls through to default formatting:
schema-qualify based on `TypeIsVisible` (or always-qualify under
FORCE_QUALIFY), and `quote_qualified_identifier` to handle keyword
collisions.

## Array handling

- Detects "true array types" via `IsTrueArrayType` AND
  `typstorage != PLAIN` (`:149-150`) — this excludes `oidvector` and
  similar plain-storage array-shaped types that should NOT be
  rendered as `oid[]`.
- For arrays, the element type is formatted via the special-case path,
  and `[]` is appended.

## Phase D notes

- **Pure read-only function** over `pg_type` syscache entries. No
  untrusted I/O.
- `elog(ERROR, "cache lookup failed for type %u", type_oid)` (`:137,
  :162`) is the only error path absent the ALLOW_INVALID flag — and
  this is internal-bug territory, not attacker-reachable.
- Output is always palloc'd, single-pass; no resource bound concerns.

## Potential issues

- [ISSUE-correctness: the BIT/BPCHAR special-case at `:189-201,
  :207-220` quietly returns `buf == NULL` for the
  `TYPEMOD_GIVEN && typemod == -1` case, causing the function to fall
  through to default (quoted) output. Subtle interaction with gram.y
  reserved word handling — comment explains, but a subtle parser change
  could break round-tripping. (low)]
- [ISSUE-dead-code: `FORMAT_TYPE_ALLOW_INVALID` flag is set
  unconditionally in the SQL entry (`:65`); the path returning `"???"`
  in the SQL surface is exercised when a stale OID is passed. Verify
  this is intentional (it is — `pg_dump` etc. want forgiving output).
  (informational)]

## Cross-references

- `source/src/backend/utils/adt/ruleutils.c` — the heaviest consumer.
- `source/src/include/utils/lsyscache.h` — `getBaseType`, type
  resolution helpers.
- `source/src/include/catalog/pg_type.h` — type OIDs and
  `Form_pg_type`.
- `source/src/backend/parser/gram.y` — the special productions referenced
  in the comment at `:174-182`.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 4
