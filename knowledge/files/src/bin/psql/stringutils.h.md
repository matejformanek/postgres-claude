---
path: src/bin/psql/stringutils.h
anchor_sha: 4b0bf0788b0
loc: 30
depth: read
---

# stringutils.h

- **Source path:** `source/src/bin/psql/stringutils.h`
- **Lines:** 30
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `stringutils.c` (implementations), `psqlscanslash.l` (the heavier slash-arg scanner that `strtokx` complements).

## Purpose

Three quoting / tokenizing helpers used by psql's backslash-command parser and by the tab-completion code.

## Public surface

- `strtokx(s, whitespace, delim, quote, escape, e_strings, del_quotes, encoding)` (15) — quote-aware strtok replacement that does NOT overwrite its input (uses an internal `static` storage buffer). [verified-by-code, stringutils.h:15-22]
- `strip_quotes(source, quote, escape, encoding)` (24) — in-place removal of quoting from a token. [verified-by-code, stringutils.h:24]
- `quote_if_needed(source, entails_quote, quote, escape, force_quote, encoding)` (26) — opposite of `strip_quotes`; returns NULL if no quoting is needed. **Not** a substitute for `PQescapeStringConn`. [verified-by-code, stringutils.h:26-28]

## Phase D notes

- `strtokx` returns a pointer into a `static` buffer. Re-entrancy hazard if a SIGINT handler longjmps inside a `strtokx` loop and then a new call clobbers the buffer. Not a concern in psql's actual call sites (slash-command parsing is single-threaded and is bracketed by the SIGINT cleanup), but worth flagging for anyone copying the pattern. [verified-by-code, stringutils.c:61-83] [no concern]
- `quote_if_needed` allocates `2 * strlen(src) + 3` per call. For pathological inputs (e.g. a huge name in a tab-completed identifier) this is `O(N)` and unbounded; bounded by what a user can type so trivial. [verified-by-code, stringutils.c:305] [no concern]

## Confidence tag tally
`[verified-by-code]=5 [no concern]=2`
