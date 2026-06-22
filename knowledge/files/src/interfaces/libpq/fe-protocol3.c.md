---
path: src/interfaces/libpq/fe-protocol3.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 2553
depth: deep
---

# fe-protocol3.c

- **Source path:** `source/src/interfaces/libpq/fe-protocol3.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 2553
- **Companion files:** `libpq-int.h` (PGconn, PGresult, async-status enums, query-class enums), `fe-misc.c` (`pqGet*` byte-level primitives), `fe-exec.c` (consumes the `conn->result` this file builds, `pqRowProcessor`, `pqSaveErrorResult`, `pqClearAsyncResult`, `pqPrepareAsyncResult`, `pqSaveParameterStatus`), `protocol.h`/`libpq/protocol.h` (`PqMsg_*` byte constants — the wire protocol)

## Purpose

The client-side message dispatcher for protocol version 3 (the only protocol supported since PG 7.4). Every byte that arrives from the server lands in `conn->inBuffer`; this file pulls structured protocol messages out and turns them into PGresult state transitions. Symmetric to `src/backend/tcop/postgres.c`'s server-side dispatch.

Three primary entry points:

1. **`pqParseInput3`** (70) — the main loop. Called from `parseInput` in fe-exec.c whenever `PQconsumeInput` or `PQgetResult` think there might be new bytes. Loops until the buffer doesn't have a complete message.
2. **`pqGetErrorNotice3`** (898) — parse an Error or Notice response. Builds a PGresult with field codes filled in (SQLSTATE, message, detail, hint, severity, position, …) and either reports it as a notice (via `noticeHooks.noticeReceiver`) or installs it as `conn->result`.
3. **`pqFunctionCall3`** (2207) — implements the legacy fast-path Function Call protocol, used by `fe-lobj.c`. Sends a 'F' message and parses the 'V' response.

Plus internal helpers for each message type: `getRowDescriptions`, `getParamDescriptions`, `getAnotherTuple`, `getNotify`, `getParameterStatus`, `getBackendKeyData`, `getCopyStart`, `getCopyDataMessage`, `getReadyForQuery`, `pqGetNegotiateProtocolVersion3`, `pqGetCopyData3`, `pqGetline3`, `pqGetlineAsync3`, `pqEndcopy3`. And the startup-side `pqBuildStartupPacket3` / `build_startup_packet`.

## Public/internal API surface

(All "public" to other libpq files, none in the PQ\* ABI directly except as a behavior described by PQexec/PQgetResult.)

| Function | Line | Purpose |
|---|---|---|
| `pqParseInput3` | 70 | Main dispatch loop. |
| `handleFatalError` | 487 | Abandon conn after a non-recoverable error. |
| `handleSyncLoss` | 503 | Lost protocol sync — close the connection. |
| `getRowDescriptions` | 518 | Parse 'T' RowDescription → fill `result->attDescs`. |
| `getParamDescriptions` | 689 | Parse 't' ParameterDescription → fill `result->paramDescs`. |
| `getAnotherTuple` | 777 | Parse 'D' DataRow → call `pqRowProcessor`. |
| `pqGetErrorNotice3` | 898 | Parse 'E'/'N' ErrorResponse/NoticeResponse. |
| `pqBuildErrorMessage3` | 1030 | Format an error PGresult's fields into a human string per `PQerrorVerbosity` setting. |
| `reportErrorPosition` | 1201 | Insert a `^`-pointing caret line under the offending query token. |
| `pqGetNegotiateProtocolVersion3` | 1443 | Parse 'v' NegotiateProtocolVersion (proto minor version downgrade). |
| `getParameterStatus` | 1590 | Parse 'S' ParameterStatus → `pqSaveParameterStatus`. |
| `getBackendKeyData` | 1621 | Parse 'K' BackendKeyData → store be_pid + be_cancel_key. |
| `getNotify` | 1685 | Parse 'A' NotificationResponse → enqueue `PGnotify`. |
| `getCopyStart` | 1756 | Parse 'G'/'H'/'W' CopyIn/Out/BothResponse → set COPY state. |
| `getReadyForQuery` | 1812 | Parse 'Z' ReadyForQuery → advance command queue. |
| `getCopyDataMessage` | 1844 | Inner-loop reader for 'd' CopyData. |
| `pqGetCopyData3` | 1949 | Consumer-facing: pull next COPY row. |
| `pqGetline3` | 2008 | Legacy text-COPY line reader. |
| `pqGetlineAsync3` | 2059 | Async variant. |
| `pqEndcopy3` | 2114 | Finalize COPY. |
| `pqFunctionCall3` | 2207 | Function-call (`'F'`) message round-trip; used by fe-lobj. |
| `pqBuildStartupPacket3` | 2448 | Build StartupMessage / SSLRequest / GSSENCRequest packets. |
| `build_startup_packet` | 2479 | Workhorse — runs twice, once to measure, once to fill. |

## Internal landmarks

### Main loop (`pqParseInput3`, line 70)

For every iteration:

```
1. inCursor = inStart                       // rewind for clean partial-message recovery
2. pqGetc(&id)                              // 1-byte message type
3. pqGetInt(&msgLength, 4)                  // 4-byte length-including-length-word
4. if msgLength < 4:        handleSyncLoss  (unrecoverable — close conn)
5. if msgLength > 30000 && !VALID_LONG_MESSAGE_TYPE(id):  handleSyncLoss
6. if buffer doesn't yet hold msgLength bytes: pqCheckInBufferSpace and return
7. dispatch on (asyncStatus, id)
```

`VALID_LONG_MESSAGE_TYPE` is defined at the top of fe-protocol3.c itself (not libpq-int.h, as an earlier draft of this doc claimed) and limits the "huge message" allowance to message types that are legitimately large (DataRow, RowDescription, CopyData, ErrorResponse, NoticeResponse, FunctionCallResponse, NotificationResponse, and — since commit `e0511883cae2` — ParameterDescription, so a `PQdescribePrepared` result describing >7498 parameters can exceed the 30 KB cap). Other message types capped at 30000 bytes — this is the **client-side defense against a runaway server message length**. [verified-by-code, fe-protocol3.c:38-46 (macro), :102 (usage gate) @ e0511883cae2]

### Dispatch matrix

The outer dispatch on `asyncStatus`:

- **`id == 'A' (NotificationResponse)`** — always processed (notify can arrive any time).
- **`id == 'N' (NoticeResponse)`** — always processed.
- **`asyncStatus != PGASYNC_BUSY`** — special handling:
  - `IDLE` and `id == 'E'`: treat as notice (server probably about to close conn). [fe-protocol3.c:178-182]
  - `IDLE` and `id == 'S'`: process ParameterStatus (SIGHUP-driven GUC change). [fe-protocol3.c:183-187]
  - `IDLE` and anything else: warn-and-skip via `pqInternalNotice`.
  - Not IDLE (e.g. READY): return without consuming — wait for app to drain.
- **`asyncStatus == PGASYNC_BUSY`** — full switch on `id`:
  - `PqMsg_CommandComplete` ('C'): build PGRES_COMMAND_OK, status → READY.
  - `PqMsg_ErrorResponse` ('E'): build error result, status → READY.
  - `PqMsg_ReadyForQuery` ('Z'): if pipeline, build PGRES_PIPELINE_SYNC; else `pqCommandQueueAdvance` + status → IDLE.
  - `PqMsg_EmptyQueryResponse` ('I'): PGRES_EMPTY_QUERY, READY.
  - `PqMsg_ParseComplete` ('1'): for PGQUERY_PREPARE produces PGRES_COMMAND_OK; otherwise ignored.
  - `PqMsg_BindComplete` ('2'): always ignored.
  - `PqMsg_CloseComplete` ('3'): for PGQUERY_CLOSE produces PGRES_COMMAND_OK; otherwise ignored.
  - `PqMsg_ParameterStatus` ('S'): update internal map.
  - `PqMsg_BackendKeyData` ('K'): store be_pid + cancel key.
  - `PqMsg_RowDescription` ('T'): start a new PGRES_TUPLES_OK result; if a result is already in progress, set status → READY (new T means new result group).
  - `PqMsg_NoData` ('n'): for PGQUERY_DESCRIBE produces PGRES_COMMAND_OK; else ignored.
  - `PqMsg_ParameterDescription` ('t'): fill `result->paramDescs`.
  - `PqMsg_DataRow` ('D'): row processor.
  - `PqMsg_CopyInResponse`/`CopyOutResponse`/`CopyBothResponse` ('G'/'H'/'W'): set COPY status.
  - `PqMsg_CopyData` ('d'): silently dropped here (only relevant in COPY state).
  - `PqMsg_CopyDone` ('c'): silently dropped (normal during PQendcopy).
  - **default**: protocol-violation → build error PGresult, status → READY, advance past the unknown message.

[verified-by-code, fe-protocol3.c:201-475]

### Validate-length-vs-cursor (line 460-475)

After dispatch, sanity check `inCursor == inStart + 5 + msgLength`. If parser consumed too few/too many bytes, build a "message contents do not agree with length" error, set READY, and use `msgLength` as the authoritative skip distance to resync. This is the **last line of defense** against parser bugs corrupting the byte stream.

### `pqGetErrorNotice3` (898)

Loops over field codes ('S', 'V', 'C', 'M', 'D', 'H', 'P', 'p', 'q', 'W', 's', 't', 'c', 'd', 'n', 'F', 'L', 'R'), accumulates them in a `PGresult->errFields` linked list via `pqSaveMessageField`. After all fields parsed, calls `pqBuildErrorMessage3` to format the user-facing string per `conn->verbosity` (`PQERRORS_TERSE`/`DEFAULT`/`VERBOSE`/`SQLSTATE`) and `conn->show_context` (`PQSHOW_CONTEXT_NEVER`/`ERRORS`/`ALWAYS`). Returns 0 on success, EOF on need-more-data. [verified-by-code, fe-protocol3.c:897-1199]

`reportErrorPosition` (1201) decodes the 'P' (statement position) field as a 1-based character offset (encoding-aware), walks the original query text, and emits a `^`-pointer line under the offending token.

### `getRowDescriptions` (518)

Parses 'T' message: `int16 nfields; for each field { string name; int32 tableOid; int16 colno; int32 typOid; int16 typLen; int32 atttypmod; int16 fmtcode }`. **Allocates per-field strings inside the PGresult arena** via `pqResultStrdup`. If `nfields` > MaxAllocSize / sizeof, fails with overflow check.

### `getAnotherTuple` (777)

Parses 'D' DataRow: `int16 nfields; for each col { int32 len (-1 = NULL); bytes value }`. Calls `pqRowProcessor` (in fe-exec.c) to actually store the row. On row-processor failure (typically OOM), discards via `pqClearAsyncResult` and falls through to `advance_and_error:` which sets up a PGRES_FATAL_ERROR. [verified-by-code, fe-protocol3.c:776-895]

### `pqFunctionCall3` (2207)

Outgoing: builds a 'F' message with function OID, arg formats, arg values, result format. Then loops `pqParseInput`-like over the response: 'V' (FunctionCallResponse) → store result int, 'E' → error, 'N' → notice, 'Z' → done, anything else → "unexpected response".

### Startup packet build

`build_startup_packet` (2479) runs twice — once with `packet == NULL` to compute length, once to fill. The two-pass approach avoids over-allocating. Overflow protection via `pg_add_size_overflow` (common/int.h). Supports `_pq_.` protocol extension parameters; emits `_pq_.test_protocol_negotiation` as grease if `pversion == PG_PROTOCOL_GREASE`. [verified-by-code, fe-protocol3.c:2477-2553]

## Invariants & gotchas

- **`inCursor = inStart` at every message start** — required so partial-parse failure (returning to the outer loop after a `pqGet*` returned EOF) doesn't lose bytes. The rewind is the foundation of the resume-on-more-data pattern. [verified-by-code, fe-protocol3.c:84-88]
- **Length-validation gate `msgLength > 30000 && !VALID_LONG_MESSAGE_TYPE(id)`** caps memory exposure to a malicious or buggy server. Without it, a single bad 'B' (BindComplete, should be 4 bytes) claiming `msgLength = 2^31` would force a 2 GiB allocation. [verified-by-code, fe-protocol3.c:102 @ e0511883cae2]
- **Length consistency check** at the end of dispatch (lines 460-475) verifies the parser consumed exactly `5 + msgLength` bytes. Mismatch triggers a synthesized error result with status READY, and the cursor is force-advanced by the wire-declared length. This is a **defense against protocol bugs in libpq itself** and the only safe recovery: trust the server's length field over libpq's per-field parsing. [verified-by-code, fe-protocol3.c:455-475]
- **Notify and Notice in any state**: 'A' and 'N' never wait. This is required because the server may emit notifications between an idle backend's SIGHUP-driven ParameterStatus and the next query. [verified-by-code, fe-protocol3.c:152-165]
- **Error in IDLE state → notice processor**: an Error arriving when libpq thinks the conn is idle is treated as a notice rather than a result, because there's no PGresult slot for it. The notice still surfaces to the application via `noticeHooks.noticeReceiver`. Often this is the server's swan song ("FATAL: terminating connection due to administrator command"). [from-comment, fe-protocol3.c:168-182]
- **Pipeline error transition**: `pqGetErrorNotice3` sets `conn->pipelineStatus = PQ_PIPELINE_ABORTED` if currently `PQ_PIPELINE_ON`. Subsequent commands return `PGRES_PIPELINE_ABORTED` until the next `Sync`. [verified-by-code, fe-protocol3.c:903-906]
- **New 'T' (RowDescription) mid-result starts a new PGresult**. The comment says "It is not clear that this is really possible with the current backend." Defensive code path. [from-comment, fe-protocol3.c:330-340]
- **'D' DataRow without prior 'T' is an error**: libpq sets up an error result and discards the row. Cannot happen in normal protocol flow; defense against backend bug or MITM. [verified-by-code, fe-protocol3.c:380-393]
- **NegotiateProtocolVersion** ('v') is the only message that can move `conn->pversion` to a value other than the originally-requested one. Server uses it to downgrade a client that asked for 3.x to 3.y. Unknown extension params (in startup `_pq_.` namespace) are reported back. [verified-by-code, fe-protocol3.c:1442-1588]
- **Startup packet build is overflow-paranoid.** Each `ADD_STARTUP_OPTION` uses `pg_add_size_overflow`. Buffer-too-large path returns 0 so caller refuses to send. [verified-by-code, fe-protocol3.c:2498-2553]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-misc.c.md` — `pqGetc`/`pqGetInt`/`pqCheckInBufferSpace` plumbing.
- `knowledge/files/src/interfaces/libpq/fe-exec.c.md` — `pqRowProcessor`, `pqSaveErrorResult`, `pqClearAsyncResult`, the async-status state machine.
- `knowledge/files/src/interfaces/libpq/fe-connect.c.md` — calls `pqGetNegotiateProtocolVersion3` and `pqBuildStartupPacket3` during the connect handshake.
- `knowledge/files/src/interfaces/libpq/fe-lobj.c.md` — sole user of `pqFunctionCall3` (via `PQfn`).
- Backend mirror: `knowledge/files/src/backend/tcop/postgres.c.md` (the `PqMsg_*` dispatch on the server side), `knowledge/files/src/include/libpq/protocol.h.md` (the canonical `PqMsg_*` enum).

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## INV tags (invariants for cross-referencing)

