# sequence.c

- **Source path:** `source/src/backend/commands/sequence.c`
- **Lines:** 1915
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `sequence_xlog.c` (WAL redo, split out in PG 18+), `access/sequence/` (sequence access-method abstraction), `catalog/pg_sequence.h`.

## Purpose

CREATE / ALTER / DROP SEQUENCE, plus `nextval()` / `currval()` / `setval()` / `lastval()` SQL functions and SEQUENCE redo.

## Public surface

- `DefineSequence`, `AlterSequence`, `ResetSequence`, `DeleteSequenceTuple` — DDL plus the `OWNED BY` link to a column.
- `nextval`, `nextval_oid`, `nextval_internal` — increment and return. Uses a per-backend log-counter trick: each backend allocates `SEQ_LOG_VALS` (32) values from the sequence under WAL but only WALs every 32nd one. On crash, the next-after-crash value can be up to 32 ahead — that's why a clean shutdown vs crash makes sequences appear to skip.
- `currval`, `lastval`, `setval` — straightforward.
- `seq_redo` — handles `XLOG_SEQ_LOG`; replaces the sequence relation's single page.
- `pg_sequence_parameters`, `pg_sequence_last_value` — SQL introspection helpers.

## Each sequence is a 1-page table

A sequence's heap is one 8 KB page with one tuple of type `pg_sequence_data` (`last_value bigint, log_cnt bigint, is_called bool`). The relfilenode is a real heap; nextval takes a buffer-content lock on that page, mutates the tuple in-place, WAL-logs if `log_cnt == 0`, then resets `log_cnt = SEQ_LOG_VALS - 1`. **This is why a sequence under contention is a hot spot** — all backends serialise on that one page's exclusive content lock.

## Confidence tag tally

`[verified-by-code]=4 [inferred]=1`
