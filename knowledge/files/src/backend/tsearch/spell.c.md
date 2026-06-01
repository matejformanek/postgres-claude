# `src/backend/tsearch/spell.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~2630
- **Source:** `source/src/backend/tsearch/spell.c`

Ispell/Hunspell-compatible morphological dictionary engine. Loads two
files: `.dict` (word list with flags) and `.affix` (suffix/prefix rules
referenced by flag). Build a compressed trie of all dict words; each
word carries a set of flags. At lexize time, for each candidate the
engine walks the trie + checks affixes (using `regis.c` for affix
conditions) until a base form is found, returning all morphological
variants.

Big internal data: `IspellDict` with `Dictionary` trie node array,
`AffixData`, `Prefix`/`Suffix` rule arrays, `CompoundAffix` for
Hunspell compound words. Memory is bounded — initialization happens
once per session per dictionary (cached in tsearch cache) and held in
a dedicated AllocSet.

Exported helpers: `NIImportDictionary`, `NIImportAffixes`, `NISortDictionary`,
`NIFindWord`, `NormalizeSubWord`. [from-comment] (`spell.c:9-13`)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
