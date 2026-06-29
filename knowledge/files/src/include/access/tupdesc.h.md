# tupdesc.h

- **Source path:** `source/src/include/access/tupdesc.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tupdesc_details.h`, `tupdesc.c`.

## Purpose

Defines `TupleDesc` (the backend's canonical rowtype descriptor) plus the auxiliary structs `AttrDefault`, `ConstrCheck`, `TupleConstr`, and the hot-path `CompactAttribute`. Also declares every function in `tupdesc.c` and the `TupleDescAttr` / `TupleDescCompactAttr` accessor macros. [from-comment, tupdesc.h:1-13, 50-67]

## Key types

- **`CompactAttribute`** (68) — 8-byte cut-down `FormData_pg_attribute` for hot-path deform. Holds `attcacheoff`, `attlen`, `attbyval`, `attalignby`, packed bool flags (`attispackable`, `atthasmissing`, `attisdropped`, `attgenerated`), and `attnullability` (one of `'f'`/`'u'`/`'v'`/`'i'`). Must stay 8 bytes — the comment flags this explicitly. [from-comment, tupdesc.h:50-67]
- **`TupleConstr`** (38) — Per-relation constraints (default expressions, CHECK constraints, missing-value entries for added columns, summary flags `has_not_null`, `has_generated_stored`, `has_generated_virtual`).
- **`AttrDefault`** (22), **`ConstrCheck`** (28) — Sub-arrays referenced by `TupleConstr`.
- **TupleDesc fields (continued past line 120):** natts; per-tuple `tdtypeid` + `tdtypmod`; `tdrefcount` (−1 = unmanaged, ≥0 = ref-counted by tupdesc.c); a variable-length array of CompactAttribute followed (after a calculated offset) by the array of `FormData_pg_attribute`.

## Key invariants

- `tdrefcount == -1` ⇒ caller owns the TupleDesc's lifetime; `tdrefcount >= 0` ⇒ ResourceOwner-tracked. [from-comment, tupdesc.h:112-118]
- `tdtypeid != RECORDOID` ⇒ rowtype is a named composite type; `tdtypeid = RECORDOID` ⇒ anonymous or typmod-registered. [from-comment, tupdesc.h:100-110]
- `CompactAttribute` is a CACHE of `Form_pg_attribute` fields — must be refreshed via `populate_compact_attribute` after any mutation to the underlying `FormData_pg_attribute`. [from-comment, tupdesc.h:53-67]
- Domains-over-composite NEVER appear in `tdtypeid`. [from-comment, tupdesc.h:106-110]

## Public surface

- All the functions defined in `tupdesc.c` are declared here: `CreateTemplateTupleDesc`, `CreateTupleDesc`, `CreateTupleDescCopy*`, `TupleDescCopy*`, `TupleDescFinalize`, `FreeTupleDesc`, `IncrTupleDescRefCount` / `DecrTupleDescRefCount`, `equalTupleDescs`, `equalRowTypes`, `hashRowType`, `TupleDescInitEntry*`, `BuildDescFromLists`, `TupleDescGetDefault`, plus the accessor macros `TupleDescAttr(tupdesc, i)` and `TupleDescCompactAttr(tupdesc, i)`.

## Cross-references

- See `knowledge/files/src/backend/access/common/tupdesc.c.md` for behaviour.

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=6 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/tupledesc.md](../../../../data-structures/tupledesc.md)
