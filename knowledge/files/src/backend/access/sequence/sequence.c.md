# sequence.c

- **Source path:** `source/src/backend/access/sequence/sequence.c`
- **Lines:** 77
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `sequence.h`, `commands/sequence.c` (the actual nextval/setval/currval implementation — much larger), `common/relation.c`.

## Purpose

Two-function file: `sequence_open` and `sequence_close`. These are the SEQUENCE analogue of `table_open` / `table_close` — they call `relation_open` then assert `relkind == RELKIND_SEQUENCE`. The bulk of sequence logic (state, gaplessness, WAL) lives in `commands/sequence.c`, not here. [from-comment, sequence.c:13-17]

## Top-of-file comment

> "Generic routines for sequence-related code… This file contains sequence_ routines that implement access to sequences (in contrast to other relation types like indexes)." [from-comment, sequence.c:13-17]

## Public surface

- `sequence_open` (37) — `relation_open(relationId, lockmode)` + `validate_relation_as_sequence`.
- `sequence_close` (58) — Forwards to `relation_close`.
- `validate_relation_as_sequence` (70, static inline) — Throws `ERRCODE_WRONG_OBJECT_TYPE` ("\"%s\" is not a sequence") for non-SEQUENCE relkind.

## Key invariants

- The whole point of this file's existence (vs. callers using `relation_open` directly) is the typed `errcode` + message for the wrong-relkind case. [verified-by-code, sequence.c:70-77]
- Locking semantics inherit from `relation_open`. [inferred]

## Cross-references

- Almost entirely consumed by `commands/sequence.c::nextval_internal` and friends.

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=1 [from-readme]=0 [inferred]=1 [unverified]=0`
