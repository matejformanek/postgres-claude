# src/include/nodes/miscnodes.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 57 [verified-by-code]

## Role

Catch-all for tagged structs that don't belong to parse / plan / exec
trees but need `IsA()` discrimination. Today it contains exactly one
type — `ErrorSaveContext` — the canonical **soft-error** mechanism.

## Public API

- `ErrorSaveContext` — `NodeTag type`, `bool error_occurred`,
  `bool details_wanted`, `ErrorData *error_data` (`:44-50`).
- `SOFT_ERROR_OCCURRED(escontext)` macro (`:53-55`) — defensive check
  that `escontext` is non-NULL and IsA(ErrorSaveContext) before
  reading `error_occurred`.

## Invariants

- INV-ESC-INIT: caller must zero-init all fields except `type` (set
  to `T_ErrorSaveContext`); details_wanted optionally set true. Then
  pass via `FunctionCallInfo.context` (`:30-35` [from-comment]).
- INV-ESC-CONTEXT-OWNERSHIP: if `error_data` is filled, it lives in
  the **callee's memory context** (`:39-43` [from-comment]). Caller
  must either be in a short-lived context (auto-freed) or call
  `FreeErrorData()`.
- INV-ESC-NO-LONGJMP: soft-error path means `errsave()` (not
  `ereport`/`elog`) — does NOT longjmp. Caller MUST check
  `error_occurred` after every soft-error-aware call.

## Notable internals

- A callee receiving an `escontext` chooses between hard and soft
  reporting via the `errsave(escontext, ...)` macro family — if
  escontext is NULL, falls back to `ereport(ERROR, ...)`.
- The pattern is opt-in per callee. Examples:
  `record_recv` (jsonb input), `pg_input_is_valid`, COPY's
  `on_error=ignore` (PG17).

## Trust boundary / Phase D surface

- **A7 echo — canonical soft-error infrastructure.** Many input
  functions retrofitted to support soft errors. Trust risk: if a
  type's `_in` function partially mutates state before deciding to
  raise a soft error, the partial state is observable via
  `error_data->message` even though the operation "failed cleanly".
  Documented A7 finding cluster: numeric / xml / record types.
- **PG14+ infrastructure.** Pre-existing code in extensions may
  pass FunctionCallInfo.context for OTHER purposes (e.g. trigger
  data) — the `SOFT_ERROR_OCCURRED` macro's `IsA` check defends
  against that confusion. Extensions adding their own NodeTag for
  function context must NOT use `T_ErrorSaveContext`.

## Cross-references

- `utils/elog.h` — `ErrorData`, `errsave()`, `ThrowErrorData()`,
  `FreeErrorData()`.
- `fmgr.h` — `FunctionCallInfo.context` field.
- A7 corpus entries on `record_recv` / xml.c safe paths.
- `error-handling` skill — full soft-error idiom.

## Issues / drift

- `[ISSUE-DOC: comment does not warn that error_data lives in callee's context — easy to UAF if caller switches context between call and FreeErrorData (medium)] — source/src/include/nodes/miscnodes.h:39-43`
- `[ISSUE-TRUST: A7 cluster — input functions that partially-update state before soft-erroring expose intermediate state via ErrorData (medium)] — source/src/include/nodes/miscnodes.h:25-43`
