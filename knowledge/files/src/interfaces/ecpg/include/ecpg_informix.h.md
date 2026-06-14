---
path: src/interfaces/ecpg/include/ecpg_informix.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 90
depth: read
---

# `ecpg_informix.h` — Informix ESQL/C compatibility surface

## Purpose
The umbrella header for Informix compatibility mode (the `compatlib`
`informix.c` implementation). Pulls in ecpglib + all four pgtypes headers, then
declares the full Informix API: `r*` date/format helpers (`rdatestr`,
`rfmtdate`, `rdefmtdate`, `rfmtlong`, …), null helpers (`risnull`/`rsetnull`),
type-introspection (`rtypalign`/`rtypmsize`/`rtypwidth`), the `dec*` decimal
arithmetic family, and the `dt*` datetime family. Also defines the
`ECPG_INFORMIX_*` (`-12xx`) error codes. [verified-by-code]

## Public symbols
| Symbol group | Site | Notes |
|---|---|---|
| `ECPG_INFORMIX_*` error codes | ecpg_informix.h:16-29 | `-1200…-1264`, Informix-numbered [verified-by-code] |
| `rdatestr/rtoday/rjulmdy/rdefmtdate/rfmtdate/rmdyjul/rstrdate/rdayofweek` | ecpg_informix.h:36-43 | Informix date helpers [verified-by-code] |
| `rfmtlong/rgetmsg/risnull/rsetnull/rtypalign/rtypmsize/rtypwidth/rupshift` | ecpg_informix.h:45-52 | format/null/type helpers [verified-by-code] |
| `byleng/ldchar` | ecpg_informix.h:54-55 | fixed-char helpers [verified-by-code] |
| `ECPG_informix_set_var/_get_var/_reset_sqlca` | ecpg_informix.h:57-59 | Informix var registry [verified-by-code] |
| `dec*` family (`decadd/deccmp/deccvasc/…/dectolong`) | ecpg_informix.h:62-75 | decimal arithmetic [verified-by-code] |
| `dt*` family (`dtcurrent/dtcvasc/dtsub/dttoasc/dttofmtasc/intoasc/dtcvfmtasc`) | ecpg_informix.h:78-84 | datetime helpers [verified-by-code] |
| `SQLNOTFOUND` | ecpg_informix.h:14 | `100` (Informix spelling) [verified-by-code] |

## Internal landmarks
- Defining `_ECPG_INFORMIX_H` is what flips [[sqlda.h]] to the `sqlda-compat`
  layout (it tests `#ifdef _ECPG_INFORMIX_H`). So including this header changes
  the SQLDA struct shape seen by the translation unit. [verified-by-code]
- Comments split the decl block by "Informix defines these in decimal.h /
  datetime.h" (ecpg_informix.h:61,77) — documenting where Informix itself
  declares them, for porting fidelity. [from-comment]

## Invariants & gotchas
- The `dttoasc`/`intoasc`/`rfmtlong`/`rfmtdate` formatters write into
  caller-supplied buffers with **no length** — the subsystem-wide unbounded
  output-buffer surface (see `knowledge/issues/ecpg.md`). [verified-by-code]
- `ECPG_INFORMIX_*` are a *third* error vocabulary alongside [[ecpgerrno.h]]'s
  `ECPG_*` and [[pgtypes_error.h]]'s `PGTYPES_*`, for the same failures. [verified-by-code]

## Cross-refs
- [[sqlda.h]] — `_ECPG_INFORMIX_H` selects the compat SQLDA.
- [[decimal.h]] / [[datetime.h]] — the `dec_t`/`dtime_t` aliases this enables.
- `knowledge/files/src/interfaces/ecpg/compatlib/informix.c.md` — implementation.
