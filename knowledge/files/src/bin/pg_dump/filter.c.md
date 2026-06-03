---
path: src/bin/pg_dump/filter.c
anchor_sha: 4b0bf0788b0
loc: 475
depth: deep
---

# filter.c

- **Source path:** `source/src/bin/pg_dump/filter.c`
- **Lines:** 475
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `filter.h` (the `FilterStateData`, command-type and object-type enums), `pg_dump.c` / `pg_dumpall.c` / `pg_restore.c` (callers, each pass their own `exit_nicely` as the `exit_function` callback).

## Purpose

Parser for the `--filter=<file>` option introduced in v17. The filter file format is one rule per line:

```
[include|exclude] <object_type> <pattern>
```

with `#` comments, blank lines, multi-line patterns continued by quoted strings spanning newlines, and an opt-in stdin path (`--filter=-`). The parser returns one (command, object-type, pattern) triple per call to `filter_read_item`. [from-comment, filter.c:368-390]

## Public surface

- `filter_init(fstate, filename, f_exit)` (36) — opens file or assigns stdin; stashes the caller's `exit_nicely` so error paths in static helpers can terminate without linking to pg_dump-specific symbols. [verified-by-code, filter.c:35-54]
- `filter_free(fstate)` (60) — closes fp (unless stdin), frees the line-buffer. [verified-by-code, filter.c:59-75]
- `filter_object_type_name(fot)` (82) — enum → English name; `pg_unreachable()` on bad enum. [verified-by-code, filter.c:81-114]
- `filter_read_item(fstate, **objname, *comtype, *objtype)` (392) — reads one rule. Returns true on success, false on EOF; exits on parse error. The `*objname` is a freshly initialised `PQExpBuffer.data` — caller owns it. [verified-by-code, filter.c:391-475]
- `pg_log_filter_error(fstate, fmt, …)` (154) — wraps `pg_log_error` with file/line context. `printf(2,3)`-attributed via the header. [verified-by-code, filter.c:153-169]

## Static helpers

- `get_object_type(keyword, size, *objtype)` (122) — 12-entry `is_keyword_str` ladder mapping `table`/`schema`/`function`/etc to the enum. [verified-by-code, filter.c:121-150]
- `filter_get_keyword(**line, *size)` (179) — non-whitespace token at the head of the line. [verified-by-code, filter.c:178-208]
- `read_quoted_string(fstate, str, pattern)` (217) — multi-line quoted identifier. Reads `pg_get_line_buf` for continuation lines. Handles `""` → `"`, `\n` → newline, `\\` → `\`. [verified-by-code, filter.c:216-285]
- `read_pattern(fstate, str, pattern)` (302) — drives the parse for one pattern, normalising whitespace and dispatching to `read_quoted_string` on `"`. Treats `#` outside quotes as a comment-to-EOL. [verified-by-code, filter.c:301-366]

## Format grammar (from `read_pattern` + `read_quoted_string`)

- Whitespace separates lexical tokens but inside a pattern it is collapsed to single spaces.
- `"…"` quotes a possibly-multi-line identifier; `""` inside is a literal `"`.
- Inside a quoted string, `\n` is a literal newline (NOT a continuation), `\\` is `\`, no other `\<x>` escapes are documented and the implementation silently consumes the `\` then appends nothing — see filter.c:270-278.
- `.()`, are treated as identifier-joining punctuation (qualified names + routine signatures); `,` becomes `, `; `(` and `)` are kept.
- `#` outside a quoted string ends the line (comment).

## Phase D — surfaces of concern

- **The pattern is NOT quoted before being fed downstream.** `filter_read_item` returns the raw `pattern.data` as `*objname`. Pg_dump / pg_dumpall then pass that string to the existing `expand_*_name_patterns` infrastructure, which uses `processSQLNamePattern` → SQL `LIKE` or regex queries against the catalog. So the dump-side trust path is: filter pattern → `processSQLNamePattern` → server-side LIKE. Quoting is the consumer's responsibility. [verified-by-code, filter.c:453-456; consumer in pg_dump.c::expand_table_name_patterns — not audited here] [maybe]
- **Backslash escape silently swallows unknown escapes** (filter.c:270-278). `\n` → newline, `\\` → `\`, anything else → the `\` AND the next byte are both consumed but only nothing is appended (the increment `str++` at 278 always runs). So a pattern containing `\"` ends up with neither byte in the output — effectively a way to comment out a character. Documented behaviour: zero. [verified-by-code, filter.c:270-278] [maybe — surfaces as silent data loss, NOT injection]
- **`read_pattern` keeps consuming until `*str == '\0' || '#'`**, then returns. There's no length cap on a single pattern. A 16-GB single-line pattern would `pg_get_line_buf` + `appendPQExpBufferChar` until OOM (which raises pg_fatal). [verified-by-code, filter.c:301-366] [no concern — bounded by available RAM]
- **`filter_init` calls `fopen(filename, "r")`** with the raw user-supplied path. No path-traversal check; `--filter=/etc/shadow` would attempt to read it (with the user's own privileges), find no `include`/`exclude` lines, and pg_log_error → exit. [verified-by-code, filter.c:43-51] [no concern — same trust level as any `--file=` flag]
- **`pg_log_filter_error` uses a 256-byte stack buffer** with `vsnprintf` — bounded. [verified-by-code, filter.c:157-161] [no concern]
- **No glob / regex DoS surface here.** This file does only literal token splitting; the regex is built later in `processSQLNamePattern`. [verified-by-code]
- **Multi-line quoted string trusts `pg_get_line_buf`** to handle ferror; explicit `ferror(fstate->fp)` check after EOF (filter.c:241-247). [verified-by-code, filter.c:240-249]
- **Stdin path (`--filter=-`)** is treated identically to a file but the error messages say "read from standard input" instead of naming the file. No special handling beyond that. [verified-by-code, filter.c:43, 163-168]

## Cross-references

- Callers: `pg_dump.c::read_dump_filters`, `pg_dumpall.c::read_dumpall_filters`, `pg_restore.c::read_restore_filters` (each passes its own `exit_nicely`).
- Pattern downstream: `processSQLNamePattern` in `fe_utils/string_utils.c` — handles wildcard expansion and the actual catalog query.
- See also: `knowledge/files/src/bin/pg_dump/filter.h.md` (the data types).

## Open questions

- Does any consumer of `*objname` re-quote the pattern, or does `processSQLNamePattern` accept it as a `LIKE` operand directly? A bad pattern like `%; DROP TABLE x; --` would be passed as a string literal to the server-side query — `processSQLNamePattern` does its own `appendStringLiteralConn` quoting, so injection seems closed. But this should be verified at the consumer side. [unverified — flagged for pg_dump.c per-file doc]
- Whether the silent-swallow of unknown backslash escapes is intentional or a parser bug. Not documented anywhere in the file. [unverified]

## Confidence tag tally
`[verified-by-code]=17 [from-comment]=1 [maybe]=2 [no concern]=4 [unverified]=2`
