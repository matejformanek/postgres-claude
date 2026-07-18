# attoptcache.h

- **Source path:** `source/src/include/utils/attoptcache.h`
- **Lines:** 28
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `attoptcache.c` (impl).

## Purpose

Tiny header declaring the `AttributeOpts` varlena struct and the single accessor `get_attribute_options(attrelid, attnum)`.

## Public surface

- **Type**: `AttributeOpts` (19) — `{int32 vl_len_; float8 n_distinct; float8 n_distinct_inherited;}`. Varlena header field is `vl_len_`; "do not touch directly!" — use `VARSIZE` macros. [from-comment]
- **Function**: `get_attribute_options(Oid attrelid, int attnum) → AttributeOpts *`.

## Confidence tag tally

verified-by-code: 1 — from-comment: 1 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-cache.md](../../../../subsystems/utils-cache.md)
