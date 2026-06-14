---
path: src/interfaces/ecpg/preproc/preproc_extern.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 150
depth: read
---

# `preproc_extern.h` — shared extern declarations for the ECPG preproc module

## Purpose
The module-wide header that ties the ECPG preprocessor's translation units
together: it declares every cross-file global (option flags, parse/output state),
the `YYLTYPE` location typedef, the prototypes used across `ecpg.c`, `type.c`,
`variable.c`, `output.c`, `descriptor.c`, `parser.c`, etc., the preprocessor
return codes, and the compatibility-mode enum/macros. It pulls in `type.h` (for
the `struct ECPGtype`/`variable`/`arguments` types it references) and
`common/keywords.h` `preproc_extern.h:6-7` `[verified-by-code]`. It is a pure
declaration header (no inline logic beyond macros); definitions live in the
corresponding `.c` files.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `YYLTYPE` (typedef `const char *`) | `preproc_extern.h:20` | Location type; `YYLTYPE_IS_DECLARED` set so bison uses it `:22` |
| `STRUCT_DEPTH` | `preproc_extern.h:15` | Max nesting for `struct_member_list` `:64` |
| option flags (`autocommit`, `auto_create_c`, `system_includes`, `force_indicator`, `questionmarks`, `regression_mode`, `auto_prepare`) | `preproc_extern.h:26-32` | `bool` CLI-driven mode toggles |
| parse-state ints (`braces_open`, `ret_value`, `struct_level`, `ecpg_internal_var`) | `preproc_extern.h:33-36` | |
| scanner globals (`base_yytext`, `token_start`, `base_yylineno`, `base_yyin`, `base_yyout`, `base_yydebug`) | `preproc_extern.h:41-49` | Bridge to `pgc.l`; `base_yydebug` only under `YYDEBUG` `:44-46` |
| `base_yyparse`, `base_yylex`, `base_yyerror`, `filtered_base_yylex`, `parser_init` | `preproc_extern.h:79-81,127-128` | Grammar/scanner driver entry points |
| `make2_str`/`make3_str`/`cat2_str`/`cat_str` | `preproc_extern.h:87-90` | String concatenation helpers used throughout |
| `mm_alloc`/`mm_strdup`/`loc_alloc`/`loc_strdup`/`reclaim_local_storage` | `preproc_extern.h:82-86` | Memory allocation (persistent `mm_*` vs per-statement `loc_*`) |
| `mmerror`/`mmfatal` | `preproc_extern.h:91-92` | Error reporting; `mmfatal` is `pg_noreturn` |
| `output_*` family | `preproc_extern.h:73-77,93-96` | Code-generation emitters |
| variable/descriptor/typedef registry | `preproc_extern.h:97-124` | `find_variable`, `new_variable`, `add_descriptor`, `get_typedef`, etc. |
| `ScanCKeywordLookup`/`ScanECPGKeywordLookup` | `preproc_extern.h:125-126` | Keyword recognizers |
| `SQLScanKeywordTokens[]` | `preproc_extern.h:67` | Generated keyword→token table from `keywords.c` |
| `compat` + `COMPAT_MODE` enum | `preproc_extern.h:140-147` | With `INFORMIX_MODE`/`ORACLE_MODE` macros |

## Internal landmarks (the global-flag groups)
- **Mode/option flags** — boolean preprocessor switches set from ECPG CLI options
  `preproc_extern.h:26-32` `[verified-by-code]`.
- **Parse-tracking ints** — brace nesting and struct-level counters that track
  scanner/parser position `preproc_extern.h:33-36` `[inferred]`.
- **Naming/identity strings** — `current_function`, `descriptor_name`,
  `connection`, `input_filename`, `output_filename`
  `preproc_extern.h:37-40,50` `[verified-by-code]`.
- **Scanner bridge globals** — the `base_y*` set shared with `pgc.l`/bison
  `preproc_extern.h:41-49` `[verified-by-code]`.
- **Aggregate/registry globals** — `include_paths`, `cur`, `types`, `defines`,
  `g_declared_list`, the indicator sentinels (`ecpg_no_indicator`,
  `no_indicator`), arg lists (`argsinsert`, `argsresult`), the `when_*` whenever
  handlers, and `struct_member_list[STRUCT_DEPTH]`
  `preproc_extern.h:52-64` `[verified-by-code]`.
- **Return codes** — `ILLEGAL_OPTION`…`INDICATOR_NOT_SIMPLE` (1..7), including
  `PARSE_ERROR` (3) used by `parser.c`'s `mmerror` calls
  `preproc_extern.h:132-138` `[verified-by-code]`.
- **Compat layer** — `COMPAT_MODE` enum + `compat` global + `INFORMIX_MODE`/
  `ORACLE_MODE` predicate macros `preproc_extern.h:140-147` `[verified-by-code]`.

## Invariants & gotchas
- **`YYLTYPE` is `const char *`, not a struct.** ECPG uses a string-valued
  location (the source text snippet) rather than line/col, which is exactly what
  `parser.c`'s `base_yylex_location` produces via `loc_strdup`
  `preproc_extern.h:20-22` `[verified-by-code]`. `YYLTYPE_IS_DECLARED` tells
  bison not to define its own `:22`.
- **`mm_*` vs `loc_*` allocation split.** `mm_alloc`/`mm_strdup` are persistent;
  `loc_alloc`/`loc_strdup` are per-statement and freed by
  `reclaim_local_storage` `preproc_extern.h:82-86` `[inferred]`. Mixing the two
  lifetimes is a use-after-free hazard.
- **`base_yydebug` only exists under `YYDEBUG`** `preproc_extern.h:44-46`
  `[verified-by-code]` — code referencing it must guard accordingly.
- **`struct_member_list` is a fixed `STRUCT_DEPTH`-sized array** `:64` — struct
  nesting deeper than 128 is unbounded behavior unless checked elsewhere
  `[inferred]`.

## Cross-refs
- [[src/interfaces/ecpg/preproc/parser.c]] — consumes `filtered_base_yylex` `:128`,
  `base_yylex`/`base_yyparse` `:79-80`, `base_yytext` `:41`, `make3_str` `:90`,
  `loc_strdup` `:85`, `mmerror`/`PARSE_ERROR` `:91,134`.
- [[src/interfaces/ecpg/preproc/type.h]] — included `:7`; supplies
  `struct ECPGtype`, `struct variable`, `struct arguments`, the `ECPGdtype`/
  `ECPGttype`/`errortype` enums referenced in these prototypes.
- `ecpg.c` / `type.c` / `variable.c` / `output.c` / `descriptor.c` — the
  translation units that define the globals and functions declared here.
- `pgc.l` — flex scanner that owns the `base_y*` scanner globals.
  **Generated/flex source, not separately documented in this corpus.**
- [[idioms/parser-pipeline]] — scanner/filter/grammar driver pattern.

## Potential issues
No issues. This is a straightforward declaration header; no behavioral claims to
flag.
