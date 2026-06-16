# gistfuncs.c

Covers `source/contrib/pageinspect/gistfuncs.c` (370 lines): GiST
page introspection — opaque header decode + two item-decoders, one
bytea-only and one that consults the index for column-name display.

## One-line summary

`gist_page_opaque_info` returns (LSN, NSN, rightlink, flags[]);
`gist_page_items_bytea` emits raw IndexTuple bytes per item;
`gist_page_items` additionally calls per-column output functions to
produce a `record_out`-style "(col1, col2, …)" text representation.

## Public API / entry points

- `gist_page_opaque_info(bytea)` — `:74`.
- `gist_page_items_bytea(bytea)` — `:132`.
- `gist_page_items(bytea, regclass)` — `:197`.

## Key invariants

- INV-1: `superuser()` gate at `:86, :141, :211` [verified-by-code].
- INV-2: Special-space size + `gist_page_id` magic must match
  (`:53-68`) — both checks before any flag/item read.
- INV-3: New pages return NULL (`:93, :150, :229`).
- INV-4: Deleted pages emit a NOTICE (`:155, :258`) and leave
  `maxoff = InvalidOffsetNumber`, which short-circuits the
  `offset <= maxoff` loop without doing anything.
- INV-5: `gist_page_items` requires the index to be a GiST index
  (`:221`) — but allows any GiST index, including the one the bytea
  is NOT from.

## Notable internals

**Two-flavored item decoder.**
- `gist_page_items_bytea` (`:132-194`): emits `bytea` of the raw
  IndexTuple. No tupledesc, no output function calls.
- `gist_page_items` (`:197-369`): opens the index, fetches its
  tupledesc (truncated to key attrs only for non-leaf pages —
  `:248-251`), calls `index_deform_tuple` + per-column
  `OidOutputFunctionCall` for each item.

**Leaf-vs-internal handling.** `:240-251`: leaf pages get the full
tupledesc; internal pages get only `IndexRelationGetNumberOfKeyAttributes`
columns (truncated copy). The reason: internal-page tuples don't
have INCLUDE-attribute values, just the key.

**record_out-style escaping.** `:294-356` is a manual reimplementation
of `record_out`'s quoting logic — checks for `"`, `\`, `(`, `)`,
`,`, whitespace; emits double-quotes and backslash-escapes inside.
This is the only place pageinspect emits SQL-display values rather
than raw bytes.

**`pg_get_indexdef_columns_extended` for header.** `:253-254` uses
the ruleutils API to format the index columns line — same code path
the `\d` command takes.

## Trust boundary / Phase D surface

**`gist_page_items` accepts mismatched bytea+index.** Same flaw as
`brin_page_items`: the bytea could be from a totally unrelated GiST
index. `verify_gist_page` (`:43-71`) confirms shape but doesn't
correlate. `index_deform_tuple` (`:282`) then deforms under the
WRONG tupledesc. The per-column output function calls happen on
bytes that aren't that type → can range from "garbage output" to
"output-function crash".
**[ISSUE-correctness: bytea is not cross-validated against
`indexRelid`'s tupledesc; mismatched pair decodes under wrong types
and may crash inside output functions (likely)]** —
`source/contrib/pageinspect/gistfuncs.c:282`.

**Output-function call on attacker bytes (same as BRIN).** `:313-314`:
`getTypeOutputInfo`, then `OidOutputFunctionCall`. If a custom GiST
opclass has a buggy output function, fabricated bytes can trigger
it. Bounded by superuser.

**`PageGetItem` without bounds re-check.** `:170-176, :275-280`:
same pattern as btreefuncs — `PageGetItemId` then `ItemIdIsValid`
check then `PageGetItem`. No `lp_off + lp_len <= BLCKSZ` defense
beyond what `PageGetItemId` does. `IndexTupleSize(itup)` is then
read from the deref'd bytes (`:176, :289`). If `lp_len` is bogus
but `ItemIdIsValid` passes, the size read could be out of range.
**[ISSUE-correctness: `IndexTupleSize` is read from
attacker-controlled bytes and used as `memcpy` length at `:186`;
no upper bound on `tuple_len` before `palloc + memcpy`. Bounded by
the page size but could panic palloc on negative-cast-as-uint32
(maybe)]** —
`source/contrib/pageinspect/gistfuncs.c:176-186`.

**RLS bypass via spatial keys.** GiST is used for geometry / range
/ ltree / inet / tsquery / pg_trgm. The "key" bytes leaked here are
the indexed values (bounding boxes for geometry, range bounds for
ranges). Heavier than B-tree key leak because GiST is commonly used
on PII (geo coordinates, ranges).
**[ISSUE-security: GiST key extraction reveals indexed values
(e.g. geometry bounding boxes, range bounds) for RLS-filtered rows;
heavier than btree leak because of common GiST use cases (likely)]**.

**`maxoff` for deleted pages.** Smart: `:153-157`: NOTICE +
`maxoff = InvalidOffsetNumber` so the loop body never runs. No
crash on deleted-page bytea.

**`gist_page_id` magic.** GiST has an explicit page-ID field
(`GIST_PAGE_ID`) checked at `:62-68`. This is a stronger "is this
really GiST" test than just special-space size — a random page that
happens to have the right special-space size won't have the magic.
Defense in depth.

**CONCURRENTLY-built GiST.** No `indisvalid` check on the index
(`:219-225`). Mid-build GiST inspection: same risk as BRIN/btree.

**Auto-vacuum interaction.** GiST VACUUM can delete pages
(`F_DELETED` flag). The bytea decode handles deleted pages cleanly
(NOTICE + empty iteration). No race risk because bytea is detached.

## Cross-references

- `source/src/include/access/gist.h` — `GISTPageOpaqueData`,
  `GistPageGetOpaque`, `GistPageIsLeaf`, `F_LEAF`/`F_DELETED`/etc.
- `source/src/backend/access/gist/gistutil.c` — `gistformtuple` /
  `gistDeCompressAtt`, the writer side.
- `source/src/backend/utils/adt/ruleutils.c` —
  `pg_get_indexdef_columns_extended` at `:253`.
- `knowledge/files/contrib/pageinspect/pageinspect.md` — bytea source.

<!-- issues:auto:begin -->
- [Issue register — `pageinspect`](../../../issues/pageinspect.md)
<!-- issues:auto:end -->

## Issues spotted

- **[ISSUE-correctness: bytea + regclass not cross-validated;
  mismatched pair may crash inside output functions (likely)]** —
  `source/contrib/pageinspect/gistfuncs.c:282`.
- **[ISSUE-correctness: `IndexTupleSize` from on-page bytes is used
  as `memcpy` length at `:186` without an explicit upper-bound
  check (maybe; bounded by PageGetItem invariants)]** — `:176-186`.
- **[ISSUE-security: GiST key bytes leak geometry/range/inet/tsquery
  data for RLS-filtered rows; particularly impactful for geo PII
  (likely)]** — `:282-356`.
- **[ISSUE-security: per-opclass output functions called on
  attacker-controlled bytes; foothold for buggy GiST opclass
  output fns (maybe; superuser-bounded)]** — `:313-314`.
- **[ISSUE-defense-in-depth: GIST_PAGE_ID magic check at `:62-68`
  is good; suggests amcheck/pageinspect should adopt this pattern
  for AMs that lack a magic byte (nit, positive note)]**.
