# FDW IterateForeignScan — pull-next-tuple discipline

The FDW's `IterateForeignScan` callback is the **per-tuple
read path**. It mirrors a normal executor scan node's
`ExecProcNode`: return one TupleTableSlot or an empty slot at
EOF. The implementation owns the connection state, cursor
position, and per-batch buffering; the executor just pulls
slots until EOF.

Anchors:
- `source/src/include/foreign/fdwapi.h:46` —
  IterateForeignScan_function signature [verified-by-code]
- `source/src/include/foreign/fdwapi.h:213-219` — BeginForeignScan /
  IterateForeignScan / ReScanForeignScan / EndForeignScan
  [verified-by-code]
- `knowledge/idioms/fdw-routine-callbacks.md` — companion
- `knowledge/idioms/fdw-direct-modify.md` — companion
- `.claude/skills/extension-development/SKILL.md` — companion

## The signature

[verified-by-code `fdwapi.h:46`]

```c
typedef TupleTableSlot *(*IterateForeignScan_function) (ForeignScanState *node);
```

Returns:
- A TupleTableSlot pointer with the next tuple (typically
  `node->ss.ss_ScanTupleSlot`).
- The same slot with `tts_isempty = true` (or empty via
  `ExecClearTuple`) to signal EOF.

The FDW's state (cursor, batch buffer, remote conn) is
typically stored in `node->fdw_state` — opaque to the executor.

## The lifecycle

```
BeginForeignScan(node, eflags)
    ↓
    open connection, prepare cursor / query
    initialize node->fdw_state
    ↓
[loop:]
IterateForeignScan(node) → slot
    ↓ ... slot consumed by parent node ...
    ↓
IterateForeignScan(node) → slot
    ↓
... eventually returns empty slot ...
    ↓
EndForeignScan(node)
    ↓
    close connection, free state
```

ReScanForeignScan can be called between BeginForeignScan and
EndForeignScan: it resets the cursor / state so the next
IterateForeignScan returns the first tuple again.

## State stored in fdw_state

[from postgres_fdw + file_fdw reference]

Typical per-scan state:
- **Connection handle** to the remote server (libpq for
  postgres_fdw, FILE* for file_fdw).
- **Cursor name** (postgres_fdw uses DECLARE CURSOR).
- **Batch buffer** — pre-fetched tuples to reduce round-trips.
- **Tuple descriptor** for deformation.
- **Query plan deparsed** (postgres_fdw constructs a SQL
  string).

`fdw_state` is allocated in `node->ss.ps.state->es_query_cxt`
or a per-scan child context; freed at EndForeignScan.

## The batch-fetch pattern (postgres_fdw)

postgres_fdw doesn't fetch one row per round trip. It uses
`FETCH N FROM cursor` to pull a batch:

```c
typedef struct PgFdwScanState {
    PGconn  *conn;
    char    *cursor_name;
    int      num_tuples_in_batch;
    HeapTuple *batch;
    int      next_tuple_index;
    /* ... */
} PgFdwScanState;
```

`IterateForeignScan`:
1. If `next_tuple_index < num_tuples_in_batch`: return the
   pre-fetched tuple.
2. Else: issue `FETCH N FROM cursor`, refill the batch,
   return first.
3. If FETCH returned 0 rows: clear slot, return.

The batch size is bounded by the GUC
`fetch_size` (default 100).

## ReScanForeignScan — cursor restart

```c
typedef void (*ReScanForeignScan_function) (ForeignScanState *node);
```

The executor calls this when:
- The outer side of a NestLoop has a new tuple → inner side
  must restart.
- A subquery is re-evaluated due to PARAM_EXEC changes.
- A SubPlan executes again.

postgres_fdw `ReScanForeignScan`:
1. Close the existing cursor (issue `CLOSE cursor`).
2. Re-deparse the query (PARAM values may have changed).
3. Re-declare the cursor with new bound parameters.
4. Reset the batch.

For correctness, the FDW MUST honor the executor's `chgParam`
hint: if the parameters haven't changed, the rescan can skip
the re-DECLARE and just re-fetch from the start of the
existing cursor.

## Async execution path

[per `fdw-routine-callbacks`]

For async-capable FDWs:

