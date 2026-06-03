---
path: src/bin/psql/prompt.c
anchor_sha: 4b0bf0788b0
loc: 437
depth: deep
---

# prompt.c

- **Source path:** `source/src/bin/psql/prompt.c`
- **Lines:** 437
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `prompt.h`, `settings.h` (consumer of `pset.prompt1`/`2`/`3`), `mainloop.c` (caller — feeds the result to readline), `variables.c` (`%:name:` lookup).

## Purpose

Single function: `get_prompt(promptStatus_t, ConditionalStack)`. Takes one of `pset.prompt1`/`pset.prompt2`/`pset.prompt3` based on parser state, expands `%`-substitutions in tcsh style, and returns a pointer into a **256-byte `static` buffer**. [verified-by-code, prompt.c:70-74]

## The `%` substitution alphabet

The header comment at 22-67 enumerates all expansions. Implemented in the big switch at lines 110-374:

- `%/`, `%~` — current database; `~` collapses to literal `~` if db matches user or `$PGDATABASE`.
- `%M`/`%m` — host (full/short). Returns `"[local]"` or `"[local:/path]"` for UNIX sockets.
- `%>` — port.
- `%n` — `session_username()` (NOT necessarily `PQuser` — this is `SELECT session_user`).
- `%S` — `search_path` via `PQparameterStatus`.
- `%s` — value of psql var `SERVICE`.
- `%p` — `PQbackendPID`.
- `%P` — pipeline status: `on`, `abort`, or `off`.
- `%i` — `in_hot_standby` → `standby`/`primary`/`?`.
- `%x` — transaction status: empty / `*` / `!` / `?`.
- `%w` — whitespace as wide as the previous PROMPT1 (for PROMPT2 alignment). Caches `last_prompt1_width` in a function-level static. [verified-by-code, prompt.c:79, 390-433]
- `%R` — state indicator. PROMPT1: `=`/`^`/`!`/`@`. PROMPT2: `-`/`'`/`"`/`$`/`*`/`(`. PROMPT3: empty.
- `%l` — `pset.stmt_lineno`.
- `%#` — `#` if superuser, `>` otherwise. `is_superuser()` checks current role.
- `%[0-9]` and `%0[0-7]` — octal char code via `strtol(p, ..., 8)`. [verified-by-code, prompt.c:216-226]
- ``%`cmd` `` — `popen(cmd, "r")`, take first line of stdout, strip CRLF. **Runs as the psql user under `/bin/sh`** (popen). [verified-by-code, prompt.c:317-339]
- `%:name:` — value of psql variable `name` via `GetVariable(pset.vars, name)`. [verified-by-code, prompt.c:342-354]
- `%[` / `%]` — readline `RL_PROMPT_START_IGNORE`/`END_IGNORE` markers so non-printing escape sequences (color codes etc.) don't confuse cursor accounting. [from-comment, prompt.c:359-365]
- `%%` and default — pass through.

## Width accounting

After building the prompt for PROMPT1, scan it and compute display width using `PQmblen` + `PQdsplen`, skipping anything between `RL_PROMPT_START_IGNORE` and `RL_PROMPT_END_IGNORE`. `\n` resets the width counter. Result is cached in the function-level `static size_t last_prompt1_width` and used the next time PROMPT2's `%w` runs. [verified-by-code, prompt.c:390-433]

## State / lifetime

- 256-byte `static char destination[MAX_PROMPT_SIZE + 1]` — output buffer. **REUSED across calls.** Caller must consume before next `get_prompt`. [verified-by-code, prompt.c:73-74] Mainloop hands directly to `readline()` which copies, so this is safe.
- `static size_t last_prompt1_width = 0` — cross-call cache for `%w`. [verified-by-code, prompt.c:79]

## Phase D notes

