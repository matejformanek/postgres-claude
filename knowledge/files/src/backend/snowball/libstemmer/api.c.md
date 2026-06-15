---
path: src/backend/snowball/libstemmer/api.c
anchor_sha: e18b0cb7344
loc: 30
---

# src/backend/snowball/libstemmer/api.c

Hand-shipped Snowball runtime (not auto-generated): implements the `SN_env`
lifecycle used by every generated stemmer in this directory. Exports
`SN_create_env`, `SN_close_env`, and `SN_set_current`, called from each
`stem_<encoding>_<language>_create_env` / `_close_env`.

See [README.md](README.md) for why per-file analysis is deferred (upstream
Snowball import, no PG-side invariants beyond what `dict_snowball.c` enforces).
