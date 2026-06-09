# ginfuncs.c

Covers `source/contrib/pageinspect/ginfuncs.c` (283 lines): GIN page
introspection — metapage, opaque header (flags + rightlink), leaf
posting-list decode.

## One-line summary

`gin_metapage_info` decodes the GIN metapage; `gin_page_opaque_info`
returns the (rightlink, maxoff, flags[]) opaque header for any GIN
page; `gin_leafpage_items` SRF-iterates the compressed posting lists
in a `GIN_DATA | GIN_LEAF | GIN_COMPRESSED` leaf, returning
(first-tid, nbytes, tids[]) per segment.

## Public API / entry points

- `gin_metapage_info(bytea)` — `:28`.
- `gin_page_opaque_info(bytea)` — `:96`.
- `gin_leafpage_items(bytea)` — `:179`.

## Key invariants

- INV-1: `superuser()` gate at `:39, :109, :185` [verified-by-code].
- INV-2: Special-space size must be
  `MAXALIGN(sizeof(GinPageOpaqueData))` (`:49, :119, :208`).
- INV-3: `gin_metapage_info` requires `opaq->flags == GIN_META` exactly
  (`:59`); other flag bits → ERROR "input page is not a GIN metapage".
- INV-4: `gin_leafpage_items` requires flags EXACTLY equal to
  `(GIN_DATA | GIN_LEAF | GIN_COMPRESSED)` (`:217`); uncompressed
  leaves or entry/data internal pages rejected.
- INV-5: New pages → NULL (`:46, :116, :202`).

## Notable internals

**Flag decoding into text[].** `gin_page_opaque_info` (`:134-157`)
sets bits one at a time and pushes the human name; unknown bits are
emitted in hex via `to_hex32` (`:156`). This matches the pattern in
`gistfuncs.c` and is forward-compatible: new flags just appear as
hex strings instead of erroring.

**Posting-list decode loop.** `:233-237`: state cursor walks from
`GinDataLeafPageGetPostingList(page)` to
`GinDataLeafPageGetPostingListSize(page)` bytes past it. Each
iteration:

- Reads `cur->first` (an ItemPointer) and `cur->nbytes`.
- Calls `ginPostingListDecode(cur, &ndecoded)` which varbyte-decodes
  the compressed TID stream.
- Builds an `array_builtin` of TID Datums and emits one row.
- Advances `cur = GinNextPostingListSegment(cur)`.

The loop terminator is `cur != lastseg`. If a corrupted page reports
`GinDataLeafPageGetPostingListSize` inconsistent with the actual
segment chain, the loop could over- or under-shoot. `lastseg` is
computed once at SRF init from `GinDataLeafPageGetPostingListSize`
which reads `((PageHeader)page)->pd_upper - pd_lower` style fields.

## Trust boundary / Phase D surface

**Strict flag matching is good defense.** Requiring flags EXACTLY
`(GIN_DATA | GIN_LEAF | GIN_COMPRESSED)` (`:217`) rules out most
mis-classified pages. `gin_page_opaque_info` is the only function
here that accepts any flag combination — and it only reads the
header, doesn't deref into the body.

**`ginPostingListDecode` is called on attacker-controlled bytes.**
The decode reads varbyte-encoded TIDs from `cur` for `cur->nbytes`.
A crafted bytea with `cur->nbytes` near `UINT16_MAX` and a
short-but-claims-long encoded stream is the realistic foothold for
read-overflow.
**[ISSUE-correctness: `ginPostingListDecode` is called with
`cur->nbytes` from on-page bytes; if `nbytes` extends past the
posting-list region, the decoder reads past `lastseg`. Bounded by
the special-space size check and `lastseg` computation, but the
decoder itself is not range-aware (likely; would need to read
`ginpostinglist.c` to confirm bounds)]** —
`source/contrib/pageinspect/ginfuncs.c:264`.

**RLS bypass via inverted-index keys.** GIN entries store the
inverted-index keys (text words for tsvector, array elements,
jsonb keys). These ARE the values that RLS-filtered rows
contributed. **[ISSUE-security: GIN leaf-page items leak the
inverted keys (e.g. tsvector lexemes, jsonb keys) for RLS-filtered
rows; superuser-bounded (likely; same shape as btree key leak)]**.

**No relation cross-check.** None of these functions take a regclass
arg — they're pure bytea decoders. There's no way for the C code to
validate the bytea came from a GIN index. The flag/special-space
checks are the only "is this GIN" defense.

**No `indisvalid` check.** All three accept any bytea; the original
extraction via `get_raw_page` doesn't check `indisvalid` either. A
mid-build GIN leaf can be inspected; decoded posting lists may be
incomplete.

**Auto-vacuum interaction.** N/A — bytea is detached. The "pending
list" GIN concept means a tsvector may have entries that are not yet
in any leaf; `gin_leafpage_items` won't see those.

**Metapage forward-compat.** `gin_metapage_info` returns
`ginVersion` (`:86`) as a separate column. Decoders can dispatch on
this. Unlike btree which gates whole behaviors on
`BTREE_NOVAC_VERSION`, GIN exposes the raw version.

## Cross-references

- `source/src/include/access/gin_private.h` — `GinPageOpaqueData`,
  `GIN_META`/`GIN_DATA`/`GIN_LEAF`/`GIN_COMPRESSED` constants,
  `GinMetaPageData`.
- `source/src/backend/access/gin/ginpostinglist.c` —
  `ginPostingListDecode`, the function called at `:264`.
- `source/src/backend/access/gin/ginget.c` — pending-list reading,
  not exposed here.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — bytea source.

## Issues spotted

- **[ISSUE-correctness: `ginPostingListDecode` is invoked on
  potentially-malicious bytes; out-of-range `nbytes` could over-read.
  Bounded by `lastseg` end check but the decoder itself is not
  caller-validated (likely)]** —
  `source/contrib/pageinspect/ginfuncs.c:264`.
- **[ISSUE-security: GIN leaf-pages leak inverted-index keys
  (lexemes, jsonb paths) for RLS-filtered rows (likely;
  superuser-bounded)]** — `:233-269`.
- **[ISSUE-correctness: pending-list contents are invisible to
  `gin_leafpage_items` — the function does not see uncompressed
  pending entries that may exist for the index (nit, documented gap
  in coverage)]**.
