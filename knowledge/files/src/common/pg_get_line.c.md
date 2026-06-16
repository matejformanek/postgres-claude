# pg_get_line.c

`fgets()` with an expansible (`StringInfo`-backed) buffer. Reads a
single line of arbitrary length from a `FILE *`, into either a
freshly-allocated string (`pg_get_line`), a caller-supplied
`StringInfo` (`pg_get_line_buf`), or appended to an existing
`StringInfo` (`pg_get_line_append`). Optional cancellation through
a `PromptInterruptContext` longjmp hook.
(`source/src/common/pg_get_line.c:27-180`) [verified-by-code]

Shared FE/BE — backend uses `palloc`/`pfree`; frontend gets the
shim from `fe_memutils.c`. (`source/src/common/pg_get_line.c:15-19`)

## Purpose

A safer replacement for `fgets(fixed_buf, sizeof(fixed_buf), …)`
that doesn't truncate or require pre-sized buffers. Used by
`simple_prompt` (so it underlies every interactive password
prompt), by `psql`'s file mode, and by anything else that parses
text input line-by-line. Trailing newline is preserved, matching
`fgets()` semantics; caller is expected to apply `pg_strip_crlf()`.

## Key functions

- `pg_get_line(stream, prompt_ctx)` — allocates a `StringInfo`,
  delegates to `pg_get_line_append`, returns `buf.data`. On failure
  pfrees and returns NULL, preserving `errno`.
  (`source/src/common/pg_get_line.c:58-76`)
- `pg_get_line_buf(stream, buf)` — resets `buf` then appends.
  Returns false on EOF/error with `buf` empty.
  (`source/src/common/pg_get_line.c:94-100`)
- `pg_get_line_append(stream, buf, prompt_ctx)` — the core loop.
  Calls `fgets()` into the unused tail of `buf->data`, advances
  `buf->len`, and enlarges by 128 bytes until a newline is seen or
  EOF/error.
  (`source/src/common/pg_get_line.c:123-180`)

  The signal/cancel handshake: if `prompt_ctx` is given,
  `sigsetjmp(*prompt_ctx->jmpbuf, 1)` runs once at entry; before
  each `fgets()` the loop sets `*prompt_ctx->enabled = true`, then
  clears it after. A SIGINT handler elsewhere is expected to
  `siglongjmp` to `*jmpbuf` *only* when `*enabled` is true. On
  longjmp return, `prompt_ctx->canceled = true` and `buf` is
  truncated back to its entry length. (`pg_get_line.c:127-137`)

## State / globals

None — entirely caller-state driven via `StringInfo` and the
`PromptInterruptContext` struct.

## Phase D notes

[ISSUE-secret-scrub: pg_get_line buffer holds the password tail
from simple_prompt and is pfree'd unscrubbed (maybe)] When
`simple_prompt(echo=false)` calls `pg_get_line` to read a password
(`sprompt.c:145`), the returned buffer is the live secret. On
errors (`pg_get_line.c:65-73`), the function does
`pfree(buf.data)` — which is `free()` in frontend — without
`explicit_bzero`. The password sits in the freed allocation until
overwritten. Same applies to all caller-side disposal.

[ISSUE-undocumented-invariant: OOM during enlargeStringInfo
abandons partial line silently (low)] The comment at
`pg_get_line.c:43-45` warns "there'll be an ereport(ERROR) or
exit(1) inside stringinfo.c" — the cancellation path
(`prompt_ctx`) won't run for an OOM-triggered exit, so a partly
filled secret can survive in any process that wraps `pg_get_line`
in a setjmp/longjmp cleanup of its own.

## Potential issues

- The `fgets`-equivalence comment (line 41) means newlines are
  preserved; new callers commonly forget `pg_strip_crlf`. This is
  handled correctly by `simple_prompt` (`sprompt.c:152`).
- `errno` is explicitly preserved across `pfree`
  (`pg_get_line.c:67-71`) so callers can `if (ferror(stream))
  perror(...)` — a real but easy-to-break invariant.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
