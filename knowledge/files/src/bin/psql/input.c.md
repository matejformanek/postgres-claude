---
path: src/bin/psql/input.c
anchor_sha: 4b0bf0788b0
loc: 550
depth: deep
---

# input.c

- **Source path:** `source/src/bin/psql/input.c`
- **Lines:** 550
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `input.h`, `tab-complete.c` (registers tab-completion callback consumed via `tab_completion_query_buf`), `mainloop.c` (caller of `gets_interactive`), `command.c` (`\s` calls `printHistory`), `startup.c` (calls `initializeInput`).

## Purpose

Thin wrapper over GNU readline / libedit:
- `gets_interactive` — interactive line read with SIGINT handling.
- `gets_fromFile` — non-interactive fallback (also used when `USE_READLINE` is undefined or for `\i` script execution).
- History accumulation (multi-line entries glued together) and persistence to `~/.psql_history`.
- `\s` printing.

If built without `HAVE_LIBREADLINE`, all readline-dependent functions degrade gracefully (history disabled, `\s` reports "not supported").

## Public surface

- `gets_interactive(prompt, query_buf)` (66) — readline if enabled; `gets_fromFile(stdin)` otherwise. Calls `rl_reset_screen_size` (if available) to dodge a SIGWINCH-while-idle bug. Sets `sigint_interrupt_enabled = true` around the `readline()` call so Ctrl-C longjmps to the mainloop. Stashes `query_buf` into `tab_completion_query_buf` for the tab-complete callback to see. [verified-by-code, input.c:66-106]
- `pg_append_history(s, history_buf)` (112) — append a chunk to the running history-entry buffer; ensure trailing `\n`. [verified-by-code, input.c:111-123]
- `pg_send_history(history_buf)` (134) — emit the buffered entry to readline's `add_history`. Trims trailing `\n`s, applies `HISTCONTROL` (`ignorespace`/`ignoredups`), uses a function-level static `prev_hist` for dedup comparison. Resets buffer. [verified-by-code, input.c:134-171]
- `gets_fromFile(source)` (185) — line-at-a-time with a static `PQExpBuffer` (held across calls to avoid leaks if interrupted). [verified-by-code, input.c:185-242]
- `initializeInput(int flags)` (343) — when `flags & 1`: enable readline, call `initialize_readline` (tab-complete registration), `rl_variable_bind("comment-begin", "-- ")`, `rl_initialize` (reads `~/.inputrc`), `using_history`, resolve histfile path, `read_history`, `decode_history`. Always installs `atexit(finishInput)`. [verified-by-code, input.c:343-400]
- `printHistory(fname, pager)` (493) — `\s`. If `fname == NULL`, page to console via `PageOutput`; else `fopen(fname, "w")`. Iterates history with `BEGIN_ITERATE_HISTORY`. [verified-by-code, input.c:493-536]

## Statics

- `useReadline`, `useHistory` (31-32) — set by `initializeInput`.
- `psql_history` (34) — resolved path to history file. Owned by this file; freed in `finishInput`.
- `history_lines_added` (36) — counts entries added in this session; used in `saveHistory` for `append_history`'s nlines arg. [verified-by-code, input.c:36, 165, 448-457]
- `prev_hist` in `pg_send_history` (138) — static, leaked at exit by design.
- Static `PQExpBuffer buffer` in `gets_fromFile` (188) — never freed across the process lifetime, by design. Comment at 182-184 says: "we re-use a static PQExpBuffer for each call. This is to avoid leaking memory if interrupted by SIGINT."

## History encoding

- `NL_IN_HISTORY = 0x01` (47). Newlines in multi-line history entries are mapped to `0x01` on disk because readline parses the file as one-entry-per-line. `decode_history` runs after `read_history` to reverse the mapping; `encode_history` runs before `write_history`/`append_history`. [from-comment, input.c:39-47]
- `BEGIN_ITERATE_HISTORY` / `END_ITERATE_HISTORY` macros (277, 290) — paper over a libedit-vs-libreadline incompatibility where you must use `previous_history` for ascending iteration on libedit and `next_history` on libreadline. Comment at 247-275 is the canonical explanation of the kludge. [from-comment, input.c:247-275]

## History file resolution

`initializeInput` (369-389) picks the history path in this priority order:

1. psql variable `HISTFILE` (set via `\set HISTFILE ...` or `-v HISTFILE=...`).
2. Environment `PSQL_HISTORY`.
3. Default: `$HOME/.psql_history` (Unix) or `$HOME/psql_history` (Windows).

If step 1 or 2 supplies a path, `expand_tilde` is run on it (so `HISTFILE=~/foo` works). [verified-by-code, input.c:369-389]

## History file persistence

`saveHistory(fname, max_lines)` (412):

