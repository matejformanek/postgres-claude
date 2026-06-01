# fastpath.c

- **Source:** `source/src/backend/tcop/fastpath.c` (458 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + main API)

## Purpose

Server-side implementation of `PQfn()` — the "F" protocol message that
invokes a single function by OID, bypassing parse/plan/execute. Used in
practice by libpq's large-object API. [from-comment] `:13-14`

## Design notes

- No caching of function/type info across calls. An earlier attempt was
  removed because each fastpath call is a separate transaction command, so
  cached `FmgrInfo` could never have been reused safely. [from-comment]
  `:37-47`
- The local cache struct `fp_info` (`:48-56`) is allocated per call: funcid,
  flinfo, namespace, rettype, argtypes[], short fname.

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 67 | `SendFunctionResult` | format the function's `Datum`/`null` result and send the `'V'` reply |
| 119 | `fetch_fp_info` | syscache lookup → fill `fp_info` |
| 188 | `HandleFunctionRequest` | the dispatch entry called from `PostgresMain` on `'F'` |
| 329 | `parse_fcall_arguments` | parse the wire format args according to format codes |

## Control flow

`HandleFunctionRequest`:

1. Read function OID and format codes from `msgBuf`.
2. `fetch_fp_info(funcid, &fp_info)` — pg_proc lookup, ACL check, build
   `FmgrInfo`.
3. Snapshot setup (`PushActiveSnapshot`).
4. `parse_fcall_arguments` decodes args (text or binary per format codes).
5. `FunctionCallInvoke(fcinfo)`.
6. `SendFunctionResult`.
7. Pop snapshot, command-complete.

## Authorization

`fetch_fp_info` enforces `EXECUTE` privilege on the function and forbids
the path for security-restricted contexts where appropriate.

## Header

`tcop/fastpath.h` (very small — just `HandleFunctionRequest` prototype).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
