---
path: src/interfaces/ecpg/include/ecpglib.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 79
depth: read
---

# `ecpglib.h` — client-visible ecpglib API surface

## Purpose
The public header an ECPG-generated `.c` file includes. Declares every `ECPG*`
entry point the preprocessor emits calls to: connection management, the central
`ECPGdo` statement executor, transaction control, prepare/deallocate, the
dynamic-SQL descriptor API (`ECPGget_desc` / `ECPGset_desc` …), and the
`SQLCODE` / `SQLSTATE` convenience macros that alias into the per-thread `sqlca`.
[verified-by-code] Pulls in `ecpg_config.h`, `ecpgtype.h`, `libpq-fe.h`,
`sqlca.h` (ecpglib.h:13-16). [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `ECPGconnect` | ecpglib.h:28 | open named connection [verified-by-code] |
| `ECPGdo` | ecpglib.h:30 | variadic statement executor — the workhorse [verified-by-code] |
| `ECPGtrans` / `ECPGdisconnect` | ecpglib.h:33-34 | txn + teardown [verified-by-code] |
| `ECPGprepare` / `ECPGdeallocate` / `ECPGdeallocate_all` | ecpglib.h:35-38 | prepared-stmt lifecycle [verified-by-code] |
| `ECPGget_PGconn` | ecpglib.h:40 | escape hatch to the raw libpq `PGconn` [verified-by-code] |
| `ECPGget_desc_header` / `ECPGget_desc` / `ECPGset_desc*` | ecpglib.h:57-60 | dynamic-SQL descriptor API [verified-by-code] |
| `ECPGset_var` / `ECPGget_var` | ecpglib.h:67-68 | host-var registry by number [verified-by-code] |
| `SQLCODE` / `SQLSTATE` macros | ecpglib.h:48-49 | `sqlca.sqlcode` / `sqlca.sqlstate` [verified-by-code] |

## Internal landmarks
- The `#ifndef _ECPGLIB_H` guard is also tested by [[datetime.h]]/[[decimal.h]]
  to decide whether to typedef `dtime_t`/`dec_t` (they must not redefine what
  ecpglib already declares). So including `ecpglib.h` changes the behavior of
  those Informix headers. [verified-by-code]
- Almost every entry point takes `int lineno` first — the preprocessor passes
  the source line so runtime errors point back into the `.pgc`. [verified-by-code]

## Invariants & gotchas
- `SQLCODE`/`SQLSTATE` resolve through the `sqlca` macro, which (unless
  `POSTGRES_ECPG_INTERNAL` is defined) is `(*ECPGget_sqlca())` — a *function
  call returning a per-thread struct* (see [[sqlca.h]]). Reading `SQLCODE`
  repeatedly re-calls `ECPGget_sqlca()`. [verified-by-code]
- This is an installed ABI header: signatures here are contractual with shipped
  application binaries. [inferred]

## Cross-refs
- [[sqlca.h]] — the `sqlca` macro / `ECPGget_sqlca`.
- [[ecpgtype.h]] — `enum ECPGttype` used by `ECPGset_noind_null`.
- `knowledge/files/src/interfaces/ecpg/ecpglib/connect.c.md`,
  `execute.c.md`, `prepare.c.md` — implementations of these protos.