```c
ForeignAsyncRequest_function           /* request async fetch */
ForeignAsyncConfigureWait_function     /* set up wait event */
ForeignAsyncNotify_function            /* called when ready */
```

Instead of blocking in IterateForeignScan, the FDW can:
1. Submit an async query (e.g., libpq's `PQsendQuery`).
2. Return a "no tuple yet" signal.
3. The executor (in `Append` async mode) waits for any of
   multiple FDWs to be ready.
4. When ready, `ForeignAsyncNotify` is called; tuples flow.

This is what enables a query against multiple remote PG
servers to read them in parallel without a thread per server.

## EXPLAIN integration

[from-code]

```c
ExplainForeignScan_function ExplainForeignScan;
```

Called during EXPLAIN to add FDW-specific output. For
postgres_fdw, this adds the "Remote SQL: ..." line showing
what query was sent. The hook can also include estimated /
actual round-trips, batch sizes, etc.

## Cleanup at error

If a transaction aborts mid-scan:
1. `EndForeignScan` is NOT called (would only run on normal
   end).
2. The connection / cursor is leaked unless the FDW registers
   a cleanup callback (e.g., via `RegisterResourceReleaseCallback`).

postgres_fdw uses a per-server connection cache + xact
callbacks to ensure cleanup at abort.

## Concurrency

A single FDW scan is single-threaded (one IterateForeignScan
call returns at a time). However:
- Multiple FDW scans across a query can be parallel-safe (via
  parallel callbacks).
- The same backend may have multiple cursors open against the
  same remote.
- Multiple backends with their own FDW scans run independently.

## Common review-time concerns

- **Always check chgParam** in ReScan — re-deparse only if
  necessary.
- **Batch size affects round-trip overhead** — too small =
  too many roundtrips; too big = memory pressure.
- **Cursor names must be unique** within a backend session.
- **EndForeignScan only on normal end** — register xact-abort
  cleanup separately.
- **Slot lifetime** — the returned slot is borrowed; FDW can
  reuse same slot across IterateForeignScan calls.
- **Async opt-in** — adds complexity; only for FDWs with
  long-latency remotes.

## Invariants

- **[INV-1]** IterateForeignScan returns slot or empty slot
  (EOF).
- **[INV-2]** State in node->fdw_state; freed at
  EndForeignScan.
- **[INV-3]** ReScanForeignScan honors chgParam — skip
  re-DECLARE if no param change.
- **[INV-4]** EndForeignScan called only on normal completion;
  abort cleanup via xact callbacks.
- **[INV-5]** Async path uses ForeignAsync* trio; opt-in via
  IsForeignPathAsyncCapable.

## Useful greps

- The interface:
  `grep -n 'IterateForeignScan\|ReScanForeignScan\|BeginForeignScan\|EndForeignScan' source/src/include/foreign/fdwapi.h | head -10`
- postgres_fdw impl:
  `grep -n 'postgresIterateForeignScan\|postgresReScanForeignScan' source/contrib/postgres_fdw/postgres_fdw.c | head -10`
- Executor caller:
  `grep -RIn 'fdwroutine->IterateForeignScan' source/src/backend/executor | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`contrib/postgres_fdw/postgres_fdw.c`](../files/contrib/postgres_fdw/postgres_fdw.c.md) | — | reference implementation |
| [`src/include/foreign/fdwapi.h`](../files/src/include/foreign/fdwapi.h.md) | 46 | IterateForeignScan_function signature |
| [`src/include/foreign/fdwapi.h`](../files/src/include/foreign/fdwapi.h.md) | 213 | BeginForeignScan / IterateForeignScan / ReScanForeignScan / EndForeignScan |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/fdw-routine-callbacks.md` — full
  FdwRoutine context.
- `knowledge/idioms/fdw-direct-modify.md` — bypass per-row
  callbacks for whole-DML.
- `knowledge/data-structures/tupletableslot.md` — slot
  returned by Iterate.
- `knowledge/data-structures/exprcontext.md` — chgParam
  Bitmapset reads here.
- `knowledge/idioms/parallel-worker-coordination.md` —
  parallel FDW scans.
- `knowledge/subsystems/foreign.md` — foreign-tables.
- `.claude/skills/extension-development/SKILL.md` —
  FDW packaging.
- `source/contrib/postgres_fdw/postgres_fdw.c` — reference
  implementation.
