# pqexpbuffer.c

- **Source path:** `source/src/interfaces/libpq/pqexpbuffer.c`
- **Last verified commit:** `4b0bf0788b0`
- **Size:** 413 lines

## Purpose

Implementation of the StringInfo-equivalent extensible string for frontend code. See `pqexpbuffer.h.md` for the API contract; this doc covers the implementation choices.

## OOM design

> "It does not rely on palloc() nor elog(), nor psprintf.c which will exit() on error." [lines 11-12, from-comment]

OOM is **never fatal**. The mechanism:

- A static `const char oom_buffer[1] = ""` (line 38) is shared by every broken buffer.
- `markPQExpBufferBroken` (lines 49-64) frees the live data (if not already `oom_buffer`) and points `data` at this shared zero-byte string with `len = maxlen = 0`.
- The const-storage choice is deliberate: comment at lines 56-59 says it lets the compiler put `oom_buffer` in read-only storage so any accidental writes SIGSEGV instead of silently corrupting state.
- The cast away const uses the `unconstify()` macro (e.g. line 61).

[verified-by-code]

## Growth algorithm (`enlargePQExpBuffer`, lines 171-225)

1. Early-out if already broken.
2. **Overflow guard**: if `needed >= INT_MAX - str->len`, mark broken and bail (lines 185-189). Prevents `needed += len + 1` from wrapping.
3. Add `len + 1` to get total required.
4. If `needed <= maxlen`, return 1 (no realloc).
5. Otherwise double `maxlen` until `>= needed`. Start at 64 if maxlen was 0.
6. Clamp to `INT_MAX` (lines 212-213). Comment notes assumption `INT_MAX <= UINT_MAX/2` so doubling can't overflow `size_t`. [from-comment]
7. `realloc`. On failure, mark broken. On success, update `data` + `maxlen`.

The `INT_MAX` ceiling matches `PGconn.inBufSize`/`outBufSize`'s `int` typing — buffer can't exceed 2GiB-1.

## Format functions

`appendPQExpBufferVA` (lines 293-359) — shared guts. Strategy:

1. If `> 16` bytes free, try `vsnprintf` directly into the tail.
2. If `vsnprintf < 0` (format string error per C99), mark broken, return done.
3. If `nprinted < avail`, success.
4. Else trust C99 vsnprintf's "would-have-written" return value; check `nprinted > INT_MAX - 1` overflow guard (lines 335-339), mark broken if so; otherwise `needed = nprinted + 1` and request enlarge then retry (return false).
5. If `<= 16` bytes free, skip the format attempt and just enlarge by 32 — caller will retry. Comment (lines 343-350) explains this is fine because of `enlargePQExpBuffer`'s power-of-2 sizing.

`printfPQExpBuffer` (lines 234-254) and `appendPQExpBuffer` (lines 264-282) both **save and restore `errno`** across the loop. Reason: `%m` in the format consumes `errno`; if the first `vsnprintf` succeeds but doesn't fit, the second call needs the original `errno`. [verified-by-code, comment at line 290-291]

## appendPQExpBufferChar / appendBinaryPQExpBuffer

`appendPQExpBufferChar` (lines 377-388) — fast path: enlarge by 1, write byte, advance len, write trailing NUL.

`appendBinaryPQExpBuffer` (lines 396-412) — enlarge by `datalen`, `memcpy`, advance len, write trailing NUL. Comment (line 408-410) says "Keep a trailing null in place, even though it's probably useless for binary data" — the invariant is unconditional. [from-comment]

## Phase D notes

[ISSUE-pqexpbuffer-001 — maybe] The `INT_MAX` ceiling (line 213) silently caps growth at ~2GiB. A 2GiB allocation request will succeed with a truncated buffer, possibly producing partial COPY data. Hard error vs silent cap is debatable, but the current behavior is fail-broken on the **next** `enlargePQExpBuffer` call only.

[ISSUE-pqexpbuffer-002 — maybe] `vsnprintf` is called on the buffer's tail with `avail` = `maxlen - len`. On a buggy libc that writes past the requested size, this could corrupt the next heap chunk. PG ships its own snprintf (`src/port/snprintf.c`) when configure detects libc's is broken; verify the configure-time check is still triggered on current platforms.

## Tally

`[verified-by-code]=4 [from-comment]=4 [maybe]=2`
