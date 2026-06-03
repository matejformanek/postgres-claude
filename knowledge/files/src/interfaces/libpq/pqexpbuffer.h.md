# pqexpbuffer.h

- **Source path:** `source/src/interfaces/libpq/pqexpbuffer.h`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 192 lines

## Purpose

> "PQExpBuffer provides an indefinitely-extensible string data type... essentially the same as the backend's StringInfo data type, but it is intended for use in frontend libpq and client applications. Thus, it does not rely on palloc() nor elog()." [`pqexpbuffer.h:6-13`, from-comment]

The frontend analogue of `StringInfo`. Pure-malloc; no exit-on-OOM. Used everywhere in libpq (error messages, message construction, conninfo parsing) and re-exported for client tools like psql, pg_dump.

## Types

- `PQExpBufferData` (lines 44-49): `char *data`, `size_t len`, `size_t maxlen`. Invariant: `maxlen > len` and `data[len] == '\0'` (so it's always a valid C string, even when storing binary).
- `PQExpBuffer` typedef = `PQExpBufferData *`.

## Broken state

OOM is in-band, not an exception. After a failing `malloc`/`realloc`, the buffer becomes **"broken"**: `data` points at a shared static empty string (`oom_buffer` in the .c), `len = maxlen = 0`. All subsequent ops are no-ops; only `resetPQExpBuffer` or `terminate`/`destroy` are legal.

Test macros:
- `PQExpBufferBroken(str)` (lines 59-60) — null or `maxlen == 0`. Use for malloc'd buffers.
- `PQExpBufferDataBroken(buf)` (lines 67-68) — just `maxlen == 0`. Use for stack/embedded structs (the null check would warn).

## Constants

- `INITIAL_EXPBUFFER_SIZE` 256 (line 76) — comment: "must be large enough to hold error messages that might be returned by PQrequestCancel()". [verified-by-code]

## API

Construction (two flavors):
- `createPQExpBuffer(void)` — malloc'd struct + malloc'd data; pair with `destroyPQExpBuffer`.
- `initPQExpBuffer(PQExpBuffer)` — caller-supplied struct (typically a struct member or stack), data buffer malloc'd; pair with `termPQExpBuffer`.

Teardown:
- `destroyPQExpBuffer(str)` — frees data + struct.
- `termPQExpBuffer(str)` — frees data only.

State:
- `resetPQExpBuffer(str)` — set to empty; also un-breaks a broken buffer by retrying allocation.

Growth:
- `enlargePQExpBuffer(str, needed)` — ensure room for `needed` more bytes (excluding NUL). Returns 1 OK / 0 broken.

Formatting:
- `printfPQExpBuffer(str, fmt, ...)` — reset + append (printf-style).
- `appendPQExpBuffer(str, fmt, ...)` — append formatted.
- `appendPQExpBufferVA(str, fmt, va_list)` — va_list variant; returns true if done (success or hard failure), false to retry. **Caller must preserve entry-time errno** when looping, because `%m` consumes `errno`. [from-comment, line 165-166]
- `appendPQExpBufferStr(str, s)` — append C string.
- `appendPQExpBufferChar(str, ch)` — append single byte (fast path).
- `appendBinaryPQExpBuffer(str, data, datalen)` — append arbitrary bytes.

## Cross-references

- `pqexpbuffer.c` — implementation.
- `libpq-int.h` — `PGconn.errorMessage` is a `PQExpBufferData`, `PGconn.workBuffer` is too.
- Backend `StringInfo` — same contract minus the broken-state mechanism.

## Tally

`[verified-by-code]=3 [from-comment]=4`
