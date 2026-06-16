# src/common/stringinfo.c

## Purpose

Implementation of the `StringInfoData` dynamic byte buffer (the
PG-wide alternative to `PQExpBuffer` and to ad-hoc `realloc`
loops). Provides amortised-O(1) append, automatic geometric
growth, MaxAllocSize cap, and a per-allocation memory context
binding (in backend) or malloc-backed fallback (in frontend).

## Role in PG

Shared **frontend + backend**, with the backend version using
palloc/repalloc and the frontend version falling back to
malloc/realloc via the `palloc` macro defined in
`common/fe_memutils.h`. Used by basically every code path that
builds a string of unknown length: the wire-protocol output
buffer, every elog message, json/jsonb output, pg_dump's SQL
emission, COPY OUT, and so on.

## Key functions

- `initStringInfoInternal(str, initsize)` static inline — common
  init path, asserts `1 <= initsize <= MaxAllocSize`. Used by both
  the default- and explicit-size variants. (`stringinfo.c:40-48`)
- `StringInfo makeStringInfo(void)` — heap-allocate a
  `StringInfoData` then init with `STRINGINFO_DEFAULT_SIZE` (=1024
  per `stringinfo.h`). (`stringinfo.c:71-75`)
- `StringInfo makeStringInfoExt(int initsize)` — same with explicit
  size. (`stringinfo.c:84-88`)
- `void initStringInfo(StringInfo str)` — init in-place with default
  size; the stack-allocated `StringInfoData` idiom.
  (`stringinfo.c:96-100`)
- `void initStringInfoExt(StringInfo str, int initsize)` — likewise
  with explicit size. (`stringinfo.c:110-114`)
- `void resetStringInfo(StringInfo str)` — clear contents, keep
  buffer; asserts `maxlen != 0` (read-only StringInfos use
  `maxlen=0` as the read-only marker). (`stringinfo.c:125-134`)
- `void appendStringInfo(StringInfo str, const char *fmt, ...)` —
  printf-style append with auto-grow. Loops on `appendStringInfoVA`
  + `enlargeStringInfo` until a single attempt fits. Preserves
  `errno` across attempts so `%m` works.
  (`stringinfo.c:144-166`)
- `int appendStringInfoVA(StringInfo str, const char *fmt, va_list
  args)` — single printf attempt; returns 0 on success or the
  needed buffer size if it didn't fit. If `avail < 16`, returns 32
  immediately without trying. (`stringinfo.c:186-221`)
- `void appendStringInfoString(StringInfo str, const char *s)` —
  fast path equivalent to `%s` format.
  (`stringinfo.c:229-233`)
- `void appendStringInfoChar(StringInfo str, char ch)` — single
  byte append, inline-friendly. (`stringinfo.c:241-252`)
- `void appendStringInfoSpaces(StringInfo str, int count)` —
  pad with `count` spaces. (`stringinfo.c:259-272`)
- `void appendBinaryStringInfo(StringInfo str, const void *data,
  int datalen)` — copy raw bytes; always maintains a trailing NUL
  for callers that mix binary and text. (`stringinfo.c:280-298`)
- `void appendBinaryStringInfoNT(...)` — same without the trailing
  NUL guarantee, slightly cheaper. (`stringinfo.c:306-317`)
- `void enlargeStringInfo(StringInfo str, int needed)` — the growth
  routine. Hard error on `needed < 0`. Errors with
  `ERRCODE_PROGRAM_LIMIT_EXCEEDED` if `len + needed >= MaxAllocSize`.
  Otherwise doubles `maxlen` until `>= len + needed + 1`, clamped to
  MaxAllocSize. Uses `repalloc()`, so the buffer stays in the
  context that was current at `initStringInfo` time —
  load-bearing for memory-context discipline.
  (`stringinfo.c:336-400`)
- `void destroyStringInfo(StringInfo str)` — pfree buffer then the
  struct. Only valid for palloc'd StringInfos.
  (`stringinfo.c:408-416`)

## State / globals

None.

## Phase D notes

- **Length is `int`, capped at MaxAllocSize (1GB - 1).** Both
  `len` and `maxlen` are `int`. The `enlargeStringInfo` check
  uses `Size needed >= MaxAllocSize - str->len` to avoid the
  obvious overflow, and the doubling loop relies on
  `MaxAllocSize <= INT_MAX/2` (commented at `stringinfo.c:390-393`).
  A caller passing `needed < 0` hits the explicit `elog(ERROR)`,
  not silent UB. `[verified-by-code]`
- **Memory-context binding is invariant.** The big comment block
  at `stringinfo.c:331-335` calls out that `repalloc` keeps the
  buffer in the context current at init time, even if the active
  context has since changed. Breaking this invariant by switching
  contexts mid-build would leave a buffer pfree'd by a context
  reset under the caller's feet.
- **Read-only StringInfos.** `initReadOnlyStringInfo` (defined in
  `lib/stringinfo.h`, not here) sets `maxlen = 0`. The asserts in
  `resetStringInfo`, `enlargeStringInfo`, and `destroyStringInfo`
  catch attempts to mutate or free those. The asserts are
  Assert(), so a non-cassert build would silently corrupt; this is
  intentional per PG convention.
- **`appendStringInfoVA` early-out at avail < 16.** The "guess
  size = 32" shortcut at line 199-201 returns without attempting
  the vsnprintf; this means a tiny `%c` append never actually
  measures its size. In the worst case this trades one extra
  enlarge call for not invoking vsnprintf on a too-small buffer.

## Potential issues

`[ISSUE-dos: StringInfoData length is int+MaxAllocSize-bound (1GB);
parsers building a single StringInfo from attacker-controlled input
(e.g. row text in COPY FROM, large JSON path output) can hit
ERRCODE_PROGRAM_LIMIT_EXCEEDED rather than OOM. Behaviour-correct
but yields a hard ereport instead of a graceful soft error. (low)]`

`[ISSUE-undocumented-invariant: the "buffer stays in init-time
context" invariant is documented in this file but not in
lib/stringinfo.h — a caller reading only the header could
misinterpret the lifetime rules. (low)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