- If `fname == DEVNULL` ("/dev/null" on Unix), skip the write. Comment at 416-422 notes this dodges a macOS-specific `write_history`-chmods-target-file bug. [from-comment, input.c:416-422]
- `encode_history()` first (turns `\n` into `0x01`).
- Preferred path (`HAVE_HISTORY_TRUNCATE_FILE && HAVE_APPEND_HISTORY`): `history_truncate_file(fname, max - added)`, then `open(fname, O_CREAT | O_WRONLY | PG_BINARY, 0600)` to ensure file exists (workaround for `append_history` requiring pre-existing file), then `append_history(nlines, fname)`. Race-conditions on concurrent sessions are noted ("there are still race conditions when two sessions exit at about the same time"). [verified-by-code, input.c:440-463] [from-comment, input.c:435-438]
- Fallback path: `stifle_history(max_lines)` + `write_history(fname)`. Overwrites; comment says "Tough luck for concurrent sessions." [from-comment, input.c:469]

Mode `0600` is the only protection against other users reading the history file.

`finishInput` (539) — runs at `atexit`; calls `saveHistory(psql_history, pset.histsize)`. `pset.histsize == -1` means unlimited.

## Phase D notes

- **No filtering of password-containing lines.** Unlike most shells (which filter lines starting with whitespace via `HISTCONTROL=ignorespace`, but NOT `*PASSWORD*` patterns by default), psql's only filter is the same `HISTCONTROL` enum (`ignorespace`/`ignoredups`). **A `CREATE USER foo PASSWORD 'secret'` or `ALTER USER foo PASSWORD 'secret'` goes straight to `~/.psql_history` in plaintext.** [verified-by-code, input.c:148-167] [ISSUE-info-leak: psql history records CREATE/ALTER USER ... PASSWORD lines verbatim; no scrubbing (high — credentials persist on disk in 0600 file)]
- **History file mode is 0600.** Better than nothing; if `HISTFILE` is set to a directory the user controls, the open succeeds and the file lands there. If `HISTFILE` resolves to a location like `/tmp/psql_history`, the 0600 mode at create time helps but a pre-existing symlink could still redirect. `open(O_CREAT)` does not use `O_NOFOLLOW`. [verified-by-code, input.c:452] [ISSUE-tocttou: history-file create follows symlinks; PSQL_HISTORY pointing through a writable dir is a redirection vector (low — already-have-account threat model)]
- **`PSQL_HISTORY` env override.** Honored even in non-interactive mode if `flags & 1`. Standard env-trust model; psql honors many env vars (PGHOST, PGUSER, etc.) and `PSQL_HISTORY` joins that crowd. [verified-by-code, input.c:375-377] [no concern — by design]
- **Readline `~/.inputrc` is read** by `rl_initialize` at 363. `.inputrc` can rebind keys to arbitrary readline macros, but cannot execute shell. Standard readline trust. [verified-by-code, input.c:362-363] [no concern — by design]
- **Untrusted strings passed to readline.** `readline(prompt)` receives the prompt verbatim; readline interprets `RL_PROMPT_START_IGNORE`/`RL_PROMPT_END_IGNORE` markers (added by `prompt.c::%[`/`%]`) but does NOT execute prompt contents. Any terminal-escape sequence in the prompt would be passed through to the terminal raw. See `prompt.c.md` for the term-injection surface via `%:LAST_ERROR_MESSAGE:`. [verified-by-code, input.c:91] [no concern — readline doesn't execute prompts]
- **`add_history(s)` interprets `s` as-is.** No escape sequences. The line goes verbatim into the in-memory history; only the on-disk encoding maps `\n` → `0x01`. Multi-byte safety: `encode_history`/`decode_history` iterate byte-by-byte and only touch `0x0a`/`0x01`. Comment at 41-45 notes `0x00` can't be used because readline mishandles it; `0x01` is assumed never user-typed. [from-comment, input.c:39-47] [no concern]
- **`gets_fromFile` static buffer.** Lives forever; reset on each call. The "if interrupted by SIGINT we don't leak" rationale at 182-184 is the load-bearing reason it's static. [from-comment, input.c:182-184] [no concern]
- **`saveHistory` race on concurrent exit** is documented and unfixed. Two psqls exiting near-simultaneously can lose entries or interleave. [from-comment, input.c:435-438] [ISSUE-correctness: concurrent-exit history-file race documented but unfixed (low)]
- **Tab-completion callback's `tab_completion_query_buf` is a global.** Cleared after `readline()` returns. If readline ever recursed (it shouldn't), the stash/clear would leak. [verified-by-code, input.c:86, 97] [no concern]
- **`sigint_interrupt_enabled` window.** Set true immediately before `readline()`, cleared immediately after. If a SIGINT arrives during the few instructions between `enabled = true` and readline's own SIGINT handler being installed, the longjmp may corrupt readline's internal state. Documented as "probably short enough to be ignored" in the SIGWINCH comment but applies here too. [from-comment, input.c:74-80] [no concern — race documented]

## Cross-references

- `pset.histsize`, `pset.histcontrol`: see `settings.h.md`.
- Tab-completion: `tab-complete.c` (not in this batch).

<!-- issues:auto:begin -->
- [Issue register — `psql`](../../../../issues/psql.md)
<!-- issues:auto:end -->

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=8 [no concern]=6 [ISSUE]=3`
