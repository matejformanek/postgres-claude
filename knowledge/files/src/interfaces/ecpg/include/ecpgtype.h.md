---
path: src/interfaces/ecpg/include/ecpgtype.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 109
depth: read
---

# `ecpgtype.h` — ECPG host-variable type taxonomy

## Purpose
Defines the three enumerations that the ECPG preprocessor emits into generated
`.c` files and that ecpglib consumes at runtime: `ECPGttype` (the host-variable
type codes, `ECPGt_*`), `ECPGdtype` (SQL-descriptor item codes, `ECPGd_*`), and
`ECPG_statement_type` (normal / execute / exec-immediate / prepnormal / prepare
/ exec-with-exprlist). The header comment frames host variables as a "recursive
definition" of typed list elements. [verified-by-code] Installed into the public
include dir, so the `ECPGt_*` values are a frozen ABI between any preprocessor
version and any ecpglib version. [inferred]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `enum ECPGttype` | ecpgtype.h:41 | host-var type codes; `ECPGt_char = 1` anchors the range; ends with `ECPGt_bytea` [verified-by-code] |
| `enum ECPGdtype` | ecpgtype.h:71 | descriptor item codes; `ECPGd_count = 1` [verified-by-code] |
| `enum ECPG_statement_type` | ecpgtype.h:95 | statement dispatch class passed to `ECPGdo` [verified-by-code] |
| `IS_SIMPLE_TYPE(type)` | ecpgtype.h:92 | macro: true for simple scalar/string/bytea codes [verified-by-code] |

## Internal landmarks
- The numbering is explicit-implicit: only `ECPGt_char = 1` / `ECPGd_count = 1`
  / `SQL3_*` peers are pinned; the rest auto-increment. The `ECPGt_EOIT` /
  `ECPGt_EORT` sentinels separate insert-types from result-types in the variadic
  `ECPGdo` argument stream (ecpgtype.h:62-63). [verified-by-code]
- `ECPGt_numeric` vs `ECPGt_decimal`: malloc'd-digit-array vs fixed-array
  variants (ecpgtype.h:49-52) — the same split surfaced in
  [[pgtypes_numeric.h]] (`numeric` vs `decimal` structs). [verified-by-code]

## Invariants & gotchas
- `IS_SIMPLE_TYPE` is a **range check** `((type) >= ECPGt_char && (type) <=
  ECPGt_interval) || string || bytea` (ecpgtype.h:92). It silently depends on
  the declaration order of `ECPGttype` — every "simple" code must stay
  contiguous between `ECPGt_char` and `ECPGt_interval`. Inserting a non-simple
  code into that span, or moving one out, breaks the predicate with no compile
  error. [verified-by-code] See `knowledge/issues/ecpg.md`.
- Because this is an installed/ABI header, appending to `ECPGttype` is safe but
  renumbering is not — a preprocessor and an ecpglib built against different
  numberings would mis-decode the host-variable stream. [inferred]

## Cross-refs
- [[ecpglib.h]] — `ECPGset_noind_null` / `ECPGis_noind_null` take `enum ECPGttype`.
- [[sqltypes.h]] — Informix `C*TYPE` / `SQL*` aliases map onto these codes.
- [[pgtypes_numeric.h]] — the numeric/decimal storage-class split.
- `knowledge/files/src/interfaces/ecpg/ecpglib/typename.c.md` — runtime consumer
  (`ecpg_type_name` aborts on an unknown `ECPGttype`).

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues
- **[ISSUE-invariant: IS_SIMPLE_TYPE couples to enum order]** `ecpgtype.h:92` —
  the range macro relies on `ECPGt_char..ECPGt_interval` staying contiguous in
  the `ECPGttype` declaration (ecpgtype.h:43-55). A future code inserted mid-run
  silently changes which types are "simple" with no diagnostic. Mirrored to
  `knowledge/issues/ecpg.md`.