**INV-libpq-proto3-1**: Every message body MUST be `msgLength - 4` bytes (the `-4` because `msgLength` includes its own length word). The dispatcher enforces this via the post-switch consistency check. [verified-by-code, fe-protocol3.c:455-475]

**INV-libpq-proto3-2**: `msgLength` is read as int via `pqGetInt(4)`. A high-bit-set length becomes negative; the immediate `< 4` check rejects this as sync loss. [verified-by-code, fe-protocol3.c:89-91]

**INV-libpq-proto3-3**: `inCursor` is set to `inStart` at the top of each iteration. Any field that returns EOF leaves `inCursor` mid-parse but the outer loop rewinds before retrying. **Pointers into `inBuffer` cannot be held across iterations** (also covered by INV-libpq-misc-1). [verified-by-code, fe-protocol3.c:79-92]

**INV-libpq-proto3-4**: A NoticeResponse or NotificationResponse is always processable, regardless of `asyncStatus`. Other messages MUST come in BUSY state (with the IDLE-special cases above). [verified-by-code, fe-protocol3.c:152-200]

**INV-libpq-proto3-5**: `pqGetErrorNotice3` MUST always either fully consume the message or return EOF — partial consumption leaves the parser desynced. [verified-by-code, fe-protocol3.c:898-1028, returns rooted at "return EOF" or "return 0" with consumed cursor]

