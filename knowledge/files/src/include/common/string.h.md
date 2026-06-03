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

## Potential issues

None at the header level.
