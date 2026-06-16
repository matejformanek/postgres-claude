---
path: src/interfaces/libpq/fe-trace.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 927
depth: deep
---

# fe-trace.c

- **Source path:** `source/src/interfaces/libpq/fe-trace.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 927
- **Companion files:** `libpq-int.h` (`conn->Pfdebug`, `conn->traceFlags`, `conn->current_auth_response`), `fe-misc.c` (`pqParseDone` calls `pqTraceOutputMessage` on the way in), `fe-exec.c` and `fe-protocol3.c` (drive both directions)

## Purpose

Wire-protocol tracer. `PQtrace(conn, FILE *)` installs a `FILE *` into `conn->Pfdebug`; thereafter every protocol message in either direction is decoded and pretty-printed to that file. Three flags (combinable):

- `PQTRACE_SUPPRESS_TIMESTAMPS` — for tests where wall-clock would vary.
- `PQTRACE_REGRESS_MODE` — extra suppressions for fields known to vary across builds (ErrorResponse F/L/R, message length on errors, BackendKeyData PID/key, RowDescription field OIDs, ParameterDescription, NegotiateProtocolVersion). Used by `src/test/modules/libpq_pipeline` regression tests.
- `PQTRACE_SUPPRESS_TYPES` — also tied to regress mode in pieces.

Output format per message:

```
<timestamp>\tF\t<length>\t<MessageName>\t<fields…>      (for client→server)
<timestamp>\tB\t<length>\t<MessageName>\t<fields…>      (for server→client)
```

## Public API surface

| Function | Line | One-liner |
|---|---|---|
| `PQtrace` | 35 | Install `FILE *` into `conn->Pfdebug`. Side-effect: also calls `PQuntrace` first so re-installing closes the previous file? — actually NO, it just nullifies (see gotcha). |
| `PQuntrace` | 49 | `fflush` and clear `Pfdebug`. Does NOT `fclose` the file. |
| `PQsetTraceFlags` | 64 | Set the bitmask of `PQTRACE_*` flags. No-op if `Pfdebug` is NULL. |

Internal (called from `pqParseDone` in fe-misc.c and from `pqPutMsgEnd`):

`pqTraceOutputMessage` (624) — dispatcher on message-type byte, drives every `pqTraceOutput_*Foo` helper. `pqTraceOutputNoTypeByteMessage` (841) — handles startup-style messages (SSLRequest, GSSRequest, StartupMessage, CancelRequest) that have no type byte. `pqTraceOutputCharResponse` (915) — for single-char responses (the SSL/GSS handshake 'S'/'N'/'E').

## Internal landmarks

### Per-message helpers

Each `pqTraceOutput_X` is ~10-30 lines, takes `FILE *f, const char *message, int *cursor` (cursor advanced as fields are consumed), and the optional `regress` bool. Coverage:

- Frontend: `Bind`, `Close`, `CopyFail`, `Describe`, `Execute`, `Flush`, `FunctionCall`, `GSSResponse`/`PasswordMessage`/`SASLInitialResponse`/`SASLResponse` (share type byte 'p'), `Parse`, `Query`, `Terminate`.
- Backend: `Authentication`, `BackendKeyData`, `BindComplete`, `CloseComplete`, `CommandComplete`, `CopyBothResponse`, `CopyData`, `CopyDone`, `CopyInResponse`, `CopyOutResponse`, `DataRow`, `EmptyQueryResponse`, `ErrorResponse`, `FunctionCallResponse`, `NegotiateProtocolVersion`, `NoData`, `NoticeResponse`, `NotificationResponse`, `ParameterDescription`, `ParameterStatus`, `ParseComplete`, `PortalSuspended`, `ReadyForQuery`, `RowDescription`.

### Auth-response disambiguation

Several auth-response message types share the byte `'p'` (`PqMsg_PasswordMessage == PqMsg_GSSResponse == PqMsg_SASLInitialResponse == PqMsg_SASLResponse`). The dispatcher disambiguates via `conn->current_auth_response` (an `AUTH_RESPONSE_*` enum set by the sending code before `pqPutMsgEnd`). After printing, `current_auth_response` is reset to `'\0'`. [verified-by-code, fe-trace.c:710-740]

### Field type abbreviations

The trace uses single-letter / short codes for common fields. ErrorResponse / NoticeResponse field codes (`S`, `C`, `M`, `D`, `H`, `P`, `q`, `W`, `F`, `L`, `R`, …) are written verbatim then the field value; regress mode suppresses `F`/`L`/`R` since file/line/routine change as source moves.

### Hookpoints

- Frontend side: `pqPutMsgEnd` (fe-misc.c:531) ends with `if (conn->Pfdebug) pqTraceOutputMessage(conn, conn->outBuffer + conn->outMsgStart - 1, true)`.
- Backend side: `pqParseDone` (fe-misc.c:443) calls `pqTraceOutputMessage(conn, conn->inBuffer + conn->inStart, false)` before advancing `inStart`.
- Startup messages (no type byte) use `pqTraceOutputNoTypeByteMessage` because length-only framing breaks the standard `[1 type][4 length][...body]` assumption.
- 1-byte SSL/GSS responses use `pqTraceOutputCharResponse`.

## Invariants & gotchas

- **`PQuntrace` does not close the FILE.** Application owns the FILE pointer; this function only fflushes and detaches. Re-attaching a stale FILE via `PQtrace` does not assert; the burden is on the caller. [verified-by-code, fe-trace.c:35-58]
- **`PQtrace` first calls `PQuntrace`** to detach any prior trace, but again does not close. If the application called `PQtrace(conn, f1); PQtrace(conn, f2);` it must remember to `fclose(f1)` itself. [verified-by-code, fe-trace.c:35-45]
- **`conn->traceFlags = 0` is reset by both `PQtrace` and `PQuntrace`.** So flags must be re-set via `PQsetTraceFlags` after every `PQtrace` call. [verified-by-code, fe-trace.c:42-43, 56]
- **`PQsetTraceFlags` is a no-op if `Pfdebug == NULL`.** Set flags AFTER `PQtrace`, not before. [verified-by-code, fe-trace.c:64-72]
- **Regress mode suppresses lengths only for ErrorResponse/NoticeResponse**, replacing with `NN`. Other messages keep their length in the trace; tests that diff trace output across builds must be aware. [verified-by-code, fe-trace.c:651-660]
- **The tracer reads the same `inBuffer` / `outBuffer` the protocol parser is about to consume.** It is purely an observer; it doesn't advance `inCursor` / `outMsgStart`. [from-comment in pqParseDone and pqPutMsgEnd]
- **Auth-response disambiguation depends on `current_auth_response`** being set correctly by the sender. A bug that forgets to set it would print "UnknownAuthenticationResponse"; not a correctness bug, just a trace artifact. [verified-by-code, fe-trace.c:710-744]
- **No SSL/GSS payload bytes are traced.** Only the protocol bytes after the TLS layer. Traces never reveal pre-master secret. (Trivially true because the tracer sees post-TLS bytes from `conn->inBuffer`.)

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-misc.c.md` — the `pqParseDone`/`pqPutMsgEnd` hookpoints.
- `knowledge/files/src/interfaces/libpq/fe-protocol3.c.md` — what each message means in the parser.
- `src/test/modules/libpq_pipeline/` — the regression test that uses `PQTRACE_REGRESS_MODE`.

