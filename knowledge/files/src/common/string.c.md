# src/common/string.c

## Purpose

Tiny shared string utilities: postfix test (`pg_str_endswith`),
ranged `strtol` (`strtoint`), ASCII sanitizer (`pg_clean_ascii`),
ASCII classifier (`pg_is_ascii`), and CRLF stripper
(`pg_strip_crlf`).

## Role in PG

Shared **frontend + backend**. Backend uses `pg_clean_ascii` to
filter user-supplied strings (application_name, database name,
roles) before they hit `elog`/`ereport` output and end up in
server logs, where terminal escape sequences could otherwise
mess up an admin's `tail -f`.

## Key functions

- `bool pg_str_endswith(const char *str, const char *end)` — trivial
  suffix test using `strcmp`. (`string.c:31-43`)
- `int strtoint(...)` — wraps `strtol`, sets `errno=ERANGE` on
  truncation to int. (`string.c:50-58`)
- `char *pg_clean_ascii(const char *str, int alloc_flags)` —
  passes printable ASCII (0x20-0x7E) through; replaces anything
  else (control chars, high-bit bytes) with the literal four-byte
  string `\xNN`. Worst-case allocation is `strlen(str)*4 + 1`.
  Backend uses `palloc_extended(alloc_flags)`; frontend uses raw
  `malloc()`. Returns NULL on alloc failure (in MCXT_ALLOC_NO_OOM
  path). (`string.c:84-125`)
- `bool pg_is_ascii(const char *str)` — true iff no high-bit byte
  in the NUL-terminated string. (`string.c:131-141`)
- `int pg_strip_crlf(char *str)` — in-place trim of trailing
  `\r`/`\n`, returns new length. (`string.c:154-163`)

## State / globals

None — all pure functions.

## Phase D notes

`pg_clean_ascii` is the documented chokepoint for filtering
attacker-influenced strings before logging. The header comment
admits this is a stopgap: "This function should NOT be used —
instead, consider how to handle the string without needing to
filter out the non-ASCII characters" (`string.c:76-82`). Multibyte
characters get fully byte-by-byte escaped; the result is ugly but
safe against ANSI escape injection.

`pg_strip_crlf` deliberately stops at `\r`/`\n` only — embedded
nulls and other control bytes are NOT stripped. Callers must
sanitise separately (typically via `pg_clean_ascii`).

## Potential issues

`[ISSUE-undocumented-invariant: pg_clean_ascii allocates 4× input
length; long attacker-controlled strings (e.g. application_name set
by hostile client) translate into a 4× memory amplification in the
log path. Currently bounded by application_name length limit
(NAMEDATALEN-1), but the file does not state that assumption.
(maybe)]`

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `common`](../../../issues/common.md)
<!-- issues:auto:end -->
