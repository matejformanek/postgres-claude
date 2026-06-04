---
path: src/backend/utils/adt/enum.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 616
depth: deep
---

# enum.c

- **Source path:** `source/src/backend/utils/adt/enum.c`
- **Lines:** 616
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/catalog/pg_enum.h` (Form_pg_enum, `EnumUncommitted`, `AddEnumLabel`/`RenumberEnumType`), `src/backend/catalog/pg_enum.c` (uncommitted-enum tracking + renumbering), `src/backend/utils/cache/typcache.c` (`compare_values_of_enum`, sortorder cache), `src/include/utils/typcache.h`.

## Purpose
Implements the SQL-visible surface of enum types: text/binary I/O (`enum_in`/`enum_out`/`enum_recv`/`enum_send`), the full B-tree comparison operator family, and the enum programming functions (`enum_first`/`enum_last`/`enum_range`). [from-comment] `enum.c:3-4`. Enum *values* are stored as the OID of their `pg_enum` row in user tables [verified-by-code] `enum.c:144-147`; ordering comes from `pg_enum.enumsortorder` via the typcache, not from the OID itself except in the even-OID fast path. The file's central safety concern is preventing uncommitted enum values from leaking into indexes. [verified-by-code] `enum.c:33-103`.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `enum_in` | `enum.c:108` | SQL input: label string -> enum OID via `ENUMTYPOIDNAME` syscache; soft-error capable (`escontext`). |
| `enum_out` | `enum.c:154` | SQL output: enum OID -> label via `ENUMOID` syscache. |
| `enum_recv` | `enum.c:178` | Binary input: reads label text, resolves to OID. |
| `enum_send` | `enum.c:220` | Binary output: emits label text. |
| `enum_lt`/`enum_le`/`enum_gt`/`enum_ge` | `enum.c:305,314,341,350` | Ordering comparisons via `enum_cmp_internal`. |
| `enum_eq`/`enum_ne` | `enum.c:323,332` | Equality: pure OID compare, no catalog lookup. |
| `enum_cmp` | `enum.c:377` | B-tree support: returns -1/0/1. |
| `enum_smaller`/`enum_larger` | `enum.c:359,368` | min/max aggregate transition support. |
| `enum_first` | `enum.c:436` | First (lowest sortorder) member of the enum type. |
| `enum_last` | `enum.c:465` | Last (highest sortorder) member. |
| `enum_range_all` | `enum.c:526` | 1-arg: array of all members in sort order. |
| `enum_range_bounds` | `enum.c:495` | 2-arg: array of members between `lower` and `upper` (NULL = open). |
| `check_safe_enum_use` (static) | `enum.c:62` | Central guard rejecting uncommitted enum values. |
| `enum_cmp_internal` (static) | `enum.c:251` | Comparison engine with even-OID fast path + typcache. |
| `enum_endpoint` (static) | `enum.c:391` | Shared scan for `enum_first`/`enum_last`. |
| `enum_range_internal` (static) | `enum.c:546` | Shared scan for both `enum_range` variants. |

## Internal landmarks
- **Enum-blacklist / uncommitted-value guard:** `check_safe_enum_use` `enum.c:62-103`. Three-tier check: (1) fast path if the `pg_enum` tuple is hinted `HEAP_XMIN_COMMITTED` `enum.c:72-73`; (2) direct xmin check via `TransactionIdIsInProgress`/`TransactionIdDidCommit` `enum.c:79-82`; (3) consult `EnumUncommitted(en->oid)` `enum.c:90-91`. Only if all fail does it raise `ERRCODE_UNSAFE_NEW_ENUM_VALUE_USAGE` `enum.c:97-102`. The "safe" carve-out for values created in the same transaction as the type is tracked explicitly in `pg_enum.c`, not inferred from tuple xmins `enum.c:46-57`.
- **Even-OID comparison fast path:** `enum.c:269-276`. New (post-creation) enum values are assigned even OIDs in sortorder order, so two even OIDs compare correctly by raw OID magnitude without touching the catalog. Odd OIDs (assigned by ALTER TYPE ADD VALUE squeezing between existing values, or after renumbering exhausts even slots) fall through to `compare_values_of_enum` in typcache.c `enum.c:301-302`.
- **typcache caching in fcinfo:** `enum_cmp_internal` stashes the `TypeCacheEntry *` in `fcinfo->flinfo->fn_extra` `enum.c:279-298`; an `Assert(fcinfo->flinfo != NULL)` `enum.c:263` deliberately trips on callers that forget to pass flinfo, since the fast-path exit would otherwise hide the bug.
- **Index-not-syscache for ordered scans:** `enum_endpoint` `enum.c:411-413` and `enum_range_internal` `enum.c:570-572` open `EnumRelationId` + `EnumTypIdSortOrderIndexId` and use `systable_beginscan_ordered`, explicitly NOT the syscache, per `RenumberEnumType` comments `enum.c:401-405,560-563`.
- **Lookup table:** `small[]`/`big` word table is in cash.c, not here; enum.c has no static tables.

## Invariants & gotchas
- **Uncommitted enum values must never reach SQL operations** that could index them `enum.c:34-44`. `check_safe_enum_use` is called in every path returning an enum to SQL: `enum_in` `enum.c:141`, `enum_recv` `enum.c:209`, `enum_endpoint` `enum.c:420`, and per-element in `enum_range_internal` `enum.c:589`. Note `enum_out`/`enum_send` do NOT call it — emitting a value already in hand is considered safe.
- **The guard is intentionally conservative** — "stronger than necessary" `enum.c:42-44`; it rejects uncommitted values even when no index is involved.
- **enum_eq/enum_ne bypass the catalog entirely** `enum.c:323-339`: equality is OID identity. This is correct because each label has exactly one OID; but it means equality never raises the uncommitted-value error that ordering comparisons could.
- **enum_in length check before syscache** `enum.c:117-123`: labels >= NAMEDATALEN are rejected up front to avoid an Assert failure inside SearchSysCache (the cache key is a NameData). Same in `enum_recv` `enum.c:190-196`.
- **`enum_in`/`enum_recv` soft-error asymmetry:** `enum_in` uses `ereturn(escontext, ...)` for not-found/too-long `enum.c:119,129`, honoring soft-error context; but the `check_safe_enum_use` it calls always hard-throws `ereport(ERROR)` `enum.c:97`. The comment `enum.c:135-140` flags this as a known wart ("Perhaps we should ... report 'unsafe use' softly"). `enum_recv` does not take a soft context at all and hard-throws everywhere `enum.c:192,202`.
- **Sort order is not OID order in general** `enum.c:301-302`: only even/even OID pairs may be compared by magnitude. Any code comparing enum values by OID directly is wrong for odd OIDs.
- **Empty enum -> InvalidOid endpoints** `enum.c:425-426`; `enum_first`/`enum_last` translate that into `ERRCODE_OBJECT_NOT_IN_PREREQUISITE_STATE` "contains no values" `enum.c:456-460,485-489`.
- **`get_fn_expr_argtype` dependency:** `enum_first`/`enum_last`/`enum_range_*` derive the enum type from the call expression, not the argument value (which may be NULL) `enum.c:442-451,471-480,531-540`. Calling these via DirectFunctionCall without a proper expr tree yields "could not determine actual enum type" `ERRCODE_FEATURE_NOT_SUPPORTED`.

## Cross-references
- [[knowledge/files/src/backend/utils/adt/cash.c]], [[knowledge/files/src/backend/utils/adt/numutils.c]] — sibling adt I/O files.
- [[knowledge/idioms/fmgr-and-spi]] — `PG_GETARG_OID`/`PG_RETURN_OID`, `fn_extra` caching, `get_fn_expr_argtype`, `DirectFunctionCall`.
- [[knowledge/idioms/error-handling]] — `ereturn`/`escontext` soft-error path vs `ereport(ERROR)`; `ERRCODE_UNSAFE_NEW_ENUM_VALUE_USAGE`.
- `source/src/backend/catalog/pg_enum.c` — `EnumUncommitted`, `AddEnumLabel`, `RenumberEnumType` (the even/odd OID and uncommitted-tracking machinery this file relies on).
- `source/src/backend/utils/cache/typcache.c` — `compare_values_of_enum`, sortorder snapshot.

## Potential issues
- **[ISSUE-undocumented-invariant: enum_in soft-error promise is partially broken by check_safe_enum_use]** `enum.c:135-141` — `enum_in` is wired for soft errors (`escontext`), but the `check_safe_enum_use` call at `enum.c:141` unconditionally `ereport(ERROR)`s at `enum.c:97`, so an input-validation caller (e.g. `pg_input_is_valid`) asking for a soft result can still get a hard ERROR for an uncommitted value. The in-code comment acknowledges this as a deliberate-but-questionable shortcoming, so it is documented-as-known rather than a silent bug. Severity: nit.

## Confidence tag tally
- [verified-by-code]: 6
- [from-comment]: 2
- [from-README]: 0
- [inferred]: 0
- [unverified]: 0
