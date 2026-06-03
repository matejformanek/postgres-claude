---
path: src/interfaces/libpq/fe-exec.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 4745
depth: deep
---

# fe-exec.c

- **Source path:** `source/src/interfaces/libpq/fe-exec.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 4745
- **Companion files:** `libpq-int.h` (PGresult, PGconn, PGcmdQueueEntry, PGEvent), `fe-protocol3.c` (`pqParseInput3` writes into `conn->result`), `fe-misc.c` (pqPutMsgStart/End, pqFlush, pqReadData), `fe-print.c` (older PQprint result printer)

## Purpose

Client-side query mechanics. Owns:

1. `PGresult` allocation/free + the chunked allocator backing it.
2. Command dispatch: `PQexec`/`PQexecParams`/`PQprepare`/`PQexecPrepared` (sync wrappers around the async `PQsendQuery*` family).
3. The async event loop: `PQsendQuery*` → `PQconsumeInput` → `PQisBusy` → `PQgetResult`.
4. The command queue (`PGcmdQueueEntry`) — drives pipeline mode + tracks per-message query class.
5. Pipeline mode: `PQenterPipelineMode`, `PQpipelineSync`, `PQsendFlushRequest`, `PQexitPipelineMode`.
6. COPY: `PQputCopyData`, `PQputCopyEnd`, `PQgetCopyData`, plus the deprecated `PQgetline`/`PQputline`/`PQendcopy`.
7. Single-row / chunked-rows mode toggles: `PQsetSingleRowMode`, `PQsetChunkedRowsMode`.
8. Result inspection: `PQntuples`, `PQnfields`, `PQgetvalue`, `PQgetisnull`, `PQfname`, `PQftype`, `PQfmod`, `PQfsize`, `PQfformat`, `PQftable`, `PQftablecol`, `PQbinaryTuples`, `PQcmdStatus`, `PQoidValue`, `PQoidStatus`, `PQcmdTuples`, `PQparamtype`, `PQnparams`.
9. Notifications: `PQnotifies`, `PQfreeNotify`.
10. String escaping: `PQescapeString`, `PQescapeStringConn`, `PQescapeLiteral`, `PQescapeIdentifier`, `PQescapeBytea`, `PQescapeByteaConn`, `PQunescapeBytea`.
11. The legacy "fast-path function call" interface: `PQfn`, `PQnfn`.

## Public API surface

Tier 1 — execution wrappers (blocking):

| Function | Line | Purpose |
|---|---|---|
| `PQexec` | 2279 | Send simple-protocol Query, wait for all results, return final. |
| `PQexecParams` | 2293 | Extended-protocol with parameters, single round-trip group. |
| `PQprepare` | 2323 | Parse a named statement, wait for ParseComplete → PGresult. |
| `PQexecPrepared` | 2340 | Bind+Execute against a prepared name. |
| `PQdescribePrepared`/`PQdescribePortal` | 2472, 2491 | Describe round-trip. |
| `PQclosePrepared`/`PQclosePortal` | 2538, 2556 | Close a named statement/portal. |

Tier 2 — async send (return 1 success, 0 fail; result via PQgetResult):

| Function | Line | Purpose |
|---|---|---|
| `PQsendQuery` | 1433 | Simple-protocol async. |
| `PQsendQueryContinue` | 1439 | Used inside pipeline mode for subsequent commands. |
| `PQsendQueryParams` | 1509 | Extended-protocol async. |
| `PQsendPrepare` | 1553 | Parse only. |
| `PQsendQueryPrepared` | 1650 | Bind+Execute. |
| `PQsendDescribePrepared`/`PQsendDescribePortal` | 2508, 2521 | Async Describe. |
| `PQsendClosePrepared`/`PQsendClosePortal` | 2573, 2586 | Async Close. |
| `PQsendFlushRequest` | 3402 | Send a Flush message (pipeline). |
| `PQsendPipelineSync` | 3313 | Async variant of PQpipelineSync. |

Tier 3 — driving the async machinery:

| Function | Line | Purpose |
|---|---|---|
| `PQconsumeInput` | 2001 | Read any available bytes into `conn->inBuffer`. |
| `PQisBusy` | 2048 | True if not enough data for a complete result yet. |
| `PQgetResult` | 2079 | Pop the next ready PGresult; NULL when done. |
| `PQsetnonblocking`/`PQisnonblocking` | 3980, 4019 | Toggle non-blocking I/O on the conn. |
| `PQflush` | 4036 | Try to flush conn->outBuffer. |

Tier 4 — COPY:

| Function | Line | Purpose |
|---|---|---|
| `PQputCopyData` | 2712 | Send a COPY data row buffer. |
| `PQputCopyEnd` | 2766 | Finish COPY-from (NULL = success, else `CopyFail` with msg). |
| `PQgetCopyData` | 2833 | Pull next COPY-to row. |
| `PQgetline`/`PQgetlineAsync`/`PQputline`/`PQputnbytes`/`PQendcopy` | 2871, 2918, 2935, 2945, 2966 | Deprecated text-COPY interface. |

Tier 5 — pipeline:

| Function | Line | Purpose |
|---|---|---|
| `PQenterPipelineMode` | 3073 | Switch to pipeline; refuses if any in-flight. |
| `PQexitPipelineMode` | 3104 | Switch back; must be idle. |
| `PQpipelineSync` | 3303 | Blocking sync. |
| `PQpipelineStatus` | (fe-connect.c:7786) | Read current pipeline state. |

Tier 6 — result inspection (all const-correct, return owned-by-PGresult pointers):

`PQresultStatus` 3442, `PQresStatus` 3450, `PQresultErrorMessage` 3458, `PQresultVerboseErrorMessage` 3466, `PQresultErrorField` 3497, `PQntuples` 3512, `PQnfields` 3520, `PQbinaryTuples` 3528, `PQfname` 3598, `PQfnumber` 3620, `PQftable` 3717, `PQftablecol` 3728, `PQfformat` 3739, `PQftype` 3750, `PQfsize` 3761, `PQfmod` 3772, `PQcmdStatus` 3783, `PQoidStatus` 3796, `PQoidValue` 3824, `PQcmdTuples` 3853, `PQgetvalue` 3907, `PQgetlength` 3919, `PQgetisnull` 3934, `PQnparams` 3949, `PQparamtype` 3961.

Tier 7 — memory / lifecycle:

`PQmakeEmptyPGresult` 160, `PQsetResultAttrs` 250, `PQcopyResult` 319, `PQsetvalue` 453, `PQresultAlloc` 544, `PQresultMemorySize` 669, `PQclear` 727, `PQfreemem` 4068, `PQfreeNotify` 4085, `PQsetSingleRowMode` 1965, `PQsetChunkedRowsMode` 1982.

Tier 8 — escaping:

`PQescapeStringConn` 4213, `PQescapeString` 4235, `PQescapeLiteral` 4418, `PQescapeIdentifier` 4424, `PQescapeByteaConn` 4595, `PQescapeBytea` 4611, `PQunescapeBytea` 4636.

Tier 9 — legacy `fn` (large-object backend bridge):

`PQfn` 2997, `PQnfn` 3016. Used by `fe-lobj.c`. Documented as legacy.

## Internal landmarks

### PGresult memory layout

PGresult is allocated in a private chunked arena (`PGresult_data` blocks of `PGRESULT_DATA_BLOCKSIZE = 2048`, with `PGRESULT_SEP_ALLOC_THRESHOLD` triggering a per-allocation `malloc` for big strings). [verified-by-code, fe-exec.c:140-148, 543-666] `PQclear` walks `res->curBlock` (singly linked list of blocks) and frees each, then frees the tuples array, then the result itself. There is a sentinel **`OOM_result`** — a static const PGresult with `resultStatus=PGRES_FATAL_ERROR, errMsg="out of memory\n"` returned when malloc fails. `PQclear` recognizes it and no-ops. [verified-by-code, fe-exec.c:149-154, 733-737]

### Command queue (pipeline backbone)

`PGcmdQueueEntry` (libpq-int.h) holds: queryclass (`PGQUERY_SIMPLE`/`EXTENDED`/`PREPARE`/`DESCRIBE`/`SYNC`/`CLOSE`), `query` string, and a `next` pointer. Helpers here:

- `pqAllocCmdQueueEntry` (1323) — pull from free-list `conn->cmd_queue_recycle` or malloc.
- `pqAppendCmdQueueEntry` (1356) — link onto `conn->cmd_queue_tail`; if pipeline is idle and no head exists, also kick `pqPipelineProcessQueue` (3211).
- `pqRecycleCmdQueueEntry` (1403) — return to free-list.
- `pqCommandQueueAdvance` (3173) — called from `pqParseInput3` on ReadyForQuery (Sync boundary), pops the head into the recycle list.

### Async state — PGAsyncStatusType

(Defined in libpq-int.h:216-227, fe-protocol3.c references it constantly.)

```
PGASYNC_IDLE              no query
PGASYNC_BUSY              query sent, awaiting results
PGASYNC_READY             a result is built and waiting for PQgetResult
PGASYNC_READY_MORE        a result is ready, but more will follow (single-row/chunked)
PGASYNC_COPY_IN/OUT/BOTH  copy mode
PGASYNC_PIPELINE_IDLE     idle between commands in pipeline mode
```

`PQgetResult` (2079) is the consumer: it loops while `asyncStatus == BUSY` calling `parseInput` (which calls `pqParseInput3`) and `pqReadData`. When `READY` it calls `pqPrepareAsyncResult` (857) to detach `conn->result` and return it; the conn flips back to `BUSY` (more data coming) or `IDLE`. [verified-by-code, fe-exec.c:2078-2238]

### PQexec lifecycle

```
PQexec / PQexecParams / PQprepare / PQexecPrepared
  ↓
