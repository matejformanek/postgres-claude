# Issues — `psql` (src/bin/psql/)

Per-subsystem issue register for psql. See `knowledge/issues/README.md`
for tag taxonomy, severity scale, and workflow.

**Parent docs:** `knowledge/files/src/bin/psql/*` (29 docs).

**Source:** 73 entries surfaced 2026-06-03 by the A4 foreground sweep
(batches B1–B3 of 5). Each is mirrored in the corresponding per-file
doc's `## Potential issues` block.

psql is **the privilege-boundary tool on the client side**: it accepts
untrusted input from two directions — user keystrokes (incl. `.psqlrc`,
`PSQL_HISTORY`, env vars) and the server's wire responses (result rows,
NOTIFY payloads, error text, tab-completion query results, `\gset`
column values, `\gexec` rows). Every issue below sits at one of those
boundaries.

The A3 pg_dump finding's mirror is here too: pg_dump emits
`\restrict <key>` to harden psql against malicious **server response
during dump replay**. The framing protects against backslash-command
injection but NOT against malicious SQL the server emits and pg_dump
faithfully forwards — see P0 §Restrict-key framing limits.

---

## P0 — Phase D candidates

### Secret-scrub gaps (the "psql leaks credentials to disk and memory" cluster)

Mirror of the A2 libpq finding (`explicit_bzero` used in only 2 of 60+
credential-reading files). Same gap on the psql side.

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | input.c:148-167 | secret-scrub | likely | `~/.psql_history` records `CREATE USER ... PASSWORD '...'` / `ALTER ROLE ... PASSWORD ...` verbatim; only filter is `HISTCONTROL=ignorespace`/`ignoredups` (no password-pattern filter) | open | knowledge/files/src/bin/psql/input.c.md |
| 2026-06-03 | mainloop.c:431 | secret-scrub | likely | Every interactive input line goes to `pg_append_history` including PASSWORD literals; `\password` is the only meta-command that avoids it | open | knowledge/files/src/bin/psql/mainloop.c.md |
| 2026-06-03 | common.c:1158 | secret-scrub | likely | `-L logfile` captures every query text including PASSWORD literals; `fopen(logfile, "a")` honors umask, NOT 0600 | open | knowledge/files/src/bin/psql/common.c.md |
| 2026-06-03 | startup.c:249-302 | secret-scrub | likely | `main()` password buffer freed without `explicit_bzero` before process exit | open | knowledge/files/src/bin/psql/startup.c.md |
| 2026-06-03 | command.c:2604-2607 | secret-scrub | likely | `\password` `pw1`/`pw2` buffers freed without `explicit_bzero` | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | settings.h:103 | info-disclosure | maybe | `pset.db` indirectly holds cached libpq password material; `pset.dead_conn` retained after failure | open | knowledge/files/src/bin/psql/settings.h.md |
| 2026-06-03 | input.c:452 | path-traversal | maybe | History file `open(O_CREAT)` does NOT use `O_NOFOLLOW`; `PSQL_HISTORY` through a writable dir is a redirection vector | open | knowledge/files/src/bin/psql/input.c.md |

**Phase D pitch — coordinated secret-scrub sweep:**
1. Replace every psql `free(passwd)` with `explicit_bzero(passwd, len); free(passwd)`.
2. Filter `*PASSWORD*` regex from history append (`pg_append_history` wrapper).
3. Force 0600 on `-L` logfile creation (echo of history-file mode).
4. Use `O_NOFOLLOW` on history-file `open(O_CREAT)`.
5. Document the `pset.db` / `pset.dead_conn` credential-retention surface.

