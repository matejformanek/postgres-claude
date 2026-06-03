---
path: src/bin/psql/stringutils.c
anchor_sha: 4b0bf0788b0
loc: 342
depth: deep
---

# stringutils.c

- **Source path:** `source/src/bin/psql/stringutils.c`
- **Lines:** 342
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `stringutils.h`, `tab-complete.c` (`strtokx` user — parses partial input), `psqlscanslash.l` (flex scanner doing the heavier-lift slash-arg parsing; `strtokx` is the simpler companion), `command.c` (callers).

## Purpose

Three quote-aware text helpers:
- `strtokx` — strtok replacement that respects quoting / escapes / E-strings / mixed delimiters and **does not overwrite its input** (uses an internal `static` storage). The header calls it "a.k.a. poor man's flex". [from-comment, stringutils.c:17-18]
- `strip_quotes` — opposite operation: in-place quote removal from a token.
- `quote_if_needed` — opposite of `strip_quotes`; emits a malloc'd quoted form, or NULL if no quoting is needed.

## Public surface

### `strtokx(s, whitespace, delim, quote, escape, e_strings, del_quotes, encoding)` (51)

Calling convention:
- First call: pass non-NULL `s` to start a new tokenization. Function allocates a `2 * strlen(s) + 1` working copy and resets the persistent state. [verified-by-code, stringutils.c:71-83]
- Subsequent calls: pass `s = NULL` to continue.
- Returns pointer into the persistent buffer; NULL when no more tokens. Returns NULL ALSO frees the buffer. [verified-by-code, stringutils.c:93-100]

Token kinds:
1. **Delimiter character.** If `delim` is set and current char is in it, return that single char as a 1-char token. [verified-by-code, stringutils.c:103-127]
2. **E-string.** If `e_strings` is set and current is `E'` or `e'`, treat as a quoted token with `escape = '\\'`. [verified-by-code, stringutils.c:131-138]
3. **Quoted token.** If quote-char matches, scan to closing quote. Inside the quoted region: `escape` followed by anything but `\0` is a 1-char escaped sequence; `quote quote` is a doubled (literal) quote. Multi-byte chars stepped via `PQmblenBounded`. If `del_quotes`, call `strip_quotes` after scan. [verified-by-code, stringutils.c:140-181]
4. **Bare token.** Scan until next whitespace / delim / quote. [verified-by-code, stringutils.c:183-225]

The "insert null to terminate the returned token" idiom: if the boundary char is whitespace, overwrite it with `\0`; otherwise `memmove` everything one byte right (the 2× buffer makes room) and place `\0`. This is how the function preserves the caller's logical view that tokens are NUL-terminated even when adjacent in source.

### `strip_quotes(source, quote, escape, encoding)` (240)

In-place. Skips leading quote (if present), then walks the string: at the closing quote (last char) exit; at `quote quote` advance source past the doubled quote (writing one); at `escape <X>` advance past the escape (writing X). Multi-byte stepping via `PQmblenBounded`. [verified-by-code, stringutils.c:240-271]

Asserts: `source != NULL`, `quote != '\0'`.

### `quote_if_needed(source, entails_quote, quote, escape, force_quote, encoding)` (291)

Allocates `2 * strlen(src) + 3` for the result. Writes `quote`, then walks input: doubling embedded `quote` chars, doubling embedded `escape` chars, and setting `need_quotes=true` if any char appears in `entails_quote`. Closing quote. If `!need_quotes` (and not `force_quote`), free and return NULL. Otherwise return the malloc'd quoted form. **Explicit warning in header comment: NOT a substitute for `PQescapeStringConn`.** Used only for psql-internal scanning (tokens to be re-parsed by `strtokx` or `psql_scan_slash_option`). [from-comment, stringutils.c:286-290] [verified-by-code, stringutils.c:291-342]

## State

- `static char *storage` (61) and `static char *string` (63) inside `strtokx` — persist between calls within one tokenization run. Freed when `strtokx` returns NULL (end of input). **Re-entrancy hazard:** two concurrent `strtokx` walks corrupt each other. psql is single-threaded so OK. [verified-by-code, stringutils.c:61-83, 93-100]

## Phase D notes

- **`strtokx` is NOT a SQL escaper.** The header comment is emphatic: this and `quote_if_needed` are for psql-internal parsing of slash-command arguments, not for building SQL. Anything user-typed that flows from `strtokx` into `PSQLexec` MUST go through `PQescapeStringConn` or fmtId-style quoting. [from-comment, stringutils.c:286-290] [no concern — caller contract]
- **The `static` storage** means a SIGINT-longjmp out of `strtokx` and then a re-entry with a fresh `s` is safe (`free(storage)` happens first thing at 73). But a longjmp out followed by re-entry with `s = NULL` walks the abandoned buffer. psql's mainloop always restarts tokenization after a longjmp, so this is moot. [verified-by-code, stringutils.c:71-83] [no concern]
- **`memmove` to insert NUL** at token boundaries. The 2× buffer allocation ensures we never overflow. If the input is `N` bytes, the buffer is `2N + 1`. Worst case is N tokens each requiring a memmove of decreasing tail length; total work O(N²). For psql slash-command args (small) this is fine. [verified-by-code, stringutils.c:79-80, 113-119, 163-169, 212-218] [no concern]
- **Multibyte handling.** Inside quoted tokens, `PQmblenBounded` is used so multi-byte chars don't get split when scanning for the closer. Outside quoted tokens (the bare-token scan at 188), `strcspn` operates byte-wise — but the delimiter sets passed in are all ASCII (`whitespace`, `delim`, `quote`), so byte-wise scanning is correct for any encoding that's an ASCII superset (PG always uses such). [verified-by-code, stringutils.c:146, 188, 265] [no concern]
- **`strip_quotes` infinite-loop guard.** Loop exits when `*src == '\0'`. The `c == quote && src[1] == '\0'` case (258) breaks out before the multi-byte step; otherwise we'd consume the closing quote and walk past end. Looks correct. [verified-by-code, stringutils.c:253-270] [no concern]
- **`quote_if_needed` allocates 2x+3.** Worst case `source` is all `quote` characters: each one doubles. So result is `1 + 2*strlen + 1 = 2*strlen + 2`. The `+3` slot is for slack. No overflow. [verified-by-code, stringutils.c:305-333] [no concern]
- **Argument-boundary mis-parsing.** The header note at 47-49 warns: "it's okay to vary delim, quote, and escape from one call to the next on a single source string, but changing whitespace is a bad idea since you might lose data." A caller that mid-tokenize switches whitespace can drop bytes. No security implication; correctness gotcha. [from-comment, stringutils.c:47-49] [no concern]
- **No tests in this file** for the e_strings + del_quotes combo. The header comment says it's "not currently handled" (line 42-43); if a future caller passes both, behavior is undefined. **A regression risk** if tab-complete or a new slash-command stumbles into this combo. [from-comment, stringutils.c:42-43] [ISSUE-correctness: `strtokx(e_strings=true, del_quotes=true)` combo is documented as unsupported but not asserted (low)]

## Cross-references

- `psqlscan.l` and `psqlscanslash.l` for the heavier flex-based parsers.
- `PQmblenBounded`: `src/interfaces/libpq` (mbutils).

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=4 [no concern]=7 [ISSUE]=1`
