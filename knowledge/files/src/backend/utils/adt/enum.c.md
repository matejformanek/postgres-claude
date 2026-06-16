# enum.c — `enum` type I/O and ordering

## Purpose

SQL-level `enum` type: every CREATE TYPE … AS ENUM populates `pg_enum`, and this file implements I/O + comparison via syscache lookups. Comparison is by `enumsortorder` (a float4 in `pg_enum`) so labels can be added between existing ones without renumbering OIDs.

Source: `source/src/backend/utils/adt/enum.c` (616 lines).

## Key functions

- `check_safe_enum_use` (63) — a generated-this-transaction-and-rolled-back enum value would be invalid to compare; this gate rejects use of un-committed enums to avoid dangling values. [verified-by-code]
- `enum_in` (109) — lookup label string in `pg_enum` syscache (`ENUMTYPOIDNAME`); error if not found. [verified-by-code]
- `enum_out` (155) — reverse lookup by OID. [verified-by-code]
- `enum_recv` / `enum_send` (179, 221) — wire format. [verified-by-code]
- `enum_cmp_internal` (252) — fetches both enums' sortorder via `EnumOidInfo` syscache lookup, compares as float4. [verified-by-code]
- `enum_lt` ... `enum_gt` / `enum_cmp` (306-388). [verified-by-code]
- `enum_smaller` / `enum_larger` (360, 369). [verified-by-code]
- `enum_endpoint` (392) — scans `pg_enum` for the first or last label by sort order. [verified-by-code]
- `enum_first` (437), `enum_last` (466), `enum_range_bounds` (496), `enum_range_all` (527), `enum_range_internal` (547). [verified-by-code]

## Phase D notes

- **Sort-order based comparison** means adding a label "between" two existing ones is cheap (just allocate a sortorder between the two neighbors). But this also means comparing two enums requires a syscache lookup per comparison — significant cost in big sorts. [from-comment]
- **`check_safe_enum_use` mitigates a real hazard**: if a transaction adds a label, returns the OID to client code, then rolls back, the OID becomes invalid. The gate prevents the rolled-back OID from participating in queries. [verified-by-code]
- **Cross-database enum confusion impossible**: enums are typed by typoid, and pg_enum entries are catalog-tied.

## Potential issues

- `[ISSUE-dos: a large enum (thousands of labels) with frequent comparisons does many syscache lookups; the EnumOidInfo cache helps but isn't sized for arbitrary growth (low — uncommon design)]`.
- `[ISSUE-correctness: enum_cmp uses float4 sortorder; when labels are inserted via "ALTER TYPE … ADD VALUE 'x' BEFORE 'y'", sortorder midpoints can run out of precision after many insertions. The DDL code re-numbers when needed but a heavily-edited enum could hit float4 precision limits (low; rare)]`.
- `[ISSUE-undocumented-invariant: enum_range with NULL bounds returns the full range; with one NULL it returns the half-range. Documented in user docs but the function-level invariants are spread across enum_range_bounds/all/internal (low)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
