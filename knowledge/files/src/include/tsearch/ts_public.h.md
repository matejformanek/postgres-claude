# `src/include/tsearch/ts_public.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~160
- **Source:** `source/src/include/tsearch/ts_public.h`

Public C API for tsearch parsers and dictionaries. A text-search
template (e.g. simple, ispell, snowball) implements callbacks that
return `TSLexeme` arrays via the `lexize` calling convention defined
here; a parser template returns `LexDescr` token-class descriptors and
fills `HeadlineParsedText` during headline generation. [verified-by-code]

## API / declarations

- `LexDescr { lexid, alias, descr }` — returned by parser's
  `prslextype` method to advertise token categories. [verified-by-code]
- `HeadlineWordEntry` — per-token bitfield with `in`/`selected`/
  `replace`/`skip`/`repeated` flags plus `type:8`/`len:16` plus a
  `WordEntryPos pos` and a back-pointer `QueryOperand *item` to the
  matching tsquery operand. [verified-by-code]
- `HeadlineParsedText` — bundles `words[]`, `lenwords`, `curwords` +
  output strings `startsel`/`stopsel`/`fragdelim` (palloc'd by the
  prsheadline function). [verified-by-code]
- `StopList { len, stop }` + `readstoplist(fname, *, wordop)` /
  `searchstoplist(StopList*, key)` — generic stopword machinery shared
  by snowball, ispell, and similar dicts. [verified-by-code]
- `TSLexeme { nvariant, flags, lexeme }` — return struct for any
  `lexize` function. `nvariant` groups lexemes belonging to the same
  split variant (e.g. Norwegian "fotballklubber" → two variants).
  Flags: `TSL_ADDPOS` (0x01), `TSL_PREFIX` (0x02), `TSL_FILTER` (0x04).
  [verified-by-code]
- `DictSubState { isend, getnext, private_state }` — opaque state
  passed as 4th arg to `dictlexize` for multi-call dicts (thesaurus).
  [verified-by-code]
- `get_tsearch_config_filename(basename, extension)` — resolves
  `$SHAREDIR/tsearch_data/<basename>.<extension>`. [verified-by-code]

## Notable invariants / details

- `repeated=1` HeadlineWordEntries are duplicates that exist only to
  carry an `item` back-pointer when one token matches multiple tsquery
  operands. Consumers must ignore everything except `item` on those.
  [from-comment]
- A dict's `lexize` may set "TSL_FILTER" to force the engine to
  reapply the configuration's dictionary chain to its output (used by
  `unaccent` and similar). [inferred]

## Potential issues

- `TSLexeme.flags` is only 16 bits and three of the low bits are
  taken; the remaining 13 bits are undocumented as
  reserved-vs-available. [ISSUE-undocumented-invariant: TSLexeme.flags
  reserved bits not stated (nit)]
- `HeadlineWordEntry.type:8` carries the parser's token category but
  the comment says nothing about the legal range or where it's
  defined (it's the parser-specific `lexid` from `LexDescr`).
  [ISSUE-doc-drift: type:8 semantics under-documented (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-tsearch`](../../../../issues/include-tsearch.md)
<!-- issues:auto:end -->
