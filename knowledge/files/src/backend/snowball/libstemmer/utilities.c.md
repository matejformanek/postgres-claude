---
path: src/backend/snowball/libstemmer/utilities.c
anchor_sha: e18b0cb7344
loc: 509
---

# src/backend/snowball/libstemmer/utilities.c

Hand-shipped Snowball runtime (not auto-generated): the shared helpers every
generated stemmer calls into — `find_among`, `find_among_b`, `slice_from_s`,
`slice_del`, `slice_check`, `eq_s` / `eq_s_b`, and the small string-buffer
growth machinery behind `SN_set_current`. Imported verbatim from upstream
Snowball.

See [README.md](README.md) for why per-file analysis is deferred (upstream
Snowball import, no PG-side invariants beyond what `dict_snowball.c` enforces).
