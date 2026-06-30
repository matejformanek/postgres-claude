# tupdesc.c

- **Source path:** `source/src/backend/access/common/tupdesc.c`
- **Lines:** 1193
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tupdesc.h`, `tupdesc_details.h`, `pg_attribute.h`, `catalog/heap.c` (relcache builder), `parser/parse_relation.c`.

## Purpose

Build, copy, compare, ref-count and free `TupleDesc` objects. A `TupleDesc` is the canonical description of a rowtype: an array of `Form_pg_attribute` plus a parallel `CompactAttribute` cache (hot path), optional `TupleConstr` (defaults + check constraints + missing values), and `tdtypeid`/`tdtypmod`/`tdrefcount`. The relcache, the executor, the typcache, and many DDL paths use this module to materialise rowtypes. [from-comment, tupdesc.c:1-17]

## Top-of-file comment

> "POSTGRES tuple descriptor support code". Brief — most of the documentation lives inline at the entry points. [from-comment, tupdesc.c:1-15]

## Public surface (non-static functions)

- **Creation:** `CreateTemplateTupleDesc` (165, returns a zeroed descriptor for natts), `CreateTupleDesc` (216, from existing `Form_pg_attribute *`), `CreateTupleDescCopy` (242), `CreateTupleDescTruncatedCopy` (289), `CreateTupleDescCopyConstr` (336), `BuildDescFromLists` (1109).
- **In-place copy:** `TupleDescCopy` (427), `TupleDescCopyEntry` (472), `TupleDescFinalize` (511) (populate CompactAttribute cache after manual edits).
- **Free / refcount:** `FreeTupleDesc` (560), `IncrTupleDescRefCount` (617), `DecrTupleDescRefCount` (635). Ref-counting is wired into the ResourceOwner so leaks are caught at xact end.
- **Comparison / hashing:** `equalTupleDescs` (648, full structural equality incl. constraints/defaults), `equalRowTypes` (835, just rowtype identity for typcache), `hashRowType` (871).
- **Single-attribute fill:** `TupleDescInitEntry` (900, lookup pg_type and fill one attribute), `TupleDescInitBuiltinEntry` (976, hard-coded for bootstrap), `TupleDescInitEntryCollation` (1084).
- **Default lookup:** `TupleDescGetDefault` (1152).

## Key static helpers

- `populate_compact_attribute_internal` (65), `populate_compact_attribute` (100), `verify_compact_attribute` (125) — keep the `CompactAttribute` cache in sync with the `Form_pg_attribute` it shadows; `verify_*` is an Assert-only consistency check.
- ResourceOwner glue: `ResourceOwnerRememberTupleDesc` (49), `ResourceOwnerForgetTupleDesc` (55), `ResOwnerReleaseTupleDesc` (1176), `ResOwnerPrintTupleDesc` (1187). The `tupdesc_resowner_desc` (38) sets `release_phase = RESOURCE_RELEASE_AFTER_LOCKS`. [verified-by-code]

## Key invariants

- `tdrefcount == -1` means "not refcounted" (caller manages lifetime explicitly via `FreeTupleDesc`). Refcounted descriptors must NOT be freed directly; you Decr the refcount and free happens at zero. [verified-by-code, tupdesc.c:560-635]
- `CompactAttribute` is a pure cache: any code that mutates `Form_pg_attribute` after creation must call `populate_compact_attribute` for that index. [from-comment, tupdesc.c:60-100]
- `equalTupleDescs` compares attnames, types, typmod, ndims, byval/len/storage/align/notnull/identity/generated, plus full `TupleConstr` (defaults + check constraints + missing). `equalRowTypes` is laxer — for typcache rowtype identity it ignores constraints. [verified-by-code, tupdesc.c:648-870]
- `TupleDescGetDefault` returns the default expression for `attnum` or NULL — it does NOT evaluate it; expression eval is the caller's job. [verified-by-code]

## Functions of note

1. **`CreateTemplateTupleDesc`** (165) — single allocation: descriptor header + natts `Form_pg_attribute` slots + natts `CompactAttribute` slots, all in current memory context. `tdrefcount = -1` by default. [verified-by-code]
2. **`CreateTupleDescCopy`** (242) — deep copies attributes BUT strips constraints/defaults/typid. Used when only the column shape matters (e.g. resolving record types). [verified-by-code]
3. **`TupleDescInitEntry`** (900) — looks up `pg_type` by OID, fills attname, atttypid, atttypmod, attbyval/len/align/storage/collation, calls `populate_compact_attribute`. The workhorse used by parser/executor code that builds tuple descs from query targetlists. [verified-by-code]
4. **`equalTupleDescs`** (648) — exhaustive comparator; used for catalog cache validation, plan invalidation, and to verify that a `RECORD` typmod is reusable. [verified-by-code]
5. **`IncrTupleDescRefCount` / `DecrTupleDescRefCount`** — implement refcount-tied-to-ResourceOwner pattern; when CurrentResourceOwner is released the descriptor's ref is automatically forgotten so leaks at xact end become a runtime warning. [verified-by-code]

## Cross-references

- Major callers: `relcache.c` (`RelationBuildTupleDesc`), `typcache.c` (record-type registry), `executor/execTuples.c`, `parser/parse_relation.c`, every `make_*` node builder that emits a rowtype.
- Calls into: `syscache.c` (`SearchSysCache` on TYPEOID / TYPENAMENSP), `utils/resowner.c`, `utils/datum.c`.

## Open questions

- The exact rules for when a manually mutated `Form_pg_attribute` (e.g. by DDL) re-enters this module to refresh the CompactAttribute — likely via `populate_compact_attribute` from callers in `tablecmds.c`. Not deep-traced. [unverified]

## Confidence tag tally
`[verified-by-code]=9 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/pg_attribute-form.md](../../../../../data-structures/pg_attribute-form.md)
- [data-structures/tupledesc.md](../../../../../data-structures/tupledesc.md)

