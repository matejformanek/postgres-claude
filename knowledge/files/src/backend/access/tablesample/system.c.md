# system.c

- **Source path:** `source/src/backend/access/tablesample/system.c`
- **Lines:** 256
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tsmapi.h`, `tablesample.c`, `bernoulli.c`, `executor/nodeSamplescan.c`.

## Purpose

The `SYSTEM` TABLESAMPLE method: block-level sampling. Implements the `TsmRoutine` with callbacks that, given a percentage, hash each block number together with the active seed and include the block iff the hash falls below a cutoff derived from the requested probability. All tuples on a selected block are returned. Produces samples that are repeatable both across scans and across queries (with the same seed). [from-comment, system.c:1-15]

## Top-of-file comment

> "Support routines for SYSTEM tablesample method. To ensure repeatability of samples, it is necessary that selection of a given tuple be history-independent; otherwise syncscanning would break repeatability, to say nothing of logically-irrelevant maintenance such as physical extension or shortening of the relation. To achieve that, we proceed by hashing each candidate block number together with the active seed, and then selecting it if the hash is less than the cutoff value computed from the selection probability by BeginSampleScan." [from-comment, system.c:3-15]

## Public surface

- `tsm_system_handler` (67) — The SQL-callable handler; allocates a `TsmRoutine` node and fills `parameterTypes = list(FLOAT4OID)`, `repeatable_across_queries = true`, `repeatable_across_scans = true`, callbacks wired to the static functions below.
- Static callbacks: `system_samplescangetsamplesize` (88), `system_initsamplescan` (130), `system_beginsamplescan` (139), `system_nextsampleblock` (178), `system_nextsampletuple` (236).

## Key invariants

- Block selection is purely a function of `(blockno, seed)` — no per-scan random state, no consultation of `syncscan.c`. This is what makes samples repeatable across scans. [from-comment, system.c:6-15]
- `system_beginsamplescan` (139) reads the percentage argument, validates 0 ≤ p ≤ 100, stores `cutoff = (uint64) floor((p / 100.0) * PG_UINT64_MAX)` and `seed`. [verified-by-code]
- `system_nextsampleblock` (178) hashes `(blockno, seed)` via `hash_combine64(hash_uint32(seed), hash_uint32(blockno))` and selects iff the result < cutoff. Walks blocks in order starting at `nextblock`. [verified-by-code]
- `system_nextsampletuple` (236) returns EVERY tuple on the selected block (offsets from `lt+1` to `maxoffset`). [verified-by-code]
- `system_samplescangetsamplesize` (88) estimates pages = ceil(p% * relpages), tuples = pages × reltuples/relpages — used by the planner for costing. [verified-by-code]

## Cross-references

- Called from `nodeSamplescan.c::ExecSampleScan`, which itself drives the per-block `am->scan_sample_next_block` / `am->scan_sample_next_tuple` callbacks on the underlying table AM.

## Confidence tag tally
`[verified-by-code]=5 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=0`
