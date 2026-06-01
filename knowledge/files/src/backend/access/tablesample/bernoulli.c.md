# bernoulli.c

- **Source path:** `source/src/backend/access/tablesample/bernoulli.c`
- **Lines:** 229
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tsmapi.h`, `tablesample.c`, `system.c`, `executor/nodeSamplescan.c`.

## Purpose

The `BERNOULLI` TABLESAMPLE method: per-tuple sampling. Implements `TsmRoutine` with callbacks that include every block (no block-level filter) but, for each tuple, perform an independent Bernoulli trial against the requested probability — selecting tuples iff a hash of `(blockno, offset, seed)` falls below the cutoff. Repeatable across scans and queries with the same seed. [from-comment, bernoulli.c:1-25]

## Top-of-file comment

> "support routines for BERNOULLI tablesample method. As with the SYSTEM sampling method, our goal here is to produce a repeatable sample, ideally regardless of concurrent inserts or deletes." [paraphrased from-comment, bernoulli.c:1-25]

## Public surface

- `tsm_bernoulli_handler` (65) — SQL-callable handler. Sets `parameterTypes = list(FLOAT4OID)`, `repeatable_across_queries = true`, `repeatable_across_scans = true`, NO `NextSampleBlock` callback (NULL → caller walks all blocks).
- Static callbacks: `bernoulli_samplescangetsamplesize` (86), `bernoulli_initsamplescan` (127), `bernoulli_beginsamplescan` (136), `bernoulli_nextsampletuple` (181).

## Key invariants

- `NextSampleBlock` is NULL — meaning `nodeSamplescan.c` walks the WHOLE relation block by block, and per-block calls `bernoulli_nextsampletuple` to decide which offsets to keep. [verified-by-code, bernoulli.c:75-83]
- `bernoulli_nextsampletuple` (181) hashes `(blockno, offset, seed)` and selects iff hash < cutoff. The tuple selection is independent per tuple (Bernoulli). [verified-by-code]
- `bernoulli_beginsamplescan` (136) computes `cutoff = (uint64) floor((p / 100.0) * PG_UINT64_MAX)` from the percentage argument. [verified-by-code]
- `bernoulli_samplescangetsamplesize` (86) estimates pages = relpages (all of them), tuples = p% × reltuples. [verified-by-code]

## Cross-references

- Same consumers as `system.c`.

## Confidence tag tally
`[verified-by-code]=4 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`