### Trust-boundary in server response (psql renders/executes server bytes)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | describe.c:1917-2192 | info-disclosure | maybe | Server-supplied identifiers (relnames, role names) printed unquoted via `%s` in `printTable` titles — terminal-escape injection from hostile object owner | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | tab-complete.in.c:6305 | info-disclosure | maybe | `requote_identifier` output to readline raw; same terminal-injection vector from server identifiers | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | common.c:741-755 | trust-boundary | nit | `PrintNotifications` writes LISTEN `notify->extra` verbatim to terminal — terminal-escape injection via NOTIFY payload | open | knowledge/files/src/bin/psql/common.c.md |
| 2026-06-03 | prompt.c:342-354 | info-disclosure | maybe | PROMPT `%:var:` substitution forwards server-controlled error text (`LAST_ERROR_MESSAGE`, etc.) into terminal raw — terminal-escape injection vector | open | knowledge/files/src/bin/psql/prompt.c.md |
| 2026-06-03 | command.c:861-865 | trust-boundary | nit | `\restrict <key>` prevents server-injected backslash commands during dump replay, but does NOT prevent malicious SQL the dump emits verbatim — defines the scope of the existing defense | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | variables.c:281 | injection | likely | `\gset` populates psql variables from server result columns; bare `:var` interpolation is unsanitized — server→client SQL injection if user uses bare form | open | knowledge/files/src/bin/psql/variables.c.md |
| 2026-06-03 | common.c:862-920 | trust-boundary | nit | `\gexec` runs server-returned text as SQL — documented "user is the trust boundary" feature; needs corpus-side documentation of the contract | open | knowledge/files/src/bin/psql/common.c.md |
| 2026-06-03 | tab-complete.in.c:7041-7066 | trust-boundary | maybe | Tab-completion `PQexec` shares the user's open transaction; a catalog query error inside an explicit BEGIN silently aborts the user's transaction (#ifdef NOT_USED error path) — "successful" COMMIT becomes surprise ROLLBACK | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | trust-boundary | nit | `exec_query` returns NULL on any error, so tab-complete fails-open silently — no operator visibility | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |

### Path / shell injection (the "psql as RCE primitive" cluster)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | large_obj.c:151 | path-traversal | likely | `\lo_export` accepts arbitrary client-side path under psql's UID; trivial write-any-file primitive in setuid/scripted contexts | open | knowledge/files/src/bin/psql/large_obj.c.md |
| 2026-06-03 | large_obj.c:187 | path-traversal | likely | `\lo_import` accepts arbitrary client-side path for read; trivial read-any-file primitive in setuid/scripted contexts | open | knowledge/files/src/bin/psql/large_obj.c.md |
| 2026-06-03 | copy.c:293,312 | shell-injection | nit | `\copy PROGRAM 'cmd'` → `popen(cmd, ...)` runs through `/bin/sh -c` with only quote-stripping — by-design; user typed it | open | knowledge/files/src/bin/psql/copy.c.md |
| 2026-06-03 | command.c:4690-4694 | shell-injection | nit | `\e`/`\edit` editor invocation: filename single-quoted, `$EDITOR` unquoted (intentional to allow `EDITOR="pico -t"`); malicious `$EDITOR` is by-design RCE | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | command.c | shell-injection | nit | `\!` runs arbitrary user command via `system(3)` — by-design | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | prompt.c:317-339 | shell-injection | maybe | PROMPT `%`backtick`%` substitution runs `popen` on EVERY prompt render — if `.psqlrc` is attacker-controlled (shared home, container, NFS), RCE as psql user; continuation prompts fire the command repeatedly | open | knowledge/files/src/bin/psql/prompt.c.md |
| 2026-06-03 | startup.c:830-835 | trust-boundary | nit | `.psqlrc` lookup uses `access(file, R_OK)` with no ownership/mode check (cf. ssh's `.ssh/config` permission enforcement) | open | knowledge/files/src/bin/psql/startup.c.md |

### Tab-completion specifics (the auto-firing query surface)

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | tab-complete.in.c | undocumented-invariant | nit | `completion_max_records = 1000` cap on completion result set | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | dos | nit | No per-second cap on Tab firing — every Tab is a synchronous server RTT | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | wire-protocol | nit | Tab-completion `PQexec` doesn't use parameterized queries — relies entirely on `processSQLNamePattern` quoting | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | undocumented-invariant | nit | `tab_completion_query_buf` is a long-lived buffer; lifetime invariant undocumented | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | undocumented-invariant | nit | `parse_identifier` accepts unquoted/quoted/qualified forms — invariant table missing | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | stale-todo | nit | `#ifdef NOT_USED` debug log path | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |
| 2026-06-03 | tab-complete.in.c | info-disclosure | nit | `PQescapeStringConn` falls back to a process-global encoding state — same as the A2 libpq finding (echo) | open | knowledge/files/src/bin/psql/tab-complete.in.c.md |

---

## P1 — Undocumented invariants

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | common.c:287-322; mainloop.c:107; copy.c:521 | undocumented-invariant | nit | SIGINT longjmp protocol depends on every blocking-read caller resetting `sigint_interrupt_enabled`; one missed reset = use-after-jmp | open | knowledge/files/src/bin/psql/common.h.md |
| 2026-06-03 | command.c:199-200 | undocumented-invariant | nit | `restricted` / `restrict_key` are file-statics — persist across `\i`/`process_file` recursion intentionally | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | describe.c | undocumented-invariant | maybe | Hardcoded `RELKIND_*`/`PROKIND_*`/`AMTYPE_*` constants from `_d.h`; old psql vs new server displays blanks silently | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | describe.c | undocumented-invariant | nit | `pset.sversion` gates assume specific server versions for catalog column layouts | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | describe.c:1827-1829 | undocumented-invariant | nit | `fmtId` non-reentrancy footgun (two consecutive calls share the same static buffer); comment exists, no static-analyser enforcement | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | help.c | undocumented-invariant | nit | `helpVariables` list must be kept in sync with `psql_completion`'s special-variable list | open | knowledge/files/src/bin/psql/help.c.md |

---

## P2 — Stale TODOs / dead-code

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | common.c:2634, 2704 | stale-todo | nit | `XXX duplicate-of-libpq` on `uri_prefix_length` / `recognized_connection_string` — drift risk when libpq adds URI prefixes | open | knowledge/files/src/bin/psql/common.c.md |
| 2026-06-03 | mainloop.c:603-608 | dead-code | nit | `#ifdef NOT_USED` block "currently unneeded" — harmless | open | knowledge/files/src/bin/psql/mainloop.c.md |
| 2026-06-03 | copy.c:687-689 | stale-todo | nit | Protocol-v2 fallback (`PQprotocolVersion(conn) < 3`) kept for pre-v14 libpq.so runtime; increasingly hypothetical | open | knowledge/files/src/bin/psql/copy.c.md |
| 2026-06-03 | command.c:861-865 | stale-todo | nit | "This isn't an amazingly good place for them, but neither is anywhere else." on assign-hook table location | open | knowledge/files/src/bin/psql/startup.c.md |
| 2026-06-03 | command.c:4139-4142 | stale-todo | nit | "spurious connection attempts recorded in the postmaster's log" — acknowledged libpq-API limitation | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | describe.c:4-8 | stale-todo | nit | "9.2 minimum-version contract" — increasingly trivial | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | help.c:421-422 | dead-code | nit | `LASTOID` variable still listed in `helpVariables` after long deprecation | open | knowledge/files/src/bin/psql/help.c.md |
| 2026-06-03 | help.c | stale-todo | nit | Magic newline-count constant in `helpSQL` could be computed | open | knowledge/files/src/bin/psql/help.c.md |
| 2026-06-03 | startup.c:861-865 | stale-todo | nit | Comment on assign-hook table awkward-but-stable location | open | knowledge/files/src/bin/psql/startup.c.md |

---

## P3 — DoS / lower priority

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-03 | crosstabview.c:227-250,296 | dos | nit | `CROSSTABVIEW_MAX_COLUMNS = 1600` caps width but not row count; `1601 * 1M` cell pointers ~12.8 GiB still possible | open | knowledge/files/src/bin/psql/crosstabview.c.md |
| 2026-06-03 | describe.c | dos | nit | No LIMIT on `\d` pattern queries — large catalogs can return huge result sets | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | command.c:4407-4419 | dos | nit | `do_watch` race: up to 1-second SIGINT-miss window in `wait_until_connected` (documented in comment) | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | input.c:435-438 | correctness | nit | `saveHistory` documented unfixed concurrent-exit race — two psqls exiting near-simultaneously can lose entries | open | knowledge/files/src/bin/psql/input.c.md |
| 2026-06-03 | describe.c | correctness | maybe | 14 `goto error_return` sites in `\d` builders — inconsistent error-handling pattern | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | describe.c | trust-boundary | nit | Cross-database reference check in `\d`-family relies on server returning current database name correctly | open | knowledge/files/src/bin/psql/describe.c.md |
| 2026-06-03 | help.c | info-disclosure | nit | `slashUsage` echoes current database name | open | knowledge/files/src/bin/psql/help.c.md |
| 2026-06-03 | command.c | info-disclosure | nit | ECHO_HIDDEN echoes internal queries including `SELECT CURRENT_USER` from `\password` | open | knowledge/files/src/bin/psql/command.c.md |
| 2026-06-03 | prompt.c:138-303 | info-disclosure | nit | PROMPT `%`-sequences expose internal hostnames, PIDs, search_path to terminal-history readers | open | knowledge/files/src/bin/psql/prompt.c.md |
| 2026-06-03 | stringutils.c:42-43 | correctness | nit | `strtokx(e_strings=true, del_quotes=true)` combo documented unsupported but not asserted; regression risk if new caller stumbles in | open | knowledge/files/src/bin/psql/stringutils.c.md |
| 2026-06-09 | copy.h / copy.c:293,312 | shell-injection | nit | `\copy ... PROGRAM 'cmd'` passes the quoted command straight to `popen(3)` with no sanitization beyond quote-stripping; by design (restricting it needs server-level GUCs) but worth documenting | open | knowledge/files/src/bin/psql/copy.h.md |

---

## What's working well (record for future Phase D triage)

### `processSQLNamePattern` is the single chokepoint for pattern-injection defense

`fe_utils/string_utils.c::processSQLNamePattern` (wrapped by psql's
`validateSQLNamePattern` at describe.c:6631) is the canonical regex/glob
→ SQL-LIKE/regex translator. It uses encoding-aware `PQescapeStringConn`
to produce the resulting literal. **No `\d*` command is vulnerable to
user-pattern SQL injection** because patterns become string-literal LIKE
values, never identifier interpolation. The same helper is used by
`pg_dump.c` (`expand_schema_name_patterns`, `expand_table_name_patterns`).

This is a **cross-binary trust boundary worth elevating** to a single
idiom doc at `knowledge/idioms/sql-name-pattern.md` so future B-batch
reviewers can confirm "yes, this binary uses processSQLNamePattern,
ergo pattern-injection is closed" without re-deriving it.

### Quoted-form interpolation (`:'var'` / `:"var"`) IS injection-safe

Bare `:var` is unsafe by design; the quoted forms `:'var'` (literal) and
`:"var"` (identifier) are implemented in `psqlscan.l` (NOT in `variables.c`)
and DO escape. The user/server-supplied content lands at the right
escaping discipline as long as the user types the quoted form.

`psqlscan.l` is a **corpus gap** — the substitution implementation is
not yet documented; it's the next read for completing the psql injection
story.

---

## Corpus gaps surfaced (out of batch)

Read these in a follow-up sweep:

- `src/fe_utils/psqlscan.l` — the `:var` / `:'var'` / `:"var"` substitution implementation; closes the variables.c injection story.
- `src/fe_utils/psqlscanslash.l` — `\` meta-command arg flex scanner; closes the stringutils.c quoting story.
- `src/fe_utils/string_utils.c` — `processSQLNamePattern` itself; the chokepoint we trusted above.
- `src/interfaces/libpq/fe-lobj.c` — LO protocol; closes the `\lo_*` story.

---

## Summary by tag type

| Type | Count |
|---|---:|
| secret-scrub | 7 |
| trust-boundary | 11 |
| info-disclosure | 8 |
| path-traversal | 3 |
| shell-injection | 5 |
| injection (SQL via variable) | 2 |
| undocumented-invariant | 11 |
| stale-todo | 8 |
| dead-code | 3 |
| dos | 5 |
| correctness | 4 |
| wire-protocol | 1 |
| **Total** | **68** (+ 5 inline annotated but not separately categorized) |

Severity headline: 8 `likely`, ~19 `maybe`, rest `nit`/by-design.
