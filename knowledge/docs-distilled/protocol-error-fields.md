---
source_url: https://www.postgresql.org/docs/current/protocol-error-fields.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §55.8: Error and Notice Message Fields

The single-byte field codes inside every `ErrorResponse` / `NoticeResponse` wire
message. This is the protocol-level counterpart to what `ereport()`'s
`errdetail`/`errhint`/`errposition`/`errtable` macros emit — useful when matching
backend `ereport` calls to what a client driver actually receives.

## The field codes [from-docs]

Each field is one byte (the code), a string value, NUL-terminated; the message
ends at a zero code byte. At most one of each per message.

| Code | Field | Meaning |
|---|---|---|
| `S` | Severity | `ERROR`/`FATAL`/`PANIC` (errors) or `WARNING`/`NOTICE`/`DEBUG`/`INFO`/`LOG` (notices); **may be localized**. Always present. |
| `V` | Severity (non-localized) | Same as `S` but **never localized**. PG 9.6+ only. |
| `C` | Code | The **SQLSTATE** (Appendix A). Not localizable. Always present. |
| `M` | Message | Primary human-readable message (one line). Always present. |
| `D` | Detail | Optional secondary detail; may be multi-line. |
| `H` | Hint | Optional advice; may be multi-line. |
| `P` | Position | 1-based **character** index into the original query string (cursor position). |
| `p` | Internal position | Like `P` but into an internally-generated command; `q` always accompanies it. |
| `q` | Internal query | Text of the failed internally-generated command (e.g. SQL from a PL/pgSQL fn). |
| `W` | Where | Context / call-stack traceback (most recent first, one per line). |
| `s` | Schema name | Schema of the associated object. |
| `t` | Table name | Associated table. |
| `c` | Column name | Associated column. |
| `d` | Data type name | Associated type. |
| `n` | Constraint name | Associated constraint (**indexes are treated as constraints**). |
| `F` | File | Source file where the error was reported. |
| `L` | Line | Source line. |
| `R` | Routine | Source routine reporting the error. |

[verified-by-code, source/src/backend/utils/error/elog.c — `send_message_to_frontend`
emits exactly these `PG_DIAG_*` codes; via knowledge/idioms/error-handling.md]

## Non-obvious points [from-docs]

- **`S` can be localized; `V` never is** — drivers that branch on severity must
  parse `V`, not `S`, to stay locale-independent. [from-docs]
- The `s`/`t`/`c`/`d`/`n` object-name fields are *"supplied only for a limited
  number of error types"* — don't expect them on a generic error. They map to the
  `errtable()`, `errtablecol()`, `errtableconstraint()` `ereport` auxiliaries.
  [from-docs] [verified-by-code, source/src/include/utils/elog.h — `PG_DIAG_*`]
- `P` is measured in **characters, not bytes**, 1-based — matters for multibyte
  encodings when a client highlights the error position. [from-docs]
- `F`/`L`/`R` are the `__FILE__`/`__LINE__`/`__func__` the `ereport` macro
  captures automatically; they're how `\errverbose` in psql shows the backend
  source location. [from-docs, inferred]

## Links into corpus

- [[knowledge/idioms/error-handling.md]] — the `ereport`/`errdetail`/`errhint`/
  `errposition`/`errtable*` macros that populate these fields.
- [[knowledge/docs-distilled/error-style-guide.md]] — how the `M`/`D`/`H` text
  should be worded.
- [[knowledge/docs-distilled/protocol-message-formats.md]] — the byte layout of
  the enclosing `ErrorResponse`/`NoticeResponse`.
- [[knowledge/docs-distilled/protocol-overview.md]] — where these messages sit in
  the message flow.

## Gaps / follow-ups

- This page is a pure field catalogue; the *wording* rules live in
  error-style-guide (distilled this run), and the SQLSTATE-selection rules in the
  error-handling idiom + `errcodes.txt`.