PQexecStart (2361)   resets error state, drains any pending results,
                    ensures asyncStatus==IDLE before issuing
  ↓
PQsendQuery* (1432-1773)
  ↓
PQexecFinish (2427)  loops PQgetResult, returning the LAST non-NULL result
                    (with the side effect of clearing any earlier ones)
```

The "return the last result" rule is why `PQexec` only ever returns one PGresult even when a multi-statement query string produces several. For multi-statement results, the async path (`PQsendQuery` + `PQgetResult` loop) is required.

### Pipeline mode

State machine on `conn->pipelineStatus`: `PQ_PIPELINE_OFF` → `PQ_PIPELINE_ON` (via `PQenterPipelineMode`) → `PQ_PIPELINE_ABORTED` (set by `pqGetErrorNotice3` when an error arrives mid-pipeline). The aborted state survives until the next `PQpipelineSync`. Commands issued in aborted state still queue and still get a PGresult, but it's `PGRES_PIPELINE_ABORTED`. The Sync re-arms. [verified-by-code, fe-exec.c:3072-3401, plus fe-protocol3.c:903-906]

### Row processor

`pqRowProcessor` (1223) is the per-DataRow callback called from `getAnotherTuple` in fe-protocol3.c. It either appends to `res->tuples[]` (normal mode) or, when single-row / chunked mode is on, packages the row as a standalone `PGRES_SINGLE_TUPLE` / `PGRES_TUPLES_CHUNK` result and stashes a fresh result for the next batch.

### Escaping

`PQescapeStringInternal` (4107) — used by both connection-aware and standalone variants. Path:

1. Fast ASCII: `SQL_STR_DOUBLE(c, !std_strings)` decides whether the char needs doubling (always for `'`; `\\` only if `std_strings` is off).
2. Slow multibyte path: `pg_encoding_mblen_or_incomplete` → `pg_encoding_verifymbchar`. **Crucially**, invalid mb sequences are replaced with a deliberately invalid sequence so the server will reject the query — never silently passed through. This blocks the classic "skip-over-quote via partial multibyte" injection. [from-comment, fe-exec.c:4145-4180]
3. Buffer rule: `to` must be at least `2*length + 1` bytes. Comment explicitly guarantees the worst-case is `2*length`.

