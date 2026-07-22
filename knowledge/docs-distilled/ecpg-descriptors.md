---
source_url: https://www.postgresql.org/docs/current/ecpg-descriptors.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — Using Descriptor Areas (§36 leaf): named SQL descriptors (GET/SET DESCRIPTOR) vs the SQLDA struct family (sqlda_t / sqlvar_t / sqlname)"
maps_to_skill: wire-protocol
---

# ECPG — Using Descriptor Areas (dynamic result metadata)

Two *separate* mechanisms for handling result sets whose shape isn't known at
compile time (dynamic SQL): the SQL-standard **named descriptor areas**
(`ALLOCATE DESCRIPTOR` + `GET/SET DESCRIPTOR`) and the Informix-style **SQLDA**
C struct. Both are populated by `DESCRIBE`/`FETCH … INTO`; they are the ECPG
answer to "how many columns did this prepared statement return, and of what
type".

## Non-obvious claims

- **Named descriptors and SQLDA are different APIs with different syntax — the
  `SQL` keyword is the tell.** Named descriptors say `INTO SQL DESCRIPTOR
  mydesc`; SQLDA says `INTO DESCRIPTOR mysqlda` (the word `SQL` is *omitted*).
  Named descriptors are opaque handles you interrogate field-by-field; SQLDA is
  a C struct you read directly. [from-docs]

- **Named-descriptor header has exactly one useful field: `COUNT`.** `GET
  DESCRIPTOR name :hostvar = COUNT` yields the number of item (column)
  descriptors. Everything else is per-item, addressed by
  `VALUE num`. [from-docs]

- **Per-item fields include several that are parsed-but-unimplemented.**
  `TYPE`, `LENGTH`, `OCTET_LENGTH`, `RETURNED_LENGTH`, `RETURNED_OCTET_LENGTH`,
  `PRECISION`, `SCALE`, `NAME`, `INDICATOR`, `DATA`, and
  `DATETIME_INTERVAL_CODE` (1=DATE, 2=TIME, 3=TIMESTAMP, 4=TIME WITH TZ,
  5=TIMESTAMP WITH TZ, meaningful when `TYPE=9`) are live; but
  `CARDINALITY`, `DATETIME_INTERVAL_PRECISION`, `KEY_MEMBER`, and `NULLABLE`
  are documented as **not implemented** — reading them returns a fixed/placeholder
  value. Don't build logic on `NULLABLE`. [from-docs]

- **`INDICATOR` doubles as a truncation flag, not just a NULL flag.** Same
  convention as plain host-variable indicators: negative = NULL, positive =
  value was truncated into the target. [from-docs]

- **The SQLDA `sqlda_t` is a variable-length struct with a trailing 1-element
  array.** `struct sqlda_struct { char sqldaid[8]; long sqldabc; short sqln;
  short sqld; struct sqlda_struct *desc_next; struct sqlvar_struct sqlvar[1]; }`
  (`source/src/interfaces/ecpg/include/sqlda-native.h:33-41`). `sqldaid` is the
  literal `"SQLDA "` tag, `sqldabc` the allocated byte size, `sqld` the column
  count, and `sqlvar[]` is over-allocated to hold `sqld` columns (classic C
  flexible-array-before-C99 idiom). [verified-by-code]

- **Multi-row FETCH is a *linked list* of SQLDAs via `desc_next`.** A
  `FETCH 3 … INTO DESCRIPTOR mysqlda` chains one `sqlda_struct` per row through
  `desc_next` (`sqlda-native.h:39`) — you walk the list, not an array of rows.
  For *input* parameters `sqln` carries the parameter count; for output it
  mirrors `sqld`. [verified-by-code][from-docs]

- **Each column is a `sqlvar_t` carrying an `ECPGt_*` type code.** `struct
  sqlvar_struct { short sqltype; short sqllen; char *sqldata; short *sqlind;
  struct sqlname sqlname; }` (`sqlda-native.h:24-31`). `sqltype` is a value from
  `enum ECPGttype` (`ecpgtype.h`), `sqlind` points at a null indicator (0=not
  null, -1=null), and `sqlname` is `struct sqlname { short length; char
  data[NAMEDATALEN]; }` with `NAMEDATALEN 64` (`sqlda-native.h:16-22`). Note the
  ECPG-side `NAMEDATALEN` is hardcoded to 64 and must be ≥ the server's
  `NAMEDATALEN`, per the header comment. [verified-by-code]

## Links into corpus

- The `ECPGt_*` codes `sqltype` uses: `knowledge/docs-distilled/ecpg-develop.md`,
  `source/src/interfaces/ecpg/include/ecpgtype.h`.
- The dynamic-SQL statements (`PREPARE`/`DESCRIBE`/`EXECUTE`) that feed
  descriptors: `knowledge/docs-distilled/ecpg-variables.md` (host-variable side).
- Server-side describe path: `knowledge/docs-distilled/libpq-exec.md`
  (`PQdescribePrepared`, `PQnfields`/`PQftype`).
- Skill: `wire-protocol`.
