# `src/include/tsearch/` (combined)

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/include/tsearch/`

- `ts_type.h` — `TSVector`, `TSQuery` on-disk + in-memory layouts.
  Lexeme structure (`WordEntry`, position arrays), tsquery node types
  (`QI_VAL`, `QI_OPR`).
- `ts_public.h` — public C API for writing tsearch templates:
  `TSLexeme`, `DictSubState`, the `lexize` calling convention.
- `ts_cache.h` — per-config, per-dict, per-parser cache entries
  (`TSConfigCacheEntry`, `TSDictionaryCacheEntry`,
  `TSParserCacheEntry`) plus `lookup_ts_*` getters. Syscache callbacks
  invalidate on DDL.
- `ts_utils.h` — `parsetext`, `make_tsvector`, `compareEntries`,
  `tsquery_requires_match` and other shared helpers.
- `ts_locale.h` — `t_isalpha`/`t_isdigit`/`t_iseq`/`lowerstr` plus
  `tsearch_readline` for file parsing.
- `dicts/spell.h` — Ispell engine types (`IspellDict`, `Affix`,
  `SPNode`, `CMPDAffix`).
- `dicts/regis.h` — `Regis` struct and `RS_compile`/`RS_execute`.
