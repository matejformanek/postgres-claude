# `src/include/tsearch/ts_type.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~273
- **Source:** `source/src/include/tsearch/ts_type.h`

On-disk + in-memory layout for the `tsvector` and `tsquery` SQL types,
plus their fmgr access macros. This is THE phase-D-relevant header
for ts data — anyone parsing user-supplied tsvector/tsquery via
binary I/O must respect every alignment + sort invariant documented
here. [verified-by-code]

## API / declarations

### TSVector

- `WordEntry { haspos:1, len:11, pos:20 }` — packed into a uint32.
  `len` caps lexeme size at `MAXSTRLEN = 2047` bytes, `pos` (byte
  offset from end of WordEntry array to lexeme string) caps at
  `MAXSTRPOS = 1 MiB - 1`. [verified-by-code]
- `WordEntryPos` is a `uint16` with implicit `weight:2 | pos:14`
  layout; access via `WEP_GETWEIGHT(x)`, `WEP_GETPOS(x)`,
  `WEP_SETWEIGHT(x,v)`, `WEP_SETPOS(x,v)`. `MAXENTRYPOS = 1<<14`,
  positions saturate via `LIMITPOS(x)`. [verified-by-code]
- `WordEntryPosVector { uint16 npos; WordEntryPos pos[FLEX] }` +
  `WordEntryPosVector1` (exactly-1 specialization).
- `TSVectorData { vl_len_; int32 size; WordEntry entries[FLEX] }` —
  lexeme bytes + per-lexeme `WordEntryPosVector` (SHORTALIGNed) follow
  the entries[] array in a single varlena.
- Layout macros: `DATAHDRSIZE`, `CALCDATASIZE(nentries, lenstr)`,
  `ARRPTR(x)`, `STRPTR(x)`, `_POSVECPTR(x,e)`, `POSDATALEN(x,e)`,
  `POSDATAPTR(x,e)`. [verified-by-code]
- fmgr glue: `DatumGetTSVector` (PG_DETOAST_DATUM),
  `DatumGetTSVectorCopy` (PG_DETOAST_DATUM_COPY),
  `TSVectorGetDatum`, `PG_GETARG_TSVECTOR(n)`,
  `PG_GETARG_TSVECTOR_COPY(n)`, `PG_RETURN_TSVECTOR(x)`.
  [verified-by-code]

### TSQuery

- `QueryItemType { QI_VAL=1, QI_OPR=2, QI_VALSTOP=3 }`. `QI_VALSTOP`
  is only legal in the parser's intermediate stack — never on disk.
  [from-comment]
- `QueryOperand { type, weight:bitmask, prefix, valcrc:int32,
  length:12, distance:20 }` — `valcrc` is morally a pg_crc32 (cast as
  int32 because comparisons against signed ints are used in the
  code). [from-comment]
- `QueryOperator { type, oper:int8, distance:int16, left:uint32 }` —
  operands are reverse-Polish-style: right operand is `item+1`, left
  operand is `item + item->left`. [from-comment]
- `QueryItem` is the union of `{QueryItemType, QueryOperator,
  QueryOperand}`; TSQuery is 4-byte aligned so QueryItem must not
  contain `int64` fields. [from-comment]
- `TSQueryData { vl_len_, int32 size, char data[FLEX] }` — QueryItems
  followed by '\0'-terminated operand cstrings.
- Operator codes: `OP_NOT=1`, `OP_AND=2`, `OP_OR=3`, `OP_PHRASE=4`,
  `OP_COUNT=4`. Priorities via
  `tsearch_op_priority[OP_COUNT]` (PGDLLIMPORT const).
- Layout macros: `HDRSIZETQ`, `COMPUTESIZE`, `TSQUERY_TOO_BIG`,
  `GETQUERY(x)`, `GETOPERAND(x)`.
- fmgr glue: `DatumGetTSQuery`/`DatumGetTSQueryCopy` — TSQuery is
  marked plain storage (not toasted) but the `_COPY` variant still
  uses `PG_DETOAST_DATUM_COPY` "for simplicity". [from-comment]

## Notable invariants / details

- TSVector entries[] is sorted by `tsCompareString` (memcmp on the
  lexeme bytes). Per-lexeme positions inside `WordEntryPosVector`
  must also be sorted. [from-comment]
- "Note, tsvectorsend/recv believe that `sizeof(WordEntry) == 4`" —
  the binary I/O wire format is tied to the bitfield layout fitting
  in 4 bytes, which the bitfield declaration relies on a particular
  packing. [from-comment] [ISSUE-undocumented-invariant: relies on
  compiler packing 1+11+20 bits into a single uint32 (likely)]
- `MAXNUMPOS = 256` cap on positions per lexeme (defined here, used
  in ts_utils.h to size apos arrays).
- `TSQUERY_TOO_BIG` guards against integer overflow when sizing a
  TSQuery against `MaxAllocSize`. [verified-by-code]

## Potential issues

- `_POSVECPTR` uses `SHORTALIGN((e)->pos + (e)->len)` to find the
  WordEntryPosVector — assumes the WordEntry's `pos` byte offset
  plus its `len` is the byte position of the optional pos-vector
  prefix. If a caller mutates `e->pos` or `e->len` without re-sorting
  the lexemes the position pointer is silently wrong. [ISSUE-question:
  is there any path that updates WordEntry fields in place? (maybe)]
- TSQuery comment says "plain storage, so it can't be toasted but
  `PG_DETOAST_DATUM_COPY` is used for simplicity" — a future change
  that flips the `pg_type.typstorage` would need to coordinate with
  this assumption. [ISSUE-undocumented-invariant: TSQuery non-toast
  contract is per-code-comment, not catalog-enforced (nit)]
- `valcrc` documented as "XXX: pg_crc32 would be a more appropriate
  data type" — long-standing comment, never cleaned up.
  [ISSUE-stale-todo: QueryOperand.valcrc int32-vs-pg_crc32 XXX (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-tsearch`](../../../../issues/include-tsearch.md)
<!-- issues:auto:end -->