`PQescapeInternal` (4250) — common code for `PQescapeLiteral` (quotes a literal with `'…'`) and `PQescapeIdentifier` (quotes an identifier with `"…"`). Newly-allocated buffer; caller frees with `PQfreemem`. Returns NULL on encoding error.

`PQescapeByteaInternal` (4471) — outputs `\x…` hex form if server ≥ 9.0 and using std_strings, else `\\NNN` octal form for backward compat. [verified-by-code, fe-exec.c:4470-4593]

`PQunescapeBytea` (4636) — accepts either `\xHEX` or legacy octal; **bad input is silently ignored**, including whitespace between hex pairs (matching `byteain` server-side). [from-comment, fe-exec.c:4669-4675]

## Invariants & gotchas

- **`PGresult` ownership: caller owns it.** Every PQexec\* / PQgetResult result must be freed with `PQclear`. Forgetting is a memory leak. The `OOM_result` static is the one exception: `PQclear` no-ops on it. [verified-by-code, fe-exec.c:733-737]
- **Pointers returned by `PQgetvalue`, `PQfname`, etc. live inside the PGresult.** They become invalid after `PQclear`. Multi-byte safe (NUL-terminated), but text/binary distinction is per-column (`PQfformat`).
- **`PQexec` returns the LAST result of a multi-statement string** — earlier results are silently `PQclear`'d. Use `PQsendQuery` + `PQgetResult` to see them all. [verified-by-code, fe-exec.c:2427-2470]
- **In pipeline mode, every command produces a result**, including each Sync (which produces `PGRES_PIPELINE_SYNC`). The application must consume all of them; otherwise the queue desyncs and the next non-pipeline op fails.
- **`PQsetnonblocking(conn, 1)` does NOT make `PQexec*` non-blocking** — the wrappers still loop. It only affects raw send paths. The intended way to be non-blocking is `PQsendQuery` + `PQflush` + `PQconsumeInput` + `PQisBusy`. [verified-by-code, fe-exec.c:3979-4035]
- **`PQescapeString` (no `Conn`) uses static globals `static_client_encoding` / `static_std_strings`** initialized to `SQL_ASCII` + `false` (legacy-compat defaults). This is **unsafe** for non-ASCII data on a server with `standard_conforming_strings = on` (the modern default). Always prefer `PQescapeStringConn` / `PQescapeLiteral` / `PQescapeIdentifier`. [from-comment, fe-exec.c:4234-4248] (Note the static globals are updated whenever `pqSaveParameterStatus` notices a relevant ParameterStatus message — but that's per-PROCESS, last-conn-wins. Race surface in multi-conn programs.)
- **`PQescapeStringInternal` on invalid multibyte returns a poison sequence, sets `error=1`, but still produces output.** Callers should check `*error` and refuse to send; the comment notes this exists "in case the caller ignores it" to make the resulting string syntactically broken server-side. Defense in depth against SQL injection via bogus encodings. [from-comment, fe-exec.c:4156-4180]
- **`PQexec` clears `conn->errorMessage` only when no command is queued.** In pipeline mode where commands are queued behind earlier ones, error state belongs to the earlier command and is preserved. [from-comment, fe-exec.c:2369-2375]
- **`PQclear(NULL)` is safe.** Documented; many callers rely on this. [verified-by-code, fe-exec.c:733-737]
- **`PQfreemem` exists specifically for Windows** — `PQescapeBytea` / `PQnotifies` / etc. return memory allocated by libpq's CRT, which may not match the app's CRT. Always use `PQfreemem`, never `free`. [from-comment, fe-exec.c:4067-4084]
- **Result-row format is per-column.** `PQbinaryTuples` returns 1 only if ALL columns are binary; mixed-format results return 0. Check per-column via `PQfformat`. [verified-by-code, fe-exec.c:3527-3539, 3738-3748]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-connect.c.md` — connection lifecycle that feeds the async state PQexec inhabits.
- `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md` — the message-byte dispatcher that fills `conn->result`.
- `knowledge/files/src/interfaces/libpq/fe-misc.c.md` — `pqPutMsgStart`/`pqPutMsgEnd`/`pqFlush`/`pqReadData` plumbing.
- `knowledge/files/src/interfaces/libpq/fe-lobj.c.md` — sole serious caller of `PQfn`.
- Backend counterparts: `knowledge/files/src/backend/tcop/postgres.c.md` (exec_simple_query / exec_execute_message dispatch), `knowledge/files/src/backend/access/common/printtup.c.md` (server-side row formatting).

## Potential issues

- **[ISSUE-leak: `PQescapeString` reads process-global encoding state]** fe-exec.c:4234-4248, 56-60 — `static_client_encoding` / `static_std_strings` are set per-PROCESS by the most recent connection's `pqSaveParameterStatus`. In a multi-connection app where conn A is `latin1` and conn B is `utf8`, calling `PQescapeString` after conn B's params arrive will use utf8 for data destined for conn A. **Severity: likely (data corruption / injection vector).** The fix is "always use `PQescapeStringConn`", but the unsafe variant remains in the ABI. Documented; flag for any libpq tutorial / linter audit.
- **[ISSUE-correctness: `PQunescapeBytea` silently drops bad input]** fe-exec.c:4669-4677 — hex pairs with whitespace are silently accepted, single hex digits silently dropped. Mirrors `byteain` semantics but means an integrity check based on "round-trip through PQunescapeBytea/PQescapeBytea matches" can succeed on corrupted input. **Severity: maybe.**
- **[ISSUE-undocumented-invariant: row-processor errmsg ownership]** `pqRowProcessor` (1223) sets `*errmsgp` to a caller-visible message on failure. The string ownership rules (constant vs allocated) aren't fully documented at the call site in fe-protocol3.c. Code paths that don't set errmsg get a default "out of memory for query result". **Severity: nit.**
- **[ISSUE-question: pipeline aborted state and partial consumption]** fe-exec.c:3072-3401 — if the app calls `PQgetResult` until NULL in pipeline mode, it should see one `PGRES_PIPELINE_ABORTED` per queued command plus a `PGRES_PIPELINE_SYNC`. Verify the count matches in error-mid-pipeline scenarios; mismatches cause queue desync. Worth a focused TAP test.
- **[ISSUE-stale-todo: `PQfn` / `PQnfn` only used by `fe-lobj.c`]** fe-exec.c:2996-3070 — the fast-path function-call interface is documented (in the head comment of `PQfn`) as legacy. Could be deprecated once large-object support migrates to extended-query proper. **Severity: nit.**
- **[ISSUE-correctness: `dupEvents` memory accounting]** fe-exec.c:409-451 — when copying PGEvents across `PQcopyResult`, `memSize` is accumulated for `PQresultMemorySize`. Verify it accounts for the `event->name` strdup as well as the struct. **Severity: nit.**
- **[ISSUE-undocumented-invariant: `PQresultErrorField(NULL, code)` returns NULL silently]** fe-exec.c:3497-3510 — same for most `PQresult*` accessors. Documented near top of file but easy to miss; many production crashes are "called accessor on NULL result". **Severity: nit.**
- **[ISSUE-leak: error-message escape sequences in `PQerrorMessage`]** Any server-supplied error text flows through to `conn->errorMessage` raw. Apps that log this to terminals / HTML get a XSS / terminal-injection surface. Phase D should consider sanitization at the libpq-fe boundary or document the caller's burden. **Severity: maybe.**

## Tally

`[verified-by-code]=16 [from-comment]=10 [from-readme]=0 [inferred]=0 [unverified]=1`
