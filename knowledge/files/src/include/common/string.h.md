# src/include/common/string.h

## Purpose

Declares a handful of tiny string helpers (`pg_str_endswith`,
`strtoint`, `pg_clean_ascii`, `pg_strip_crlf`, `pg_is_ascii`),
the `PromptInterruptContext` used by `simple_prompt_extended`, and
the `pg_get_line*` family for line-oriented stdio input.

## Role in PG

Shared **frontend + backend**. Backend code calls `pg_clean_ascii`
when sanitising user-supplied strings before logging
(see `src/common/string.c.md`). Frontend tools (`psql`, `pg_dump`,
etc.) use `pg_get_line` and `simple_prompt`.

## Key declarations

- `struct PromptInterruptContext` — carries a `jmpbuf*` and an
  enable flag so SIGINT during a prompt can longjmp out without
  including `<setjmp.h>` here. (`string.h:18-24`)
- Sanitisers / classifiers: `pg_str_endswith`, `strtoint`,
  `pg_clean_ascii`, `pg_strip_crlf`, `pg_is_ascii`.
  (`string.h:27-32`)
- Line input: `pg_get_line`, `pg_get_line_buf`,
  `pg_get_line_append`. (`string.h:35-38`)
- Prompts: `simple_prompt`, `simple_prompt_extended`.
  (`string.h:41-43`)

## Phase D notes

`pg_clean_ascii` is the obvious choke point against terminal-escape
injection in server logs — see `string.c.md` for the actual
implementation review.

## Issues

[ISSUE-trust-boundary: `pg_strip_crlf(str)` (`string.h:31`) mutates
the string in place to remove trailing `\r`/`\n`. Used by
log-injection prevention paths (HBA-line reader, password prompts)
— but the header gives no semantics for embedded (non-trailing)
control characters (medium)] An attacker who can inject `\n` MID
string defeats the strip; `pg_clean_ascii` is the broader scrubber
and callers must pick correctly. Cross-link: A4 psql + A5 frontend
log-injection.

[ISSUE-trust-boundary: `simple_prompt`/`simple_prompt_extended`
(`string.h:41-43`) — used by every tool that asks for a password
(`pg_dump -W`, `psql -W`, `vacuumdb -W`, …). The returned buffer
is malloc'd and lifetime-managed by the caller; A4 secret-scrub
cluster: no `pg_explicit_bzero` wrapper, free does not wipe (low)]

[ISSUE-undocumented-invariant: `PromptInterruptContext`
(`string.h:18-24`) — `jmpbuf` is declared `void *` to avoid
`<setjmp.h>` here; type-checking is the caller's job (low)] A
caller that passes a wrong-typed pointer crashes on SIGINT during
prompt.

## Cross-refs

- A4 psql secret-scrub cluster — simple_prompt buffer lifetime.
- A5 `common.md` — log-injection prevention.
- Companion: `src/common/string.c.md`, `src/common/sprompt.c`.
