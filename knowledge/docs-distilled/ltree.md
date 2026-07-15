---
source_url: https://www.postgresql.org/docs/current/ltree.html
fetched_at: 2026-07-14T20:51:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.23 ltree — hierarchical tree-like data type"
maps_to_skill: [access-method-apis, type-cache]
---

# Docs distilled — ltree (label-path type + lquery/ltxtquery + GiST/GIN opclass)

Three types (`ltree`, `lquery`, `ltxtquery`) + two GiST signature opclasses.
The canonical example of a **query-language type paired with a match operator
that a GiST signature index accelerates** — beyond the flat-set model of
`intarray`/`hstore`, this one indexes *ancestor/descendant* structure.

## Non-obvious claims

- **`ltree` is a varlena carrying a `uint16` level count then MAXALIGN'd
  variable-length labels.** Struct: `{ int32 vl_len_; uint16 numlevel; char
  data[] }` [[ltree.h:46]]; each label is `{ uint16 len; char name[] }`
  (`ltree_level`) [[ltree.h:37]]. Because `numlevel` is a `uint16`, the
  max labels per path is `LTREE_MAX_LEVELS = PG_UINT16_MAX` = **65535**
  [[ltree.h:53]]. [verified-by-code @ 1863452a4bfe]
- **Max label length is a hard 1000 chars:** `LTREE_LABEL_MAX_CHARS 1000`
  [[ltree.h:18]]. Allowed label characters are locale-dependent
  (`A-Za-z0-9_-` in C locale). [verified-by-code @ 1863452a4bfe] + [from-docs]
- **Two GiST opclasses, two different signature defaults** — both bit-signature
  (lossy) with a tunable `siglen`:
  - `gist_ltree_ops` (for `ltree`): `LTREE_SIGLEN_DEFAULT = 2*sizeof(int32)` =
    **8 bytes** [[ltree.h:181]]. Indexes `<`,`<=`,`=`,`>=`,`>`,`@>`,`<@`,`@`,`~`,`?`.
  - `gist__ltree_ops` (for `ltree[]`): `LTREE_ASIGLEN_DEFAULT = 7*sizeof(int32)`
    = **28 bytes** [[ltree.h:183]]. Indexes `ltree[] <@ ltree`, `ltree @> ltree[]`,
    `@`, `~`, `?`. Max siglen for both is `GISTMaxIndexKeySize`.
  [verified-by-code @ 1863452a4bfe] + [from-docs]
- **Signature hashing is the standard GiST-signature idiom** shared with
  `intarray`/`pg_trgm`: `HASHVAL(val,siglen) = (unsigned)val %
  SIGLENBIT(siglen)`, `HASH()` = `SETBIT(sign, HASHVAL(...))` [[ltree.h:164]].
  [verified-by-code @ 1863452a4bfe]
- **`@>`/`<@` are ancestor/descendant-or-equal**; `~` matches an `ltree`
  against an `lquery` regex; `@` matches against an `ltxtquery` full-text
  pattern; `?` matches against an *array* of lqueries. [from-docs]
- **`^`-prefixed operator variants (`^@>`,`^<@`,`^@`,`^~`) have identical
  semantics but deliberately bypass the index** — the escape hatch when the
  planner mis-picks the GiST path. [from-docs]
- **`lca()` (longest common ancestor) is capped at 8 direct `ltree` args**
  (or unbounded via the `ltree[]` overload). [from-docs]
- **lquery matching grammar** is richer than a glob: `*{n,m}` label-count
  quantifiers, and per-label modifiers `@` (case-insensitive), `*` (prefix),
  `%` (match on underscore-separated word boundaries), plus `|` (OR) and `!`
  (NOT) groups. Also B-tree (`<`…`>`) and hash (`=`) are supported for exact
  ordering/equality. [from-docs]

## Links into corpus

- `access-method-apis` skill — `gist_ltree_ops` is a third worked GiST
  signature opclass alongside `[[docs-distilled/hstore.md]]` (`gist_hstore_ops`)
  and `[[docs-distilled/intarray.md]]` (`gist__intbig_ops`); the `HASHVAL`/
  `SETBIT` signature construction is identical across all three.
- `[[knowledge/idioms/varlena-and-toast.md]]` — the `uint16 numlevel` +
  MAXALIGN'd `ltree_level` array is a compact packed-varlena layout worth
  citing when designing a new tree/path type.
- `[[docs-distilled/xindex.md]]` — opclass/strategy/support-function
  registration these opclasses instantiate.
