# `utils/regproc.h` — regproc/regoper/regclass formatting + name→OID parsing

**Verified against source pin `4b0bf0788b0`** (path:
`source/src/include/utils/regproc.h`)

## Role

Public helpers for the `reg*` family of catalog OID aliases (regproc,
regprocedure, regoper, regoperator, regclass, regtype, regrole, regnamespace,
regdictionary, regconfig). Both directions: OID → printable qualified name
(`format_procedure`, `format_operator`) and qualified-name string → list
of name parts (`stringToQualifiedNameList`).

## Public API

- Flag bits — `source/src/include/utils/regproc.h:19-20, 24-25`:
  - `FORMAT_PROC_INVALID_AS_NULL`, `FORMAT_PROC_FORCE_QUALIFY`.
  - `FORMAT_OPERATOR_INVALID_AS_NULL`, `FORMAT_OPERATOR_FORCE_QUALIFY`.
- `char *format_procedure_extended(Oid procedure_oid, uint16 flags)` —
  `:21`.
- `char *format_operator_extended(Oid operator_oid, uint16 flags)` — `:26`.
- `List *stringToQualifiedNameList(const char *string, Node *escontext)`
  — `:28`.
- Backwards-compat shims:
  - `format_procedure`, `format_procedure_qualified` — `:29-30`.
  - `format_procedure_parts(oid, **objnames, **objargs, missing_ok)` —
    `:31-32`.
  - `format_operator`, `format_operator_qualified` — `:34-35`.
  - `format_operator_parts(oid, **objnames, **objargs, missing_ok)` —
    `:36-37`.

## Invariants

- `format_procedure_extended` returns the unique qualified name only if
  needed to disambiguate from search_path; with `FORCE_QUALIFY` it
  always qualifies. [inferred from flag name, `:20`]
- With `INVALID_AS_NULL`, missing OIDs return NULL; without it,
  they error. [from-flag-name, `:19`]
- `stringToQualifiedNameList` accepts the standard PG identifier syntax
  (dotted, optionally quoted, case-folded per identifier rules) and
  returns a `List *` of `String` nodes — one per name component.
  [inferred; matches parser identifier handling]
- `escontext`, when non-NULL, captures soft errors per the standard
  PG soft-error pattern. [from PG idiom; matches `parse_datetime`
  style in formatting.h]

## Notable internals

The "regfoo" types are user-facing OID aliases that print as qualified
names — these helpers are what makes that work. They consult
`pg_proc`/`pg_operator`/`pg_class` to find the row, then format with
schema qualification rules.

## Trust-boundary / Phase D surface

- **NAME-vs-OID cluster (echo of A3+A6+A7+A8+A9+A10)**:
  `stringToQualifiedNameList` parses an arbitrary identifier string —
  pretty much every NAME→OID surface in PG ends up calling this. A
  caller that uses the parsed list to look up OIDs without holding
  appropriate locks is vulnerable to TOCTOU races against
  CREATE/DROP. [ISSUE-correctness: stringToQualifiedNameList is the
  parse half of every NAME→OID race in PG; callers must hold locks
  themselves (likely)]
- `format_procedure_extended(oid, ...)` returns a heap string of
  unbounded length — qualified names with quoted special characters
  can balloon. No per-call cap. [ISSUE-resource: format_procedure
  output size is unbounded (nit)]
- `INVALID_AS_NULL` vs error: callers that forget to set the flag and
  pass a stale OID get an ERROR. This is the right default for SQL
  callers but can break introspection tools that scan a list of OIDs.
  [ISSUE-api-shape: default behaviour for missing OID is ERROR; flag
  changes to NULL (nit; well-documented in flag name)]
- `format_procedure_parts` (and `_operator_parts`) take output pointers
  `**objnames` / `**objargs` — these are allocated in caller's current
  memory context. If a caller passes pre-allocated NIL lists, the
  helpers will replace, not append. [ISSUE-documentation: output
  pointer semantics not documented in header (nit)]
- `stringToQualifiedNameList` with soft-error escontext: if the parser
  hits an invalid identifier (e.g. unterminated quote), it should
  return false-ish via escontext rather than ereport. Header doesn't
  say what the return value is on soft-error. [ISSUE-documentation:
  soft-error return semantics undocumented (nit)]
- The PG-13+ shift to qualified-name lists for object addresses
  (`get_object_address`) makes this header a critical trust surface —
  any function that takes a NAME from a SQL string and resolves it
  to an OID for ACL purposes is using these helpers. [ISSUE-security:
  regproc.h is a core NAME→OID surface; lock discipline is caller's
  problem (cross-ref A3+A6+A7+A8+A9+A10) (likely)]

## Cross-refs

- `knowledge/files/src/include/utils/acl.h.md` — `get_role_oid` is the
  role-side equivalent.
- A3, A6, A7, A8, A9, A10 — the NAME-vs-OID cluster across the corpus.

<!-- issues:auto:begin -->
- [Issue register — `include-utils`](../../../../issues/include-utils.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-correctness: `stringToQualifiedNameList` is the parse half of
   every NAME→OID race; lock discipline is caller's (likely)] —
   `source/src/include/utils/regproc.h:28`.
2. [ISSUE-security: regproc.h is a core NAME→OID surface; echoes
   A3+A6+A7+A8+A9+A10 cluster (likely)] —
   `source/src/include/utils/regproc.h:28`.
3. [ISSUE-resource: `format_procedure_extended` output is unbounded
   (nit)] — `source/src/include/utils/regproc.h:21`.
4. [ISSUE-documentation: `format_procedure_parts` / `_operator_parts`
   output-pointer ownership not documented (nit)] —
   `source/src/include/utils/regproc.h:31-37`.
5. [ISSUE-documentation: `stringToQualifiedNameList` soft-error return
   semantics undocumented (nit)] —
   `source/src/include/utils/regproc.h:28`.
6. [ISSUE-api-shape: default missing-OID behaviour is ERROR; flag
   `INVALID_AS_NULL` flips to NULL (nit)] —
   `source/src/include/utils/regproc.h:19,24`.
