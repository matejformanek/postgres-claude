# `src/backend/tsearch/dict_thesaurus.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~860
- **Source:** `source/src/backend/tsearch/dict_thesaurus.c`

Thesaurus dictionary: phrase-to-phrase substitution. Each thesaurus
file line is `phrase1 : phrase2`. Both sides go through a sub-dictionary
(typically `english_stem`) at load time so lookups are stem-matched
rather than literal. Builds a trie over the sub-dict'd phrase tokens;
lexize walks the trie to find the longest match starting at the
current position. Critical for phrase tokenization in scientific
texts (e.g., "supernova explosion" → "stellar collapse"). [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
