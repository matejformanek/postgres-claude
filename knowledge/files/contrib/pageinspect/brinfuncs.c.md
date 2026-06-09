# brinfuncs.c

Covers `source/contrib/pageinspect/brinfuncs.c` (437 lines): BRIN
index page introspection — page-type classification, regular-page
item decode (one row per indexed attribute per range), metapage
fields, and revmap TID array dump.

## One-line summary

Four entry points, all bytea-based: `brin_page_type` classifies (meta
/ revmap / regular); `brin_page_items` decodes a regular page using
the live index's `BrinDesc` to call each opclass's output function;
`brin_metapage_info` reads the metapage fields; `brin_revmap_data`
yields the TID array out of a revmap page.

## Public API / entry points

- `brin_page_type(bytea raw_page)` —
  `source/contrib/pageinspect/brinfuncs.c:45`.
- `brin_page_items(bytea raw_page, regclass index)` —
  `:130`. Takes BOTH a bytea AND an open index — the index supplies
  the `BrinDesc` and opclass output functions.
- `brin_metapage_info(bytea raw_page)` — `:344`.
- `brin_revmap_data(bytea raw_page)` — `:385`, SRF returning
  `REVMAP_PAGE_MAXITEMS` TIDs from the page's `RevmapContents.rm_tids`.

## Key invariants

- INV-1: `superuser()` gate on all four entry points (`:51, :144,
  :354, :394`) [verified-by-code].
- INV-2: `verify_brin_page` (`:93-119`) checks BOTH special-space
  size (`MAXALIGN(sizeof(BrinSpecialSpace))`) AND that
  `BrinPageType(page)` matches the expected type. Errors with
  "page is not a BRIN page of type \"%s\"".
- INV-3: New pages (`PageIsNew`) return early with NULL or empty
  result instead of erroring (`:58, :179, :361, :414`) —
  consistent across the file.
- INV-4: `brin_page_items` requires v1.12+ SQL rowtype
  (`BRIN_PAGE_ITEMS_V1_12 = 8`) — `:160-164`, errors with
  "function has wrong number of declared columns".
- INV-5: Opens the index relation under `AccessShareLock` (`:166`)
  and validates `IS_BRIN(indexRel)` (`:168`). Bytea + index must be
  consistent or output is garbage (no cross-check).

## Notable internals

**Page-type discriminator via special space.** Same idiom as
btreefuncs — special space size = `MAXALIGN(sizeof(BrinSpecialSpace))`
is the "is this BRIN" check, then `BrinPageType(page)` reads the
type byte. `verify_brin_page` is the shared validator.

**`brin_page_items` walks attributes, not items.** The outer loop
(`:216-335`) emits one row per (offset, attribute) pair, NOT one
row per item. The `dtup == NULL` check at `:227` is the
"start-of-tuple" signal; on first attribute of a new tuple it
deforms via `brin_deform_tuple` (`:235`) and stores in `dtup`. After
all attributes are emitted, `pfree(dtup); dtup = NULL` (`:325-326`)
and offset advances.

**OutputFunctionCall per opclass slot.** `:189-211`: for each
indexed attr, look up `getTypeOutputInfo` and cache a `FmgrInfo`.
Then `:298` calls the output function on each stored value
(`bv_values[i]`). This is the only place in pageinspect where a
type's output function actually runs — most other functions emit
raw bytes. **So BRIN's per-AM decoder, unlike heap/btree decoders,
does respect type-output safety. The bytea→display path goes
through registered `Oid` output functions.**

**Revmap dump is a fixed-size array.** `:432`: iterate
`state->idx < REVMAP_PAGE_MAXITEMS`. The revmap page layout is
exactly `RevmapContents` followed by `rm_tids[REVMAP_PAGE_MAXITEMS]`.
Hard-coded count, not data-driven — so a corrupted page can't extend
or shrink the count.

**`ItemIdIsUsed` filter.** `:233`: unused items emit a row with
NULLs (`:248-256`), so output is dense in (offset, attno) space and
sparse-but-NULL-marked in unused positions.

## Trust boundary / Phase D surface

