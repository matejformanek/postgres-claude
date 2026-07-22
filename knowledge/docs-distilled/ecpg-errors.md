---
source_url: https://www.postgresql.org/docs/current/ecpg-errors.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Error Handling (§36 leaf): the WHENEVER directive, the sqlca struct (SQLERRMC_LEN 150), SQLSTATE-over-SQLCODE, ECPG error-code table"
maps_to_skill: error-handling
---

# ECPG — Error Handling (WHENEVER, sqlca, SQLSTATE)

Two layers: the `WHENEVER` preprocessor directive that installs a
compile-time-woven callback on error/warning/not-found conditions, and the
`sqlca` (SQL Communications Area) struct the runtime populates on every
statement. SQLSTATE is the modern portable signal; SQLCODE is the deprecated
integer legacy.

## Non-obvious claims

- **`WHENEVER` is a *lexically-scoped preprocessor* directive, not a runtime
  handler.** `EXEC SQL WHENEVER condition action;` makes the preprocessor emit
  the chosen action's C after *every subsequent* embedded statement in the file
  until overridden — it is not a registered callback. Conditions:
  `SQLERROR`, `SQLWARNING`, `NOT FOUND`. Actions: `CONTINUE` (default/ignore),
  `GOTO label`, `SQLPRINT` (stderr), `STOP` (`exit(1)`), `DO BREAK`/`DO
  CONTINUE` (emit C `break`/`continue`), and `CALL name(args)` / `DO
  name(args)`. Because it's textual, a `WHENEVER … GOTO` can reference a label
  that isn't in scope at some later statement — a classic ECPG bug. [from-docs]

- **The `sqlca` layout is fixed and standardized.** `struct sqlca_t { char
  sqlcaid[8]; long sqlabc; long sqlcode; struct { int sqlerrml; char
  sqlerrmc[SQLERRMC_LEN]; } sqlerrm; char sqlerrp[8]; long sqlerrd[6]; char
  sqlwarn[8]; char sqlstate[5]; }` (`source/src/interfaces/ecpg/include/sqlca.h:19-54`).
  `sqlcaid`/`sqlabc`/`sqlerrp` are historical filler. [verified-by-code]

- **`SQLERRMC_LEN` is 150 — messages are truncated to fit.** The error text
  buffer `sqlerrmc` is `char[SQLERRMC_LEN]` with `#define SQLERRMC_LEN 150`
  (`sqlca.h:12,27`), and `sqlerrml` is the (possibly-truncated) length actually
  stored. A long backend error message is clipped at 150 bytes in `sqlca`; the
  full text is only in the server log. [verified-by-code]

- **`sqlerrd[2]` is the processed-row count (0-indexed slot 2).** After a
  DML/`SELECT`, `sqlca.sqlerrd[2]` holds rows affected/returned — the ECPG
  analogue of libpq's `PQcmdTuples`. `sqlerrd` is `long[6]`
  (`sqlca.h:30`); most other slots are unused. [verified-by-code][from-docs]

- **`sqlwarn` is an 8-char flag array; `sqlwarn[0]='W'` means "some warning
  set", `sqlwarn[2]='W'` means truncation.** `char sqlwarn[8]` (`sqlca.h:39`).
  `sqlwarn[0]` is the summary flag; `sqlwarn[2]` specifically flags a value
  truncated into a host variable — the same event the positive indicator value
  reports. [verified-by-code][from-docs]

- **SQLSTATE is preferred; SQLCODE is deprecated and non-portable.**
  `sqlstate[5]` is the 5-char SQL-standard class+subclass (`"00000"` = success,
  `"02000"` = no-data); `sqlcode` is the legacy integer (0=ok, positive=info
  like 100=NOT FOUND, negative=error). The docs recommend new code read
  `sqlstate`/`sqlca.sqlcode==ECPG_NOT_FOUND` rather than hardcoding SQLCODE
  integers. [from-docs]

- **The ECPG error codes are a fixed banded enum.** `ECPG_NO_ERROR 0`,
  `ECPG_NOT_FOUND 100`; library errors start at −200
  (`ECPG_UNSUPPORTED −200`, `ECPG_TOO_MANY_ARGUMENTS −201`,
  `ECPG_TOO_FEW_ARGUMENTS −202`, `ECPG_TOO_MANY_MATCHES −203`,
  `ECPG_MISSING_INDICATOR −213`, `ECPG_NO_CONN −220`, `ECPG_NOT_CONN −221`);
  dynamic-SQL/descriptor errors at −240; backend-relayed errors at −400
  (`ECPG_PGSQL −400`, `ECPG_CONNECT −402`, `ECPG_DUPLICATE_KEY −403`); backend
  warnings at −600 (`source/src/interfaces/ecpg/include/ecpgerrno.h:9-80`).
  [verified-by-code]

- **`ECPG_OUT_OF_MEMORY` is `-ENOMEM`, not a literal.** `#define
  ECPG_OUT_OF_MEMORY -ENOMEM` (`ecpgerrno.h:16`) — so the docs' "−12 / YE001"
  is the Linux `ENOMEM` value; the code deliberately reuses the system errno
  (negated) rather than inventing a fixed number, and the comment says system
  error codes "get the correct number, but are made negative". [verified-by-code]

## Links into corpus

- Backend SQLSTATE definitions ECPG relays: `source/src/backend/utils/errcodes.txt`,
  skill `error-handling` (ereport/errcode picking).
- The indicator-truncation event `sqlwarn[2]` mirrors:
  `knowledge/docs-distilled/ecpg-variables.md`.
- libpq's `PQcmdTuples` / `PQresultErrorField(PG_DIAG_SQLSTATE)` equivalents:
  `knowledge/docs-distilled/libpq-exec.md`, `knowledge/docs-distilled/protocol-error-fields.md`.
- Skill: `error-handling`, `wire-protocol`.