- **`%\`backtick\` ⇒ popen.** Anything a user puts inside backticks in PROMPT1/2/3 is executed under `/bin/sh`. The PROMPT vars themselves can be set by `~/.psqlrc`, by `\set`, or by `psql -v PROMPT1=...`. Trust boundary is the psql user — same as `\!`. **However**: if `~/.psqlrc` is world-writable, an attacker controls every prompt-render. Also, a PROMPT containing `` %`rm -rf ~` `` triggers on EVERY prompt render including PROMPT2's continuation prompts — i.e. command sequences accumulate. [verified-by-code, prompt.c:317-339] [ISSUE-rce: PROMPT backtick runs popen on every redraw; if PROMPT is set by an attacker-controlled `.psqlrc` they get RCE as the psql user (high in adversarial multi-user env, low in typical single-user)]
- **`%`-substitution information disclosure.** A user who copy-pastes their terminal log shares: `%n` session user, `%/` database name, `%M`/`%m` server hostname (potentially internal), `%>` port, `%p` backend PID, `%x` transaction state, `%i` standby status, `%S` `search_path`. The PID + transaction state is enough to correlate logs server-side. **Typical low-impact info leak**, but worth tagging. [verified-by-code, prompt.c:138-303] [ISSUE-info-leak: PROMPT %-sequences expose internal hostnames, PIDs, search_path to terminal-history readers (low)]
- **`%:name:` reads any psql variable.** That includes things like `LASTOID` (set by `\lo_import`), `LAST_ERROR_MESSAGE`, `LAST_ERROR_SQLSTATE`, etc. A PROMPT that interpolates `:LAST_ERROR_MESSAGE` displays whatever the server sent in the last error — which is server-controlled text rendered through the user's terminal. **Terminal-escape injection vector**: a malicious server could craft an error message containing ANSI escapes; if that error msg makes it into PROMPT via `%:LAST_ERROR_MESSAGE:`, the escapes render. Mitigation: terminals typically filter dangerous sequences, and the default PROMPT does NOT include any `%:LAST_*:`. [verified-by-code, prompt.c:342-354] [ISSUE-info-leak/term-injection: PROMPT %:var: forwards server-controlled error text to terminal raw (maybe — depends on what the user sets in PROMPT)]
- **Width-accounting limit.** `MAX_PROMPT_SIZE = 256`. A PROMPT longer than 256 bytes gets silently truncated. The truncation can land mid-multibyte-char; `PQmblen` in the width-accounting pass has a `p + chlen > end` guard that breaks out. [verified-by-code, prompt.c:73, 104, 417-419] [no concern]
- **`%`-followed-by-unknown.** Falls through to the `default` arm and outputs the literal character without the `%`. So `%Z` becomes `Z`. Not an error. [verified-by-code, prompt.c:370-373] [no concern]
- **`%\`backtick\` parsing has no recursion limit but is bounded by `strcspn(p+1, "`")` and the outer 256-byte cap.** A `%\``without a closing backtick reads until end-of-string and then `pclose` runs whatever the partial command was. [verified-by-code, prompt.c:319-322] [no concern — pathological PROMPT only]
- **`fflush(NULL)`** before `popen` (324) flushes all stdio streams so the child sees committed output. Standard idiom. [verified-by-code, prompt.c:324] [no concern]
- **`session_username()`** at 171 is the psql helper that runs `SELECT session_user`. So `%n` requires a connection round-trip — slow prompts on a high-latency link. Cached? Read of `common.c::session_username` would say; from prompt.c alone it appears to be called every prompt-render. [inferred, prompt.c:169-172] [maybe — perf, not security]

## Cross-references

- `pset.vars` — see `knowledge/files/src/bin/psql/variables.c.md`.
- `pset.prompt1`/`2`/`3` storage — see `knowledge/files/src/bin/psql/settings.h.md`.
- `RL_PROMPT_START_IGNORE` semantics — readline manual; psql relies on `>= 4.0`.

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=2 [inferred]=1 [no concern]=4 [ISSUE]=3`
