# `src/backend/utils/adt/regproc.c`

- **File:** `source/src/backend/utils/adt/regproc.c` (2163 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O functions for the **registered-type aliases** for Oid:
`regproc`, `regprocedure`, `regoper`, `regoperator`, `regclass`,
`regcollation`, `regtype`, `regconfig`, `regdictionary`, `regrole`,
`regnamespace`, `regdatabase`. All are binary-compatible with `Oid` and
rely on Oid comparison/hash; the only interesting per-type behavior is
**how the text input gets resolved to an OID through catalog lookups**.
(`regproc.c:1-19` [from-comment])

## Type role

Catalog-lookup-driven OID input parsers. Output formats produce a
schema-qualified identifier where needed for round-trip safety.

## Surface

Per type, three I/O entry points and one `to_regXxx` no-throw wrapper:

| Type | input | output | to_X (no-throw) |
|------|-------|--------|-----------------|
| regproc | `regprocin` (`:67`) | `regprocout` (`:139`) | `to_regproc` (`:121`) |
| regprocedure | `regprocedurein` (`:229`) | `regprocedureout` (`:441`) | `to_regprocedure` (`:284`) |
| regoper | `regoperin` (`:484`) | `regoperout` (`:552`) | `to_regoper` (`:534`) |
| regoperator | `regoperatorin` (`:647`) | `regoperatorout` (`:847`) | `to_regoperator` (`:702`) |
| regclass | `regclassin` (`:890`) | `regclassout` (`:951`) | `to_regclass` (`:933`) |
| regcollation | `regcollationin` (`:1034`) | `regcollationout` (`:1094`) | `to_regcollation` (`:1076`) |
| regtype | `regtypein` (`:1184`) | `regtypeout` (`:1255`) | `to_regtype` (`:1217`) |
| regconfig | `regconfigin` (`:1329`) | `regconfigout` (`:1367`) | — |
| regdictionary | `regdictionaryin` (`:1439`) | `regdictionaryout` (`:1477`) | — |
| regrole | `regrolein` (`:1549`) | `regroleout` (`:1609`) | `to_regrole` (`:1591`) |
| regnamespace | `regnamespacein` (`:1666`) | `regnamespaceout` (`:1726`) | `to_regnamespace` (`:1708`) |
| regdatabase | `regdatabasein` (`:1783`) | `regdatabaseout` (`:1843`) | `to_regdatabase` (`:1825`) |

Each `*recv`/`*send` is `oidrecv`/`oidsend` aliased (`:203-216` and
analogues).

Common helpers:
- `stringToQualifiedNameList(string, escontext)` (`:1922`) — calls
  `SplitIdentifierString` to break `schema.name` into a List of String
  nodes.
- `parseNumericOid` / `parseDashOrOid` (`:1968`, `:1993`) — handle
  numeric input and `'-'` (InvalidOid).
- `parseNameAndArgTypes(string, allowNone, names, nargs, argtypes,
  escontext)` (`:2020`) — for `regprocedure('foo(int, text)')` and
  `regoperator('=(int, int)')` style input.

## Phase D notes — the parser-invocation hazard

- **`parseNameAndArgTypes` reaches into the SQL parser.** For each
  comma-separated type-name string inside the parens, it calls
  `parseTypeString` (parse_type.c) which in turn calls
  `raw_parser(typename, RAW_PARSE_TYPE_NAME)`. That's a **restricted
  parser entry point** that only matches the `Typename` non-terminal —
  no SQL statements, no expressions, no DML. [verified-by-code via
  parser/parse_type.c:756]
- **Therefore `regprocedure('foo(text, "; DROP TABLE x; SELECT 1")')`
  cannot smuggle in SQL.** The `; DROP TABLE x` is comma-split, then
  the parser-on-typename refuses to recognize it as a valid Typename.
  No injection.
- **However**, ALL these input functions perform **catalog reads**:
  syscache lookups, `RangeVarGetRelid`, `LookupTypeName`, etc. So they
  honor search_path, ACL state, and trigger pg_class / pg_proc /
  pg_namespace fetches. A user who can call `regclass('x')` with a
  malicious x can probe table existence across schemas — but only
  schemas they can see via search_path or schema-qualification, which is
  already standard catalog visibility.
- **`regclassin` and friends bypass locking** in most cases — they call
  `RangeVarGetRelid(rv, NoLock, …)` (`:1908` in `text_regclass`, and
  similar in `regclassin`). This is deliberate: looking up an OID by
  name shouldn't take a lock that could deadlock with concurrent DDL.
  But it means a `regclass` lookup result can be stale by the time the
  caller uses it — caller's problem, not this file's.
- **No DoS surface.** Each input goes through bounded catalog lookups;
  recursion is one level deep (through `parseTypeString`).

## Potential issues

- `[ISSUE-undocumented-invariant: regprocedure-style input invokes the
  SQL parser on each type-name fragment via RAW_PARSE_TYPE_NAME; safe but
  worth noting for sandboxing tools (info).]`
- `[ISSUE-info-disclosure: existence-probing via regclass('foo') tells
  the user whether `foo` is visible in their search_path; standard PG
  catalog visibility, but tracked under search_path control (info).]`
- `[ISSUE-correctness: regclassin returns OID without locking; concurrent
  DROP TABLE between OID lookup and use can ERRCODE_UNDEFINED_TABLE in
  the caller (medium, by design).]`

## Cross-references

- `source/src/backend/parser/parse_type.c` — `parseTypeString`.
- `source/src/backend/utils/adt/varlena.c` — `SplitIdentifierString`,
  `quote_qualified_identifier`.
- `source/src/backend/catalog/namespace.c` — `RangeVarGetRelid`,
  `FuncnameGetCandidates`, `LookupCollation`, etc.
- `source/src/backend/utils/cache/syscache.c` — every output uses
  SearchSysCache1(NAMEDOID) etc.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 2
- `[inferred]` × 1
