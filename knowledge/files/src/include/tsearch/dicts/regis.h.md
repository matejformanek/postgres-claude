# `src/include/tsearch/dicts/regis.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~50
- **Source:** `source/src/include/tsearch/dicts/regis.h`

"Fast regex subset" used by the ISpell dictionary engine for affix
matching when the affix-file pattern is simple enough that running a
full POSIX regex per word would be wasteful. [from-comment]

## API / declarations

- `RegisNode { type:2, len:16, unused:14; next; data[FLEX] }` — node
  in a linked list. `type` ∈ `{ RSF_ONEOF=1, RSF_NONEOF=2 }`.
  [verified-by-code]
- `Regis { node, issuffix:1, nchar:16, unused:15 }` — compiled
  regis. `RNHDRSZ` = `offsetof(RegisNode, data)`.
- `RS_isRegis(str)` — predicate: is `str` simple enough for regis?
- `RS_compile(r, issuffix, str)` — compile into preallocated `r`.
- `RS_free(r)` — release node chain (struct itself is caller-owned).
- `RS_execute(r, str)` — returns true if matches.

## Notable invariants / details

- Used in tandem with full regex via the `AFFIX.reg` union in
  `dicts/spell.h`: each AFFIX entry chooses regex_t or Regis
  according to its `isregis` flag. [verified-by-code]
  (`source/src/include/tsearch/dicts/spell.h:97-107`)
- `unused:14` + `unused:15` bitfields are reserved — tweaking
  RegisNode without touching the bitfield sums would shift layout.
  [inferred]

## Potential issues

- API is sparse — no length-bounded `RS_execute` variant, so the
  caller must guarantee `str` is null-terminated. [ISSUE-doc-drift:
  RS_execute null-termination contract not in header (nit)]
- `RegisNode.data` is a flexible array of `unsigned char` — meaning
  is type-dependent and not documented here. [ISSUE-undocumented-invariant:
  RegisNode.data layout per type code (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-tsearch`](../../../../../issues/include-tsearch.md)
<!-- issues:auto:end -->
