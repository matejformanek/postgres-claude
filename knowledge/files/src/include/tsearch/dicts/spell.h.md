# `src/include/tsearch/dicts/spell.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~242
- **Source:** `source/src/include/tsearch/dicts/spell.h`

In-memory layout for the ISpell/Hunspell dictionary engine consumed
by the `ispell` text-search template. Builds a trie over base words
(`SPNode`) and a separate trie over affix prefixes/suffixes
(`AffixNode`), plus Hunspell-style compound-flag handling.
[verified-by-code]

## API / declarations

### Trie / data structures

- `SPNodeData { val:8, isword:1, compoundflag:4, affix:19; node }`
  — entry in the dictionary trie. `affix` is an index into
  `IspellDict.AffixData[]`. [verified-by-code]
- `SPNode { length; data[FLEX] }` — array of `SPNodeData` keyed by
  byte. `SPNHDRSZ = offsetof(SPNode, data)`. [verified-by-code]
- `SPELL { p.flag | p.d{affix,len}; word[FLEX] }` — staging entry
  during build. `p.flag` is the raw affix flag string from the dict
  file; after `NISortDictionary`, `p.d` is used (affix index +
  length). [from-comment]
- `AFFIX { flag; type:1, flagflags:7, issimple:1, isregis:1,
  replen:14; find; repl; reg{pregex*|regis} }` — one affix rule.
  `type` ∈ `{FF_PREFIX=0, FF_SUFFIX=1}` (order matters — sort relies
  on it). `pregex` is a pointer to a heap `regex_t` because regex_t
  is not assumed movable. [from-comment]
- `AffixNodeData { val:8, naff:24; aff (AFFIX**); node }`,
  `AffixNode { isvoid:1, length:31; data[FLEX] }`.
- `CMPDAffix { affix, len, issuffix }` — flat list of compound
  affixes for fast scan during compounding.

### Hunspell-compatible flags

- `FF_COMPOUNDONLY 0x01`, `FF_COMPOUNDBEGIN 0x02`,
  `FF_COMPOUNDMIDDLE 0x04`, `FF_COMPOUNDLAST 0x08` (combined as
  `FF_COMPOUNDFLAG`, masked by `FF_COMPOUNDFLAGMASK 0x0F`),
  `FF_COMPOUNDPERMITFLAG 0x10`, `FF_COMPOUNDFORBIDFLAG 0x20`,
  `FF_CROSSPRODUCT 0x40`. Names correlate with Hunspell affix-file
  options (https://hunspell.github.io). [from-comment]
- `FlagMode { FM_CHAR, FM_LONG, FM_NUM }` — flag encoding in the
  Hunspell affix file (1 char / 2 chars / decimal number < 65536).
  Cap: `FLAGNUM_MAXSIZE = 1<<16`. [from-comment]
- `CompoundAffixFlag { flag.s | flag.i; flagMode; value }` — both
  modes carried so bsearch can be done without an `_arg` variant.
  [from-comment]

### IspellDict (the in-memory dictionary)

- `naffixes`/`maffixes` + `AFFIX *Affix` array,
- `AffixNode *Prefix`, `*Suffix` (tries),
- `SPNode *Dictionary` (word trie),
- `AffixData[lenAffixData]` (deduplicated affix-set strings),
- `useFlagAliases`, `usecompound`, `flagMode`,
- `CMPDAffix *CompoundAffix` + Hunspell flag arrays,
- Build-time only: `MemoryContext buildCxt`, `SPELL **Spell`,
  `firstfree`/`avail` for a compact bump-allocator across the build.
  [verified-by-code]

### Build API

- `NIStartBuild(Conf)`, `NIImportAffixes(Conf, filename)`,
  `NIImportDictionary(Conf, filename)`, `NISortDictionary(Conf)`,
  `NISortAffixes(Conf)`, `NIFinishBuild(Conf)`.
- Lookup API: `NINormalizeWord(Conf, word)` returns `TSLexeme*`
  array.

## Notable invariants / details

- "Don't change the order of these. Initialization sorts by these,
  and expects prefixes to come first after sorting." — `FF_PREFIX=0`,
  `FF_SUFFIX=1`. [from-comment]
- The build allocates from `buildCxt`; `firstfree`/`avail` implement
  a manual bump allocator inside that context, so palloc overhead is
  amortized across many small allocations. [from-comment]
- AFFIX uses `regex_t *pregex` rather than embedded regex_t because
  the arrays are moved + sorted, and regex_t is not guaranteed
  movable. [from-comment]

## Potential issues

- `SPNodeData.affix:19` caps the number of distinct affix-set
  entries at 524288 — quietly silent overflow if a huge Hunspell
  dictionary exceeds that. [ISSUE-correctness: SPNodeData.affix
  19-bit cap is unbounded-on-overflow (likely)]
- `AFFIX.replen:14` caps replacement length at 16383 bytes; longer
  replacements would silently wrap. [ISSUE-correctness: AFFIX.replen
  14-bit cap (maybe)]
- The header still references the union member `regis` (inline
  `Regis` struct), but the comment above says regex_t was extracted
  to a pointer "to keep this struct small" — the union still pays
  the size of the larger member (Regis). [ISSUE-style: pregex/regis
  union nominal size unchanged (nit)]
- Build-only fields (`buildCxt`, `Spell`, `nspell`/`mspell`,
  `firstfree`, `avail`) live in the same struct that's queried at
  runtime — easy for a future patch to read them outside the
  build window. [ISSUE-undocumented-invariant: IspellDict mixes
  build-time and runtime members; only the build code clears them
  (maybe)]