<!-- issues:auto:begin -->
- [Issue register — `libpq`](../../../../issues/libpq.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: `PQsetTraceFlags` silently no-ops without active trace]** fe-trace.c:64-72 — easy to mis-order in user code (set flags, then enable trace) and have flags lost. Documented in the inline comment but worth a corpus tag.
- **[ISSUE-leak: trace files capture full DataRow contents]** fe-trace.c — `DataRow` payloads are printed verbatim. Sensitive data (PII, secrets) in result rows ends up in the trace file. **Severity: maybe (intentional).** This is a developer/debug tool; risk is mis-use in production. Phase D should at least note the data-exposure surface.
- **[ISSUE-leak: trace prints Parse/Bind parameter values]** fe-trace.c — same as DataRow: SQL parameters (e.g. passwords, tokens) go to the trace. **Severity: maybe.** Reasonable for a debugger; risky if someone enables trace in prod and forgets.
- **[ISSUE-question: regress mode and binary data]** Does `pqTraceOutput_DataRow` render binary-format columns sensibly, or does it dump raw bytes that vary by endianness/platform? Quick scan of fe-trace.c:292-310 suggests it just hex-dumps. Worth confirming for regress stability of binary-format pipeline tests. **Severity: nit.**
- **[ISSUE-style: 35+ small helper functions, very repetitive]** fe-trace.c — each `pqTraceOutput_FooMessage` is 5-25 lines doing pqGet*-then-fprintf. A table-driven dispatch would be more compact but the explicit per-message logic is easier to read. **Severity: nit.**

## Tally

`[verified-by-code]=10 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new libpq protocol message](../../../../scenarios/add-new-protocol-message.md)

<!-- scenarios:auto:end -->
