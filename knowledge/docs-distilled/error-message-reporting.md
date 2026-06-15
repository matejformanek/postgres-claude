---
source_url: https://www.postgresql.org/docs/current/error-message-reporting.html
fetched_at: 2026-06-14T19:35:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Reporting Errors Within the Server (§55.2)

The canonical reference for `ereport()` / `elog()` and the auxiliary-call zoo.
This is the docs companion to the `error-handling` skill; quote the skill for
the SQLSTATE-picking + PG_TRY/PG_CATCH-cleanup procedure, this for the call
surface.

## ereport() — one required level + errmsg, everything else auxiliary

- **`ereport(elevel, errcode(...), errmsg(...), ...)`** is the modern form. Only
  the **elevel** and **`errmsg()`** are mandatory; `errcode()`, `errdetail()`,
  `errhint()`, `errcontext()` are optional auxiliaries. **Since PG12** the extra
  parens around the auxiliary list are optional (older code wraps them). [from-docs]
- **If elevel ≥ ERROR the call does not return** (it longjmps / aborts); below
  ERROR it returns normally. That control-flow fact is why post-ereport code is
  unreachable for ERROR and why cleanup must go in PG_CATCH, not after. [from-docs]
  [cross: knowledge/idioms — see skill `error-handling`]

## The auxiliary calls worth knowing

- **`errcode(sqlerrcode)`** — SQLSTATE from macros in `src/include/utils/errcodes.h`.
  Defaults if omitted: `ERRCODE_INTERNAL_ERROR` (ERROR+), `ERRCODE_WARNING`
  (WARNING), `ERRCODE_SUCCESSFUL_COMPLETION` (NOTICE and below). [from-docs]
- **`errcode_for_file_access()` / `errcode_for_socket_access()`** — translate the
  current `errno` into the right SQLSTATE for a failed syscall; use instead of
  hand-picking a code. [from-docs]
- **`errdetail()` / `errhint()` / `errcontext()`** — secondary message, fix
  suggestion, and call-stack context (errcontext is emitted from
  `error_context_stack` callbacks and may be called multiple times, concatenating). [from-docs]
- **`errdetail_log()`** — detail that goes ONLY to the server log, never the
  client. **`errhidestmt()` / `errhidecontext()`** suppress the `STATEMENT:` /
  `CONTEXT:` log tails. [from-docs]
- **Object-association helpers** — `errtable()`, `errtablecol()`,
  `errtableconstraint()`, `errdatatype()`, `errdomainconstraint()`: at most **one**
  per ereport call. **`errposition(cursorpos)`** points at a spot in the query
  string. [from-docs]

## Translation: _internal vs translated, and %m

- **`errmsg()` / `errdetail()` / `errhint()` run through `gettext`** for
  translation; the **`*_internal()`** variants (`errmsg_internal`,
  `errdetail_internal`) **skip the translation dictionary** — use them for
  "can't happen" messages so translators aren't burdened. `*_plural()` variants
  handle singular/plural by count. [from-docs]
- **`%m`** in a format string expands to `strerror(errno)` captured **at the
  ereport call site**, not when format codes are walked — so never write
  `strerror(errno)` yourself in the arg list. [from-docs]

## elog() — the terse internal form

- **`elog(level, "fmt", ...)`** is exactly `ereport(level, errmsg_internal("fmt",
  ...))`: SQLSTATE always defaults, message never translated. Reserved for
  **internal "cannot happen" checks and low-level debug logging**; user-facing
  messages must use `ereport`. Still pervasive in the tree for its brevity. [from-docs]
  [verified-by-code, via [[knowledge/files/src/backend/utils/error/elog.c.md]]]

## Links into corpus
- Skill: **`error-handling`** — the procedural companion (elevel ladder, SQLSTATE choice, PG_TRY/PG_CATCH, soft errors via errsave/ereturn + escontext).
- [[knowledge/files/src/backend/utils/error/elog.c.md]] — the implementation of ereport/elog, error_context_stack, the ErrorData accumulation.
- [[knowledge/docs-distilled/error-style-guide.md]] — capitalization / phrasing / quoting rules for errmsg vs errdetail/errhint.
- [[knowledge/docs-distilled/protocol-error-fields.md]] — how these auxiliaries map to the wire-protocol error/notice fields.

## Gaps / follow-ups
- The elevel constants themselves (DEBUG1-5 / LOG / INFO / NOTICE / WARNING /
  ERROR / FATAL / PANIC) live in `src/include/utils/elog.h`; the page references
  the header rather than tabulating them — see the `error-handling` skill for the
  full ladder + which levels abort.
