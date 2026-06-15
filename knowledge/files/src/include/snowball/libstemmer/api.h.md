---
path: src/include/snowball/libstemmer/api.h
anchor_sha: e18b0cb7344
loc: 34
depth: stub
---

# src/include/snowball/libstemmer/api.h

Public Snowball typedefs vendored verbatim from upstream. Defines
`symbol` (`typedef unsigned char symbol;`) and `struct SN_env`
(per-stem state: working buffer `p`, cursors `c`/`l`/`lb`/`bra`/`ket`,
allocation flag `af`). Also declares `SN_new_env` / `SN_delete_env` /
`SN_set_current` — the env-lifecycle calls `dict_snowball.c` invokes
to load each input word.

No PG-specific content; ships unmodified from snowballstem.org.

See [snowball/README.md](../README.md) and
[snowball_runtime.h.md](../snowball_runtime.h.md) for the PG-side
wrapper that re-binds allocation onto palloc.
