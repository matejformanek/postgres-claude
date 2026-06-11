# Issues — `src/include/tsearch/`

Per-subdirectory issue register for tsearch headers (parsers,
dictionaries, on-disk types, Ispell engine, regis subset). See
`knowledge/issues/README.md` for tag/severity conventions.

**Parent docs:** `knowledge/files/src/include/tsearch/*.md`,
including `dicts/spell.h.md` and `dicts/regis.h.md`.

## Open / Triaged

| Date | File:line | Type | Severity | Summary | Status | Linked doc |
|---|---|---|---|---|---|---|
| 2026-06-11 | src/include/tsearch/ts_public.h:142-144 | undocumented-invariant | nit | `TSLexeme.flags` reserved-bit policy not stated; only 3 of 16 bits assigned, rest unlabeled | open | files/.../ts_public.h.md |
| 2026-06-11 | src/include/tsearch/ts_public.h:66 | doc-drift | nit | `HeadlineWordEntry.type:8` semantics tied to parser's `lexid` but not noted | open | files/.../ts_public.h.md |
| 2026-06-11 | src/include/tsearch/ts_utils.h:229 | doc-drift | nit | `clean_NOT` return semantics (NULL vs aliased input vs new ptr) absent from header | open | files/.../ts_utils.h.md |
| 2026-06-11 | src/include/tsearch/ts_utils.h:91-96 | undocumented-invariant | maybe | `ParsedWord.apos[0]` is count "excluding apos[0]" — off-by-one trap | open | files/.../ts_utils.h.md |
| 2026-06-11 | src/include/tsearch/ts_type.h:38 | undocumented-invariant | likely | Wire format assumes `sizeof(WordEntry)==4`; relies on compiler packing 1+11+20 bitfield into uint32 | open | files/.../ts_type.h.md |
| 2026-06-11 | src/include/tsearch/ts_type.h:109 | question | maybe | `_POSVECPTR` silently wrong if WordEntry's pos/len mutate without resort | open | files/.../ts_type.h.md |
| 2026-06-11 | src/include/tsearch/ts_type.h:246-249 | undocumented-invariant | nit | TSQuery is "plain storage" per code-comment only, not catalog-enforced | open | files/.../ts_type.h.md |
| 2026-06-11 | src/include/tsearch/ts_type.h:166-169 | stale-todo | nit | `QueryOperand.valcrc` flagged "XXX pg_crc32 would be more appropriate" — long-standing | open | files/.../ts_type.h.md |
| 2026-06-11 | src/include/tsearch/ts_locale.h:64 | doc-drift | nit | Deprecated bare `t_isXxx` variants have no removal schedule | open | files/.../ts_locale.h.md |
| 2026-06-11 | src/include/tsearch/dicts/spell.h:32-34 | correctness | likely | `SPNodeData.affix:19` caps AffixData entries at 524288 with no overflow check | open | files/.../dicts/spell.h.md |
| 2026-06-11 | src/include/tsearch/dicts/spell.h:91-95 | correctness | maybe | `AFFIX.replen:14` caps replacement length at 16383 bytes | open | files/.../dicts/spell.h.md |
| 2026-06-11 | src/include/tsearch/dicts/spell.h:97-107 | style | nit | `pregex` vs `regis` union: pregex extracted to pointer for size, but the union still pays for the larger member | open | files/.../dicts/spell.h.md |
| 2026-06-11 | src/include/tsearch/dicts/spell.h:184-230 | undocumented-invariant | maybe | `IspellDict` mixes build-time-only and runtime fields in one struct | open | files/.../dicts/spell.h.md |
| 2026-06-11 | src/include/tsearch/dicts/regis.h:46-48 | doc-drift | nit | `RS_execute` null-termination contract not in header | open | files/.../dicts/regis.h.md |
| 2026-06-11 | src/include/tsearch/dicts/regis.h:24 | undocumented-invariant | nit | `RegisNode.data` layout per type-code not documented | open | files/.../dicts/regis.h.md |

## Wontfix / Submitted / Landed

(empty)

## Notes

- Bitfield-packing-dependent on-disk wire format (ts_type.h
  `WordEntry`) is the single highest Phase-D risk in this subdir —
  any compiler that packs 1+11+20 differently would corrupt
  pg_dump/pg_upgrade.
- The IspellDict-as-build-AND-runtime struct is a code-organization
  smell; a future patch that splits it would clarify the
  "fields are only used during dictionary construction" warning
  comment.
- All the tsearch ABI surface ultimately funnels through
  `ts_public.h`'s `TSLexeme`/`DictSubState` — these are public to
  third-party dictionary templates and must stay binary-stable.