## Potential issues

- **[ISSUE-correctness: 30000-byte cap is a magic number]** fe-protocol3.c:100 — `msgLength > 30000 && !VALID_LONG_MESSAGE_TYPE(id)` was tuned for "no reasonable short message should exceed 30K", but is unjustified at any specific value. Tighter cap would reject more malicious data; looser would accept legitimate edge cases (very long ParameterStatus values?). Worth a focused write-up. **Severity: maybe.** Phase D consideration.
- **[ISSUE-correctness: int overflow on `getRowDescriptions` nfields]** fe-protocol3.c:518-688 — `nfields` is read via `pqGetInt(2)` (int16). The allocation `nfields * sizeof(PGresAttDesc)` should not overflow at 65535 fields × ~40 bytes ≈ 2.5 MB. Safe in practice but verify the multiplication is done in size_t, not int. **Severity: maybe.**
- **[ISSUE-undocumented-invariant: "unexpected response from server"]** fe-protocol3.c:430-440 — default branch in the switch emits a translated error and advances the cursor by `msgLength`. The server can send arbitrary bytes here and libpq will continue. Documented behavior, but worth a corpus tag.
- **[ISSUE-leak: error-field 'F' (file), 'L' (line), 'R' (routine) reveal server internals]** fe-protocol3.c:898-1199 — these fields go into `PQresultErrorMessage` when verbosity = VERBOSE. Production deployments should usually keep verbosity = DEFAULT so file/line/routine don't leak via app-rendered errors. **Severity: maybe (information disclosure).** Phase D should consider a libpq-level default-off for VERBOSE.
- **[ISSUE-question: 'q' field code in error messages]** fe-protocol3.c:898-1199 — 'q' is internal-query (the query the failing routine ran on the server's behalf, e.g. inside a trigger). Could carry sensitive SQL. Worth audit.
- **[ISSUE-correctness: out-of-order ParameterStatus in pipeline]** fe-protocol3.c:152-200 — ParameterStatus in IDLE state is processed; but in pipeline mode the "queue tail message" semantics may interact oddly with a SIGHUP-driven GUC change arriving between two pipelined commands. **Severity: maybe.** Worth a TAP test scenario.
- **[ISSUE-style: 400-line switch statement]** fe-protocol3.c:201-475 — readable but tough to refactor; the implicit "consumed exactly msgLength bytes" contract per branch is easy to violate. Consider an INV-tag in the source comment per branch.
- **[ISSUE-correctness: 'CopyData' silently dropped outside COPY state]** fe-protocol3.c:402-410 — if the application exited COPY OUT early, subsequent CopyData are silently consumed. Comment acknowledges this; the data is gone. Worth surfacing in the COPY docs.

## Tally

`[verified-by-code]=20 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=2`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->
