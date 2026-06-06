---
path: src/include/fe_utils/psqlscan.h
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 93
depth: read
---

# `src/include/fe_utils/psqlscan.h`

- **File:** `source/src/include/fe_utils/psqlscan.h` (93 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-05)

## Purpose

Public API for the frontend SQL lexer shared by psql and pgbench. Exposes an opaque
`PsqlScanState` handle, the scan-result and prompt enums, the variable-quoting request enum,
the caller-supplied callback struct, and the lifecycle functions (`create`/`setup`/`scan`/
`reset`/`finish`/`destroy`). The lexer was originally part of psql — hence the names — but is
now reusable by any frontend that wants psql-compatible SQL tokenization with optional
`:variable` substitution. Internal state is in
[[knowledge/files/src/include/fe_utils/psqlscan_int.h]]. `[from-comment]` (:6-10)

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `PsqlScanState` | :27 | Opaque pointer to `PsqlScanStateData`. |
| `PsqlScanResult` | :30 | Termination state: SEMICOLON / BACKSLASH / INCOMPLETE / EOL. |
| `promptStatus_t` | :39 | Prompt selector: READY / CONTINUE / COMMENT / {SINGLE,DOUBLE,DOLLAR}QUOTE / PAREN / COPY. |
| `PsqlScanQuoteType` | :52 | Variable-quoting mode: PLAIN / SQL_LITERAL / SQL_IDENT / SHELL_ARG. |
| `PsqlScanCallbacks` | :61 | Single `get_variable` callback (NULL ⇒ no substitution). |
| `psql_scan_create` / `_destroy` | :70-71 | Lexer lifecycle. |
| `psql_scan_set_passthrough` | :73 | Set the void* handed to the callback. |
| `psql_scan_setup` / `_finish` | :75-78 | Begin/end scanning one input line (encoding + std_strings). |
| `psql_scan` | :80 | Scan up to the next semicolon/backslash; fills `query_buf` + prompt. |
| `psql_scan_reset` | :84 | Discard partial-statement state. |
| `psql_scan_reselect_sql_lexer` | :86 | Switch back to the SQL lexer after a slash-command lexer ran. |
| `psql_scan_in_quote` | :88 | Is the scanner mid-quote (for prompt/continuation)? |
| `psql_scan_get_location` | :90 | Report current line/offset (for error pointing). |

## Internal landmarks

- `PsqlScanQuoteType` (`:52-58`) is the security-relevant enum: `:'var'` requests
  `PQUOTE_SQL_LITERAL`, `:"var"` requests `PQUOTE_SQL_IDENT`, and the backtick/shell form
  requests `PQUOTE_SHELL_ARG`. The lexer hands these to the host's `get_variable` callback so
  the **host** owns the actual quoting (psql routes them through `appendShellString` /
  `appendStringLiteralConn` etc.). `[verified-by-code]`
- `PsqlScanCallbacks.get_variable` returns a *free'able* string or NULL for unknown variables
  (`:63-66`); a NULL pointer for the callback itself disables substitution entirely. `[from-comment]` (:63-66)

## Invariants & gotchas

- The lexer does not itself quote variable values — it only classifies the *requested* quoting
  via `PsqlScanQuoteType` and delegates to the callback. The injection-safety of `:'…'`/`:"…"`
  therefore lives in the consumer (psql), not here. `[verified-by-code]`
- `psql_scan_reselect_sql_lexer` (`:86`) exists because slash commands are lexed by a separate
  physical flex lexer; after one runs, the SQL lexer's start state must be reselected (the
  multi-lexer mechanism documented in `psqlscan_int.h`). `[from-comment]` (psqlscan_int.h:23-34)

## Cross-refs

- Internal state struct + the FF-substitution mechanism:
  [[knowledge/files/src/include/fe_utils/psqlscan_int.h]].
- Host quoting helpers the callback uses: [[knowledge/files/src/include/fe_utils/string_utils.h]].

## Potential issues

None at the header level — the quoting-delegation contract is sound and the injection surface
lives in the consumer's `get_variable` implementation.
