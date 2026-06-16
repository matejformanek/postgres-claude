# `src/backend/access/heap/heaptoast.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~791
- **Source:** `source/src/backend/access/heap/heaptoast.c`

Heap-table side of the TOAST machinery: decides what to compress
vs externalise on `INSERT`/`UPDATE` to fit a row into one heap page,
flattens tuples back to plain form when materialising container Datums,
and fetches arbitrary byte slices of an externalised value by walking
the toast-relation index. The four-pass compression-then-externalise
loop (EXTENDED-compress, EXTENDED-externalise, MAIN-compress,
MAIN-externalise) is the heart of `heap_toast_insert_or_update`.
[verified-by-code]

## API / entry points

- `heap_toast_delete(rel, oldtup, is_speculative)` — cascade-delete
  toast rows owned by `oldtup` on `DELETE`. Asserts the relation kind
  is plain table or matview (toast-on-toast recursion is forbidden,
  lines 50-54). Delegates the per-attribute work to
  `toast_delete_external` in `toast_helper.c`. [verified-by-code]
- `heap_toast_insert_or_update(rel, newtup, oldtup, options)` — main
  entry. Returns either `newtup` unchanged (no toasting needed) or a
  palloc'd new HeapTuple. Strips the `HEAP_INSERT_SPECULATIVE` bit
  before passing options downward (lines 113-119) — speculative
  insertions toast like normal ones. Comment at line 91 notes neither
  input is modified (post-8.1 API). [verified-by-code]
- `toast_flatten_tuple(tup, tupleDesc)` — return a new HeapTuple with
  all external pointers expanded. Preserves identity (`t_self`,
  `t_tableOid`) and copies HEAP_XACT_MASK / HEAP2_XACT_MASK visibility
  bits exactly so syscache lookups still work (lines 396-406).
  Compressed in-line datums are left compressed (comment at 343-344).
  [verified-by-code]
- `toast_flatten_tuple_to_datum(tup, tup_len, tupleDesc)` — flatten *and*
  decompress in-line compressed datums, building a Datum suitable for
  use as a composite-type value. Compression is undone here because the
  caller's container will recompress more effectively over the whole
  blob (comment at 435-442). [from-comment]
- `toast_build_flattened_tuple(tupleDesc, values, isnull)` — build a
  fresh tuple from `values[]`/`isnull[]`, expanding any external
  pointers in the input arrays. Used when assembling composite-type
  return values from C. [verified-by-code]
- `heap_fetch_toast_slice(toastrel, valueid, attrsize, sliceoffset,
  slicelength, result)` — read a contiguous byte range of an
  externalised value. Translates the byte range to a chunk-number
  range, opens the toast relation's valid index, runs an ordered
  systable scan with up to three keys (valueid + range), and copies
  chunks into `result`. [verified-by-code]

## Notable invariants / details

- Four-pass loop in `heap_toast_insert_or_update` (lines 159-271):
  - Pass 1: while too big, repeatedly pick biggest EXTENDED attribute;
    if EXTENDED, try compression; if EXTERNAL or just-compressed and
    still > maxDataLen, externalise immediately. Marks attributes
    `TOASTCOL_INCOMPRESSIBLE` after one attempt so they don't get tried
    again (line 204). [verified-by-code]
  - Pass 2: externalise any remaining inline EXTENDED/EXTERNAL.
  - Pass 3: only now try MAIN-storage attribute compression.
  - Pass 4: raise the data-len target to `TOAST_TUPLE_TARGET_MAIN` and
    externalise MAIN attributes as a last resort.
  - Each pass guards `rd_rel->reltoastrelid != InvalidOid` before
    externalising (lines 215-216, 227, 262) — a heap with no toast
    table cannot push values out and silently keeps trying compression.
  [verified-by-code]
- Comment at lines 213-214: `XXX maybe the threshold should be less than
  maxDataLen?` — a real performance question that hasn't been resolved.
  [ISSUE-stale-todo: open XXX about the immediate-externalise threshold
  in pass 1 (nit)]
- Reconstruction at lines 277-329: when any value changed, a whole new
  HeapTuple is palloc'd (`HEAPTUPLESIZE + new_tuple_len`); the old
  header is `memcpy`'d intact and only `natts` / `t_hoff` are adjusted.
  Comment at 285-294 explicitly warns that you can't reuse the old
  `t_hoff` because `ALTER TABLE ADD COLUMN` may have changed the
  null-bitmap length. [from-comment]
