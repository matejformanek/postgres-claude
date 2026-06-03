---
path: src/backend/utils/adt/bool.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 410
depth: deep
---

# bool.c

- **Source path:** `source/src/backend/utils/adt/bool.c`
- **Lines:** 410
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/builtins.h` (declares `parse_bool`/`parse_bool_with_len`), `src/include/catalog/pg_proc.dat` (boolin/boolout/booleq/bool_and/bool_or/etc. entries), `src/include/catalog/pg_type.dat` (`bool` type), `src/include/common/hashfn.h`, `src/include/libpq/pqformat.h`

## Purpose

Implements the built-in `boolean` SQL type: its I/O surface (`boolin`/`boolout`/`boolrecv`/`boolsend`), the `bool => text` cast (`booltext`), the six btree comparison functions, hash support, and the state machinery for the `bool_and`/`bool_or` (a.k.a. EVERY / ANY-SOME) aggregates [from-comment `bool.c:3-4`, `bool.c:289-321`]. It also exports the GUC/general-purpose textual boolean parser `parse_bool`/`parse_bool_with_len`, which is reused well outside the type machinery [from-comment `bool.c:24-28`].

## Public symbols

| Symbol | file:line | Role |
| --- | --- | --- |
| `parse_bool` | `bool.c:30` | Parse a NUL-terminated string to bool; wraps `parse_bool_with_len` |
| `parse_bool_with_len` | `bool.c:36` | Core textual-bool parser over (value,len); accepts true/false/yes/no/on/off/1/0 and unique prefixes |
| `boolin` | `bool.c:126` | Input function; trims whitespace then parses; soft-error capable via `ereturn` |
| `boolout` | `bool.c:157` | Output function; emits "t" or "f" |
| `boolrecv` | `bool.c:174` | Binary recv; one byte, any nonzero => true |
| `boolsend` | `bool.c:187` | Binary send; one byte 1/0 |
| `booltext` | `bool.c:204` | Cast bool=>text producing SQL-spec lowercase "true"/"false" |
| `booleq` | `bool.c:223` | Equality |
| `boolne` | `bool.c:232` | Inequality |
| `boollt` | `bool.c:241` | Less-than (false<true) |
| `boolgt` | `bool.c:250` | Greater-than |
| `boolle` | `bool.c:259` | Less-or-equal |
| `boolge` | `bool.c:268` | Greater-or-equal |
| `hashbool` | `bool.c:277` | Hash support (hash_uint32 of the bool) |
| `hashboolextended` | `bool.c:283` | 64-bit-seeded extended hash support |
| `booland_statefunc` | `bool.c:299` | bool_and / EVERY transition function |
| `boolor_statefunc` | `bool.c:311` | bool_or / ANY-SOME transition function |
| `bool_accum` | `bool.c:340` | Moving-aggregate forward transition; maintains BoolAggState |
| `bool_accum_inv` | `bool.c:361` | Moving-aggregate inverse transition |
| `bool_alltrue` | `bool.c:382` | Final function: true iff all non-null values true; NULL if no rows |
| `bool_anytrue` | `bool.c:397` | Final function: true iff any non-null value true; NULL if no rows |

## Internal landmarks

- `parse_bool_with_len` switch on `*value` (`bool.c:40`): a fast-dispatch on the first character before doing `pg_strncasecmp`. Most-used cases (`t`/`f`) first by design [from-comment `bool.c:39`].
- `'o'` ambiguity handling (`bool.c:78-93`): "on"/"off" both start with 'o', so the comparison length is forced to at least 2 (`len > 2 ? len : 2`) to keep "o" from being treated as a unique prefix [from-comment `bool.c:80`].
- `'1'`/`'0'` cases require `len == 1` exactly (`bool.c:94-109`) — so "10" or "01" do not parse.
- `struct BoolAggState` (`bool.c:317-321`): two int64 counters (`aggcount`, `aggtrue`) backing the bool aggregates.
- `makeBoolAggState` (`bool.c:323`): allocates the state in the aggregate context fetched via `AggCheckCallContext`; errors if called outside an aggregate context [verified-by-code `bool.c:329-330`].

## Invariants & gotchas

- **Prefix matching via length.** `parse_bool_with_len` calls `pg_strncasecmp(value, "true", len)` with the *caller-supplied* `len` as the comparison count (`bool.c:44`). This means a shorter `len` matches a prefix ("tr" => true), and a `len` longer than the literal still matches because `pg_strncasecmp` stops at the literal's NUL — i.e. trailing garbage after a full keyword is NOT rejected here. `boolin` protects against trailing garbage only by trimming whitespace, not arbitrary characters; correctness depends on callers passing a tight `len` [verified-by-code `bool.c:44-49`, `bool.c:138-145`]. (Not a bug: prefixes are an intentional, documented feature; see Potential issues for the subtlety.)
- **Whitespace trimming is `boolin`-only.** `boolin` strips leading/trailing `isspace` bytes (`bool.c:138-143`) before parsing; `parse_bool` does not. GUC parsing and other callers get no trimming.
- **`*result = false` on failure is a deliberate "suppress compiler warning"**, not a meaningful value — callers must check the boolean return, not `*result` (`bool.c:114-116`).
- **Soft-error path.** `boolin` uses `ereturn(fcinfo->context, ...)` not `ereport` (`bool.c:148`), so it participates in soft input error handling (e.g. `pg_input_is_valid`). The `(Datum) 0` is the soft-failure sentinel.
- **`boolrecv` accepts any nonzero byte as true** (`bool.c:180-181`) — it does not require a canonical 1, by documented design [from-comment `bool.c:171-172`].
- **Aggregate state context.** `bool_accum`/`bool_accum_inv` rely on the state being allocated in `agg_context` (`bool.c:332`), so it survives across transition calls; `bool_accum_inv` hard-errors if state is NULL because the forward function must have created it [verified-by-code `bool.c:369-370`].
- **NULL semantics in aggregates.** Both final functions return SQL NULL when `aggcount == 0` (no non-null inputs), distinguishing "no rows" from "all false" [verified-by-code `bool.c:390-391`, `bool.c:405-406`].

## Cross-references

- [[knowledge/idioms/fmgr-and-spi]] — PG_GETARG/PG_RETURN and the `Datum foo(PG_FUNCTION_ARGS)` convention used throughout.
- [[knowledge/idioms/error-handling]] — `ereturn` soft-error contract used in `boolin`.
- Sibling adt I/O type files: [[knowledge/files/src/backend/utils/adt/char.c]], [[knowledge/files/src/backend/utils/adt/name.c]].
- Aggregate transition/final convention: `AggCheckCallContext` in `src/backend/executor/nodeAgg.c`.

## Potential issues

- **[ISSUE-undocumented-invariant: parse_bool_with_len does not reject trailing characters after a complete keyword]**
  `bool.c:44-92` — Because the comparison count passed to `pg_strncasecmp` is `len` and the literal is NUL-terminated, a `len` longer than the keyword compares only up to the keyword's NUL and returns match. e.g. calling `parse_bool_with_len("tru", 3, ...)` correctly matches the prefix, but the function relies entirely on the caller passing a `len` no longer than the actual token; there is no explicit "consumed exactly len bytes" check for the multi-char keywords (only the `'1'`/`'0'` single-char cases check `len == 1`). `boolin` is safe because it trims to the real token length, but other callers of `parse_bool`/`parse_bool_with_len` must ensure `len` is tight. Severity: nit (intentional prefix design; documented only as "unique prefixes thereof" at `bool.c:26`, not the trailing-byte subtlety).

## Confidence tag tally

- [verified-by-code]: 6
- [from-comment]: 6
- [inferred]: 0
- [unverified]: 0