**Cross-check gap: bytea vs index.** `brin_page_items` takes a bytea
and a regclass. The bytea is checked for "looks like a BRIN regular
page" via `verify_brin_page` (`:177`). The index is checked for
`IS_BRIN`. But the bytea could be from a completely different BRIN
index than `indexRelid`. The `BrinDesc` built from `indexRelid` will
then be applied to bytes from another index — output is decoded
under the wrong tupledesc. **No segfault risk** because tupdesc
defines just attribute count + types, and the loop bounds use
`bdesc->bd_tupdesc->natts`, but values come out wrong (or trigger
output-function errors on bytes that aren't that type).
**[ISSUE-correctness: bytea is not cross-validated against
`indexRelid`'s BrinDesc; a mismatched pair produces nonsense but
doesn't crash (nit)]** — `:130-186`.

**Output-function-driven attack surface.** Unlike heap_page_items
which emits raw bytes, brin_page_items invokes the registered
output function for every stored value. If a BRIN opclass has a
buggy output function that crashes on malformed input, a fabricated
bytea (made by a superuser, in the chain-of-trust model) can trigger
that. Same chain-of-trust argument as elsewhere.
**[ISSUE-security: output-function call on attacker-controlled bytes
gives a foothold into per-opclass output bugs; bounded by superuser
(maybe; theoretical, no known bugs)]** —
`source/contrib/pageinspect/brinfuncs.c:298`.

**`PageGetItem` on possibly-bogus line-pointer.** `:232-236`:
`itemId = PageGetItemId(page, offset)`; if `ItemIdIsUsed`,
`PageGetItem(page, itemId)`. The validity check is just "used vs
not"; there's no `lp_off + lp_len <= BLCKSZ` defense like in
heapfuncs (`:202-205`). A bytea with a corrupted line pointer can
trick `PageGetItem` into pointing past page end.
**[ISSUE-correctness: no bounds check on `lp_off+lp_len <= BLCKSZ`
before `PageGetItem`; `brin_deform_tuple` then reads varying-width
varlena length bytes from that point; trust hierarchy assumes
upstream `PageGetItem` invariants from `PageAddItem` hold (likely)]**
— `:233-236`. Same concern in btreefuncs.c.

**Bounds on `offset > PageGetMaxOffsetNumber`.** `:333` is the loop
exit. `PageGetMaxOffsetNumber` reads `pd_lower` from the page header
— a corrupted `pd_lower` could make this miscount. The
`verify_brin_page` special-space check doesn't validate `pd_lower`.

**RLS bypass via summarization data.** BRIN summaries are
min/max-style sketches of the indexed columns. They're not the raw
heap tuples, but they DO leak the value distribution of the column
including columns that RLS would filter. E.g. an `int8 created_at`
column with RLS hiding 2026 rows still has its min/max appear in
BRIN summaries. **[ISSUE-security: BRIN summaries (min/max etc.)
leak distribution info for columns whose rows are RLS-filtered
(likely; lower severity than heap-page leak)]**.

**Revmap-page exposure.** `brin_revmap_data` returns
`REVMAP_PAGE_MAXITEMS` TIDs verbatim — these are (blkno, offsetno)
pointers into the regular BRIN pages. Used together with
`brin_page_items` they reconstruct the summarization but don't leak
heap data directly. Lower-impact than `brin_page_items`.

**CONCURRENTLY-built BRIN.** No `indisvalid` check on the index
relation in `brin_page_items` (`:166-172`). A mid-build BRIN can be
inspected; results may be partial.

**Auto-vacuum interaction.** `AccessShareLock` on the index allows
concurrent BRIN summarization (`brin_summarize_new_values` /
autovacuum). The bytea is a detached snapshot, but the `BrinDesc`
built at `:174` could outlive the bytea's notion of opclasses if
ALTER OPERATOR FAMILY runs concurrently — vanishingly rare.

## Cross-references

- `source/src/include/access/brin_page.h` — `BrinSpecialSpace`,
  `BrinPageType`, page-type constants.
- `source/src/include/access/brin_tuple.h` — `BrinTuple`,
  `BrinMemTuple`, `brin_deform_tuple`.
- `source/src/backend/access/brin/brin_pageops.c` — the writer side
  this file's reader complements.
- `source/src/backend/access/brin/brin_revmap.c` — revmap layout
  `brin_revmap_data` reads.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — the
  `get_raw_page` source.

## Issues spotted

- **[ISSUE-correctness: `brin_page_items` does not cross-validate
  bytea against `indexRelid`'s BrinDesc; mismatched pair decodes
  under wrong tupdesc (nit)]** —
  `source/contrib/pageinspect/brinfuncs.c:130-186`.
- **[ISSUE-correctness: no `lp_off+lp_len <= BLCKSZ` check before
  `PageGetItem` in the decode loop (likely; relies on `PageGetItem`
  upstream invariants holding for fabricated bytea)]** — `:233-236`.
- **[ISSUE-security: per-opclass output functions invoked on
  attacker-controlled bytes — foothold for buggy output fns; bounded
  by superuser gate (maybe; theoretical)]** — `:298`.
- **[ISSUE-security: BRIN summaries leak min/max-style distribution
  info for RLS-protected columns (likely; lower-impact than heap-page
  leak)]** — `:280-307`.
- **[ISSUE-defense-in-depth: rowtype-natts check at `:160-164` is the
  only versioning guard; older extension installs that don't get
  upgraded will hit the error path with a hint — but no
  forward-compat alternative (nit)]**.
