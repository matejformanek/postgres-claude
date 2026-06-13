---
path: src/interfaces/ecpg/ecpglib/ecpglib_extern.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 270
depth: read
---

# `ecpglib_extern.h` — ecpglib internal shared header (structs, prototypes, SQLSTATEs)

## Purpose
The internal (NOT installed) shared header for ecpglib. It declares the core
runtime data structures — `struct connection`, `struct statement`, `struct
variable`, `struct prepared_statement`, descriptors — the `ecpg_*` internal
prototypes implemented across the ecpglib `.c` files, the `enum COMPAT_MODE` /
`enum ARRAY_TYPE` compatibility enums with their helper macros, and the private
`ECPG_SQLSTATE_*` code constants. It is guarded by `_ECPG_ECPGLIB_EXTERN_H` and
pulls in `ecpgtype.h`, `libpq-fe.h`, `sqlca.h`, and both SQLDA layouts. This is
purely declarations — no per-thread `sqlca` storage lives here (the active
`sqlca` is the user-facing one from `sqlca.h`; this header only declares
`ecpg_init_sqlca`). [verified-by-code]

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `enum COMPAT_MODE` | ecpglib_extern.h:17 | PGSQL / INFORMIX / INFORMIX_SE / ORACLE; with `INFORMIX_MODE`/`ORACLE_MODE` macros (h:24-25) |
| `enum ARRAY_TYPE` | ecpglib_extern.h:27 | ERROR/NOT_SET/ARRAY/VECTOR/NONE; `ECPG_IS_ARRAY` macro (h:32) |
| `struct ECPGgeneric_varchar` / `ECPGgeneric_bytea` | ecpglib_extern.h:35, 42 | `{int len; char arr[FLEXIBLE_ARRAY_MEMBER];}` |
| `struct ECPGtype_information_cache` | ecpglib_extern.h:52 | per-connection Oid → isarray cache node |
| `struct statement` | ecpglib_extern.h:64 | one SQL statement: command, connection, compat, in/outlist `struct variable*`, libpq param arrays, `PGresult *results` |
| `struct prepared_statement` | ecpglib_extern.h:92 | name + `struct statement *stmt`, linked list per connection |
| `struct connection` | ecpglib_extern.h:101 | name, `PGconn *connection`, autocommit, `cache_head`, `prep_stmts`, `next` |
| `struct descriptor` / `descriptor_item` | ecpglib_extern.h:112, 121 | named descriptor + per-column items list |
| `struct variable` | ecpglib_extern.h:135 | host variable: type/value/pointer + size/arr/offset, plus parallel indicator (`ind_*`) fields |
| `struct var_list` + `extern struct var_list *ivlist` | ecpglib_extern.h:152, 159 | input-variable list |
| `extern bool ecpg_internal_regression_mode` | ecpglib_extern.h:22 | regression-test toggle |
| `extern locale_t ecpg_clocale` | ecpglib_extern.h:60 | `LC_NUMERIC=C` locale, only `#ifdef HAVE_USELOCALE` |
| memory/type prototypes | ecpglib_extern.h:163-182 | `ecpg_alloc`, `ecpg_auto_alloc`, `ecpg_realloc`, `ecpg_free`, `ecpg_strdup`, `ecpg_add_mem`, `ecpg_clear_auto_mem`, `ecpg_type_name`, `ecpg_dynamic_type`, `sqlda_dynamic_type` |
| execute pipeline prototypes | ecpglib_extern.h:196-209 | `ecpg_do_prologue`/`build_params`/`autostart_transaction`/`execute`/`process_output`/`do_epilogue`/`do` |
| error/log prototypes | ecpglib_extern.h:211-221 | `ecpg_check_PQresult`, `ecpg_raise`, `ecpg_raise_backend`, `ecpg_log`, `ecpg_init_sqlca` |
| SQLDA prototypes | ecpglib_extern.h:223-234 | `ecpg_build_compat_sqlda`/`build_native_sqlda` + setters, hex enc/dec helpers |
| `ECPG_SQLSTATE_*` constants | ecpglib_extern.h:247-268 | private SQLSTATE strings incl. `ECPG_SQLSTATE_ECPG_OUT_OF_MEMORY "YE001"`, `..._INTERNAL_ERROR "YE000"` |

## Invariants & gotchas
- Internal header: NOT part of the installed ecpg API. Application code includes
  `ecpglib.h` / `sqlca.h`, never this file. [inferred]
- Requires `#define POSTGRES_ECPG_INTERNAL` in including `.c` files (all ecpglib
  `.c` files do so before `#include "postgres_fe.h"`). [verified-by-code]
- `ecpg_log` is `pg_attribute_printf(1, 2)` and `ecpg_gettext` is NLS-conditional
  (a passthrough macro when `ENABLE_NLS` is off, ecpglib_extern.h:236-240). [verified-by-code]
- `struct variable` carries a full parallel set of indicator fields (`ind_type`,
  `ind_value`, `ind_varcharsize`, …) — host var and its NULL indicator are
  described in one node (ecpglib_extern.h:143-148). [verified-by-code]
- The two flexible-array structs (`ECPGgeneric_varchar`/`_bytea`) must be the
  last member of any enclosing allocation; the `len`-prefixed layout mirrors the
  generated host structs. [inferred]

## Cross-refs
- [[memory.c]] — implements the alloc/auto-mem prototypes (h:163-182).
- [[typename.c]] — implements `ecpg_type_name`/`ecpg_dynamic_type`/`sqlda_dynamic_type`.
- [[execute.c]] — implements the `ecpg_do_*` pipeline (h:196-209) and consumes
  `struct statement` / `struct variable`.
- [[connect.c]] — manages `struct connection` and `ecpg_get_connection`.
- [[prepare.c]] — `struct prepared_statement`, `ecpg_find_prepared_statement`.
- [[descriptor.c]] / [[sqlda.c]] — `struct descriptor`, SQLDA builders.
- [[error.c]] / [[misc.c]] — `ecpg_raise`, `ecpg_log`, `ecpg_init_sqlca`.
