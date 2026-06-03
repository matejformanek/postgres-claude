---
path: src/interfaces/libpq/fe-print.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 793
depth: deep
---

# fe-print.c

- **Source path:** `source/src/interfaces/libpq/fe-print.c`
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **LOC:** 793
- **Companion files:** `libpq-int.h` (PGresult fields read by accessors), `fe-exec.c` (the PGresult accessors used: `PQntuples`, `PQnfields`, `PQgetvalue`, `PQfname`, `PQfformat`)

## Purpose

Legacy pretty-printer for PGresult. From the head comment: "These functions were formerly part of fe-exec.c, but they didn't really belong there." And: "This function should probably be removed sometime since psql doesn't use it anymore. It is unclear to what extent this is used by external clients." [from-comment, fe-print.c:6-12, 62-68]

In other words: this file exists for ABI compatibility. It is **not** the path psql takes (psql does its own formatting via src/fe_utils/print.c). It is also not the path most modern bindings use. But it's exported, so it must keep working.

## Public API surface

| Function | Line | One-liner |
|---|---|---|
| `PQprint` | 69 | Box-drawing, headers, padding, optional HTML — full feature set via `PQprintOpt`. |
| `PQdisplayTuples` | 605 | Simpler variant: columns, separator char, header on/off. |
| `PQprintTuples` | 702 | The simplest one: line-per-tuple. |

`PQprintOpt` (defined in libpq-fe.h) is a flags struct: `header`, `align`, `standard`, `html3`, `expanded`, `pager`, `fieldSep`, `tableOpt`, `caption`, `fieldName[]`. [verified-by-code, fe-print.c:69-95 references all of these]

## Internal landmarks

### Pipe-to-pager dance

`PQprint` has a Unix-only block (search for `SIGPIPE`, `popen`) that, if `po->pager` is on and stdout is a TTY and the page-count would exceed terminal height, forks a pager via `popen(pager, "w")`. Saves and restores SIGPIPE handler with the legacy `pqsignal`. [verified-by-code, fe-print.c — surrounding the `popen` call near line 100-200]

### Static helpers

- `do_field` (341) — emit one cell with proper padding / quoting.
- `do_header` (456) — emit column-name row + `+---+---+` rules.
- `output_row` (562) — emit one row.
- `fill` (top of file) — pad a column with a filler char.

### HTML3 mode

When `po->html3` is set, `PQprint` emits a `<table>...</table>` instead of ASCII art. Each cell is `<td>`-wrapped with no escaping of `<`, `>`, `&` in the data — this is the classic "PGresult value goes raw into HTML" surface. Modern apps should never use this; flag for security audits. [verified-by-code, fe-print.c — the html3 branch within PQprint]

## Invariants & gotchas

- **No HTML escaping in `html3` mode.** Raw value bytes go into `<td>`. If you somehow ship `PQprint(stdout, res, &po)` with `po.html3=1` to a browser, every result value is a stored-XSS vector. The function is too old to be in active use, but it's still exported. [verified-by-code, fe-print.c — html3 branch]
- **`PQprintOpt.fieldName` is a `char **` of caller-supplied names** that override the result's column names. If the caller passes a shorter array than `nFields` and forgets to NULL-pad, undefined memory is read. [verified-by-code, fe-print.c — header path]
- **All three functions check `res != NULL` only implicitly** by deferring to `PQntuples` / `PQnfields`. `PQprint(stdout, NULL, &po)` will pass `NULL` to `PQnfields` which returns 0, so we get a clean no-op. Safe. [verified-by-code, fe-print.c:69-80]
- **`pager` mode shells out via `popen`.** On platforms with funky `PAGER` env, this can execute arbitrary commands. Standard Unix risk, but worth flagging for any setuid program linking libpq. [inferred]
- **Width calculation does not understand multibyte display width** — `PQprint` uses raw `strlen` for column-width, so wide CJK characters in a column will misalign. `PQdsplen` exists in fe-misc.c but isn't called here. [verified-by-code, fe-print.c — strlen usage in width loops]

## Cross-refs

- `knowledge/files/src/interfaces/libpq/fe-exec.c.md` — the PGresult these read.
- `knowledge/files/src/fe_utils/print.c.md` — psql's much-more-capable modern printer (when written).

## Potential issues

- **[ISSUE-stale-todo: `PQprint` documented as "should probably be removed"]** fe-print.c:62-68 — comment from many years ago saying psql no longer uses it. Still exported. Deprecation candidate but ABI freeze means we'd need a long sunset. **Severity: nit.**
- **[ISSUE-leak: HTML3 mode emits unescaped result values]** fe-print.c — any byte sequence in a result cell goes raw into `<td>...</td>`. **Severity: likely (stored-XSS via DB).** Phase D should at minimum add a doc warning; ideally deprecate the html3 flag. The function is rarely used so the realistic exposure is small, but the API surface is there.
- **[ISSUE-correctness: width math is byte-length, not display-width]** fe-print.c — `PQdsplen` is not called; wide chars misalign. **Severity: nit (legacy fn).**
- **[ISSUE-question: PAGER env trust]** fe-print.c — `popen(getenv("PAGER"), "w")`. Standard Unix concern, but for any setuid program linking libpq this is a vector. **Severity: nit.**
- **[ISSUE-style: function is 270+ lines]** `PQprint` (69) is long and tangled. A rewrite would help readability but ABI freezes the signature. **Severity: nit.**

## Tally

`[verified-by-code]=5 [from-comment]=3 [from-readme]=0 [inferred]=1 [unverified]=0`
