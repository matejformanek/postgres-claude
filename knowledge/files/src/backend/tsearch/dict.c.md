# `src/backend/tsearch/dict.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~70
- **Source:** `source/src/backend/tsearch/dict.c`

The thin standard interface a user-defined dictionary template uses
when extending tsearch. Provides `lexize()` SQL wrapper, validation
helpers, and the typed `TSDictionaryCacheEntry` lookups. Each
dictionary is a row in `pg_ts_dict` referencing a `pg_ts_template`
which names the C-level init+lexize functions; this file bridges
SQL calls to those C entry points. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
