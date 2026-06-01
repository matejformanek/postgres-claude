# `src/backend/tsearch/regis.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~230
- **Source:** `source/src/backend/tsearch/regis.c`

A tiny fast regex subset used by Ispell/Hunspell affix processing.
Recognizes only character classes (`[abc]`, `[^abc]`), wildcards, and
anchors — none of the heavyweight features of `backend/regex`. Reason
to exist: affix rules apply per-word during ts_lexize, where the full
regex compile cost would dominate. Functions: `RS_compile`,
`RS_execute`, `RS_free`. [from-comment]
