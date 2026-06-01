# relation.h

- **Source path:** `source/src/include/access/relation.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `relation.c`, `table.h`, `index.h`/`indexam.h`, `sequence.h`.

## Purpose

Declares the AM-agnostic relation-open primitives: `relation_open`, `try_relation_open`, `relation_openrv`, `relation_openrv_extended`, `relation_close`. These are the entry points everything else (`table_open`, `index_open`, `sequence_open`) is built on. [verified-by-code, relation.h:14-26]

## Public surface

- `relation_open(Oid, LOCKMODE)`
- `try_relation_open(Oid, LOCKMODE)`
- `relation_openrv(const RangeVar *, LOCKMODE)`
- `relation_openrv_extended(const RangeVar *, LOCKMODE, bool missing_ok)`
- `relation_close(Relation, LOCKMODE)`

## Cross-references

- Behaviour: `knowledge/files/src/backend/access/common/relation.c.md`.

## Confidence tag tally
`[verified-by-code]=1 [from-comment]=0 [from-readme]=0 [inferred]=0 [unverified]=0`
