---
name: copy-family
description: Understand and modify the COPY FROM / COPY TO family in PostgreSQL — `src/backend/commands/copy*.c`. Loads when the user asks about COPY-command internals, bulk-load performance, custom COPY formats, extending COPY options, COPY error-handling / ON_ERROR, COPY progress reporting, tablesync (which is built on COPY), or any patch touching `copy.c` / `copyfrom.c` / `copyfromparse.c` / `copyto.c`. Also use when investigating why COPY behaves differently from INSERT (partition routing, defaults, generated columns, extended statistics, RLS, triggers, DEFAULT expressions), and when adding a new bulk-load code path that reuses the COPY machinery. Skip when the question is about `pg_dump` / `psql \copy` (client-side) or logical-replication apply (different subsystem — but note that tablesync's initial copy IS this machinery, see `knowledge/idioms/tablesync-initial-copy.md`).
when_to_load: Extend or debug COPY (options / formats / error-handling); understand how COPY's fast path differs from INSERT (partition routing, defaults, trigger firing); write a bulk-load feature that reuses COPY internals; audit performance of a specific COPY path.
companion_skills:
  - executor-and-planner
  - error-handling
  - catalog-conventions
  - fmgr-and-spi
---

# copy-family — the COPY command internals

The COPY family under `src/backend/commands/copy*.c` implements SQL-level bulk import/export. It's one of PostgreSQL's oldest performance-critical utility statements, sits at a peculiar layer (utility statement with executor-like semantics), and is the machinery logical replication reuses for initial table sync. Getting the file split right matters — patches often touch the wrong one.

## The 4-file split

| File | Lines | Role |
|---|---:|---|
| `copy.c` | 1,142 | Option parsing + dispatch — `DoCopy` entry from `ProcessUtility`, `WITH (...)` extraction, permission checks, relation open with the right lock, then hands off. |
| `copyto.c` | ~1,300 | COPY TO — the output side. Reads tuples from the source (table or query), serializes to text / CSV / binary, writes to file / program / client. |
| `copyfrom.c` | 1,996 | COPY FROM — the input side. Reads parsed rows (from `copyfromparse.c`), routes partitions, fires triggers, inserts through table AM, updates indexes. |
| `copyfromparse.c` | 2,000+ | Format-parsing layer for COPY FROM — text / CSV / binary tokenizers, escape handling, encoding conversion. Turns bytes into Datums. |

The split is deliberate: `copy.c` is the "which direction and with what options" arbiter; `copyto.c` and `copyfrom.c` are the direction-specific engines; `copyfromparse.c` is FROM-only because the TO side doesn't parse (it serializes).

## Entry points

- **`DoCopy` (copy.c:63)** — called by `standard_ProcessUtility` when a `CopyStmt` reaches the utility path. Determines direction, opens the relation with `RowExclusiveLock` (FROM into a table) or `AccessShareLock` (TO from a table), or no relation lock (FROM/TO a query), then invokes:
  - COPY FROM: `BeginCopyFrom` → `CopyFrom` (the row loop) → `EndCopyFrom`.
  - COPY TO: `BeginCopyTo` → `DoCopyTo` (the row loop) → `EndCopyTo`.
- **`BeginCopyFrom` (copyfrom.c)** — validates the target relation, opens files/programs/pipes, sets up the executor state for BEFORE-INSERT triggers and defaults, initializes the format parser via callbacks.
- **`NextCopyFrom` (copyfromparse.c)** — one row at a time from the input; format-specific.

## What makes COPY *different* from INSERT

Reviewers new to COPY often ask "why isn't this just INSERT under the hood?" — reasons:

1. **Custom parse layer** — `copyfromparse.c` bypasses the SQL parser entirely. Text/CSV/binary formats are tokenized in-place with no query-tree round-trip.
2. **Multi-insert batching** — `copyfrom.c` groups rows into `CopyMultiInsertBuffer`s per partition and calls `heap_multi_insert` (bulk WAL, less per-row overhead).
3. **Partition routing without executor** — COPY does its own tuple-routing via `ExecFindPartition` but manages the partition-relation cache manually.
4. **Default evaluation is opt-in** — DEFAULT columns are computed only if not present in the input column list; a client can send an explicit NULL and get NULL, not the DEFAULT.
5. **Triggers fire, but no rewriter** — BEFORE and AFTER INSERT triggers run; INSTEAD OF triggers on views run; but rewrite rules do NOT (COPY is utility-level).
6. **ON_ERROR / REJECT LIMIT** — since PG 17, per-row parse errors can be soft-failed instead of aborting the whole load.

## The COPY option surface (post-PG-17)

Every `WITH (option value, ...)` clause is parsed in `copy.c`'s `ProcessCopyOptions`. Notable extractors:

- `defGetCopyHeaderOption` (copy.c:396) — HEADER: `false` / `true` / `match` (PG 16+ — match requires column names).
- `defGetCopyOnErrorChoice` (copy.c:479) — ON_ERROR: `stop` (default) / `ignore` (skip bad rows).
- `defGetCopyRejectLimitOption` (copy.c:514) — REJECT_LIMIT N — max rows to skip before aborting.
- `defGetCopyLogVerbosityChoice` (copy.c:541) — LOG_VERBOSITY: `default` / `verbose` — controls per-error logging.

Adding a new option: extend the `CopyFormatOptions` struct in `copy.h`, add a `defGet*` extractor in `copy.c`, wire it in `ProcessCopyOptions`, thread it through to `copyfrom.c` / `copyto.c` / `copyfromparse.c` as needed, plus documentation (`doc/src/sgml/ref/copy.sgml`).

## Common patch shapes

- **New COPY option** — see above. Includes a `pg_dump` sync if the option is one dump might emit.
- **New format** (rare) — currently text / CSV / binary. A new format needs a `CopyFromRoutine` / `CopyToRoutine` callback table (see `copyapi.h`) and format-dispatch changes in `BeginCopyFrom` / `BeginCopyTo`.
- **Progress reporting** — COPY exposes `pgstat_progress_update_param(PROGRESS_COPY_*, ...)` at each step. New progress fields go in `src/include/commands/progress.h`.
- **Extension AMs / custom insert paths** — the multi-insert path is table-AM-agnostic via `tuple_multi_insert`. Adding a table AM should work with COPY out of the box unless the AM has non-heap-like batching constraints.

## Related corpus

- **Idioms**: `tablesync-initial-copy` (logical replication uses COPY internally), `partition-tuple-routing` (COPY does its own routing).
- **File docs**: `knowledge/files/src/backend/commands/copy.c.md`, `copyfrom.c.md`, `copyto.c.md`, `copyfromparse.c.md`.
- **Related subsystems**: `executor` (for the row-loop model + trigger firing), `partitioning` (for partition routing).
- **Utility path context**: `knowledge/subsystems/tcop.md` — where `standard_ProcessUtility` sits.

## Pitfalls

- **`copyfrom.c` vs `copyfromparse.c` confusion** — the SQL-level "which row to insert next" logic lives in `copyfrom.c`; the byte-to-Datum layer lives in `copyfromparse.c`. New format code goes in `copyfromparse.c`; new tuple-flow logic goes in `copyfrom.c`.
- **`copyto.c` shares little with `copyfrom.c`** — despite the naming pair, the code paths are largely disjoint. Don't assume a change in one has an analog in the other.
- **`copyapi.h` is the extension seam** — external code adding new COPY formats should target `CopyFromRoutine` / `CopyToRoutine`, not modify `copyfromparse.c` directly.
- **Trigger firing is direction-asymmetric** — COPY FROM fires triggers per row; COPY TO does not fire any triggers.
- **BulkInsertState** — the multi-insert accelerator is opt-in per relation and holds a shared buffer strategy; if you add a code path that inserts via COPY internals, be aware of `RelationGetBulkInsertState` (in `heapam.c`).
- **ON_ERROR interacts with soft-error handling** (`softerrs.c`) — the machinery there was added specifically to make ON_ERROR work without aborting the transaction.

## Corpus-chain shortcut

For a live map of what a COPY-related change touches:

```
python3 scripts/corpus-chain.py --file src/backend/commands/copyfrom.c
```

This surfaces the idioms whose Call sites include `copyfrom.c`, the scenarios (if any) that touch it, and the owning subsystem — the "chained-link connection" this skill's parent goal describes.

## Boundary

**Use this skill** when working with the `copy*.c` backend files. **Don't use** for:
- `psql \copy` — that's a client-side feature in `src/bin/psql/copy.c`, a wholly separate implementation.
- `pg_dump` — uses its own SQL-level `COPY` invocations; `src/bin/pg_dump/`.
- `BULK LOAD` — no such thing in PostgreSQL; COPY IS the bulk-load mechanism.
