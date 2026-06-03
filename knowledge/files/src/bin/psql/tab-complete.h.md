---
path: src/bin/psql/tab-complete.h
anchor_sha: 4b0bf0788b0
loc: 18
depth: shallow
---

# tab-complete.h

- **Source path:** `source/src/bin/psql/tab-complete.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 18

## Purpose

Trivial public face of `tab-complete.in.c`. Exposes exactly two
symbols. [verified-by-code, tab-complete.h:11-15]

- `extern PQExpBuffer tab_completion_query_buf;` — a process-global
  buffer that `mainloop.c` fills with previously-typed continuation
  lines before each Tab keypress, so that `get_previous_words()` can
  recover multi-line context (`tab-complete.in.c:7094-7104`).
  [verified-by-code]
- `extern void initialize_readline(void);` — called once at psql
  startup (`startup.c`) to register `psql_completion` as
  `rl_attempted_completion_function` and configure word-break
  characters, filename-quoting hooks, and the 1000-row LIMIT
  (`tab-complete.in.c:1537-1581`). [verified-by-code]

## Naming oddity — `.in.c`

The implementation file is `tab-complete.in.c`, not `.c`. It is
preprocessed at build time by `gen_tabcomplete.pl`, which (a)
populates a `tcpatterns[]` array of pre-extracted `Matches/HeadMatches/
TailMatches` rules and (b) rewrites the giant else-if chain in
`match_previous_words()` into a switch keyed by pattern id. The `.in.c`
file is also valid C as-is (the `#ifdef SWITCH_CONVERSION_APPLIED`
path falls back to the linear scan) so editing it directly still
compiles. [from-comment, tab-complete.in.c:7-13]

## Phase D notes

No external state crosses this header beyond the
`tab_completion_query_buf`. Any tab-complete query exposure / DoS
surface lives in `tab-complete.in.c`.

## Confidence tag tally
`[verified-by-code]=3 [from-comment]=1`