- `toast_flatten_tuple_to_datum` (line 449): sets the composite Datum
  header fields (`Length`, `TypeId`, `TypMod`) at lines 524-527 — these
  are slots in the standard `HeapTupleHeader` that are only meaningful
  for tuples used as Datums (not for on-heap rows). [verified-by-code]
- `heap_fetch_toast_slice` chunk validation (lines 737-758): every
  fetched chunk is checked for (a) correct sequence number, (b) being
  within `[startchunk, endchunk]`, and (c) correct chunk size
  (`TOAST_MAX_CHUNK_SIZE` except possibly for the last chunk). Any
  mismatch raises `ERRCODE_DATA_CORRUPTED` with an internal message
  including the toast relation name. Final guard at 781-786 enforces
  that the loop saw the expected end chunk. [verified-by-code]
- Chunk-of-chunk impossibility: line 728 raises
  `"found toasted toast chunk for toast value %u in %s"` if a chunk's
  varlena is itself externalised — toast-on-toast must not happen.
  This is the runtime check that pairs with the relkind assertion in
  `heap_toast_delete`. [verified-by-code]
- The toast row format allows a short-header chunk
  (`VARATT_IS_SHORT(chunk)`, line 719-723): comment notes this can
  happen from `heap_form_tuple` even though `toast_save_datum` always
  writes 4-byte-header chunks. Defensive parsing. [from-comment]
- `get_toast_snapshot()` (line 688) is the canonical snapshot for
  toast scans — defined in `snapmgr.c`; the helper enforces SnapshotMVCC
  semantics consistently with whoever opened the toast table.
  [verified-by-code]
- `toast_open_indexes` returns *all* of the toast relation's indexes
  plus an index into them of the currently valid one (`validIndex`,
  line 644-647); slice fetch only uses `toastidxs[validIndex]` but the
  full list is needed by `toast_close_indexes` for symmetric locking.
  [verified-by-code]

## Potential issues

- Line 213-214. `XXX maybe the threshold should be less than maxDataLen?`
  Active open question in pass 1: today the immediate-externalise check
  triggers only when a single attribute already exceeds `maxDataLen`,
  but smaller-than-maxDataLen values might also be worth externalising
  to leave room for others. Cosmetic. [ISSUE-stale-todo: open design
  question in compression loop (nit)]
- Lines 215-216 / 262. The `rel->rd_rel->reltoastrelid != InvalidOid`
  guards mean that on a heap with no toast table, pass 1 may loop
  futilely trying to compress already-compressed-and-still-too-big
  values; `toast_tuple_try_compression` marks them
  `TOASTCOL_INCOMPRESSIBLE` after one try, so this is bounded, but a
  near-full row on a no-toast relation will still ultimately error in
  `heap_form_tuple`. The error message there is generic ("row is too
  big"). [verified-by-code]
- Line 730-731. `chunksize = 0; chunkdata = NULL;` after `elog(ERROR,
  ...)` are "keep compiler quiet" assignments — `elog(ERROR)` does not
  return. Cosmetic. [verified-by-code]
- Line 691-696. The validation loop relies on `systable_getnext_ordered`
  to actually deliver chunks in order; if the underlying index is
  corrupted such that chunks come out of order, the first
  out-of-sequence row will raise `ERRCODE_DATA_CORRUPTED` — useful
  diagnostic, but the ERROR message uses `errmsg_internal` so it is not
  translated. Acceptable for a corruption path. [verified-by-code]
- `MaxHeapAttributeNumber` and `MaxTupleAttributeNumber` are used in
  fixed-size stack arrays (lines 46-47, 106-110, 355-357). Both are
  typically 1664; the four-array stack frame in
  `heap_toast_insert_or_update` is ~30 KB. Not a leak, but the stack
  footprint per call is high. [inferred]
- Lines 401-406. `toast_flatten_tuple` masks then OR-merges
  `HEAP_XACT_MASK` and `HEAP2_XACT_MASK` from the original tuple into
  the freshly-formed one. This is correct for syscache callers but
  surprising if the function were used in a different context — there's
  no comment explaining why we copy visibility bits at all. The block
  comment at 393-394 says "in case anybody looks at those fields in a
  syscache entry" but doesn't explain what *would* go wrong otherwise.
  [from-comment]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `access`](../../../../../issues/access.md)
<!-- issues:auto:end -->
