# copyfrom.c

- **Source path:** `source/src/backend/commands/copyfrom.c`
- **Lines:** 1996
- **Last verified commit:** pinned `02f699c14163`, re-verified + re-pinned 2026-06-30 by pg-quality-auditor AUDIT mode after anchor-bump `4abf411e2328..02f699c14163` (triggering commit: a40fdf658862 "Reject child partition FDWs in FOR PORTION OF", Peter Eisentraut — no documented cite region shifted). Previously `ef6a95c7c64`.
- **Companion files:** `copyfromparse.c` (the parser), `copy.c` (options), `commands/trigger.c` (BEFORE INSERT/INSTEAD OF triggers), `executor/execPartition.c` (partition routing), `executor/nodeModifyTable.c` (some shared helpers).

## Purpose

"COPY <table> FROM file/program/client … efficiently load tuples into a table. That includes looking up the correct partition, firing triggers, calling the table AM function to insert the data, and updating indexes. Reading data from the input file or client and parsing it into Datums is handled in copyfromparse.c." [from-comment, copyfrom.c:3-9]

## Public surface

- `BeginCopyFrom` (1535) — open the source (file/program/frontend), initialise `CopyFromState`, set up per-column input function lookups, initialise `ResultRelInfo` for the target (and BEFORE/INSTEAD OF triggers if any). Returns the opaque `CopyFromState`.
- `CopyFrom` (781) — **the main loop**, ~750 lines. For each input row: call format-specific OneRow routine via `cstate->routine->CopyFromOneRow`, possibly route to a partition, run BEFORE triggers, then either insert immediately (slow path) or queue into the multi-insert buffer (fast path).
- `EndCopyFrom` (1938) — close source, release multi-insert buffers, drop `CopyFromState`.
- `ClosePipeFromProgram` (1967) — wait for and check the exit status of a `COPY FROM PROGRAM` subprocess.
- `CopyFromErrorCallback` (256) — `error_context_stack` callback that adds "COPY <relname>, line N, column X" context to any ereport from the parsing layer.
- `CopyFromGetRoutine` (158) — dispatcher returning `&CopyFromTextLikeRoutine`, `&CopyFromBinaryRoutine`, or an extension's routine.
- `CopyMultiInsertInfo*` (~365-780) — the batch-insert machinery (see below).

## Multi-insert fast path [load-bearing performance design]

`CopyFrom`'s hottest loop avoids per-row catalog/index cost by batching. The state lives in two structs (defined in copyfromparse_internal/copyfrom.c near the top): `CopyMultiInsertInfo` (top-level) holds a list of `CopyMultiInsertBuffer`s, one per *result relation* (a partition routing target gets its own buffer). Each buffer accumulates `MAX_BUFFERED_TUPLES` slots (default 1000) and `MAX_BUFFERED_BYTES` (~64 KB) before flush.

Flush (`CopyMultiInsertBufferFlush`, line 448): calls `table_multi_insert` (which heap-AM forwards to `heap_multi_insert`), then for each inserted slot runs the AFTER ROW trigger queue and updates indexes via `ExecInsertIndexTuples`. Indexes are updated *after* the batch hits the heap so that index entries are pre-sorted by physical location, reducing nbtree leaf-page write amplification. [verified-by-code, copyfrom.c:448-621]

The fast path is **bypassed** when any of: (a) the relation has a BEFORE ROW or INSTEAD OF trigger that needs to see the tuple, (b) volatile expressions in defaults force per-row evaluation, (c) the relation is a foreign table (which routes through FDW's `BeginForeignInsert`/`ExecForeignInsert`), (d) any column has a `DOMAIN` with a check constraint that must run per-row in the current pg_proc-language style, or (e) the target table has row-level security or partition routing that requires per-row decisions.

## FREEZE option

`COPY ... WITH (FREEZE)` passes `HEAP_INSERT_FROZEN` into the multi-insert, which marks tuples as already-frozen so VACUUM never needs to revisit them. Pre-conditions enforced at `BeginCopyFrom`: target must have been TRUNCATEd or CREATEd in the current subtransaction, so no concurrent observer could see partially-frozen state. [verified-by-code]

## ON_ERROR / LOG_VERBOSITY (PG 17+)

`ON_ERROR ignore` lets COPY FROM swallow per-row parsing errors and continue, recording the count. `LOG_VERBOSITY verbose` additionally logs each rejection. `REJECT_LIMIT N` caps tolerated failures.

## Confidence tag tally

`[verified-by-code]=5 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
