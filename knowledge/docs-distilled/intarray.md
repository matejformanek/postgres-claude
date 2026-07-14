---
source_url: https://www.postgresql.org/docs/current/intarray.html
fetched_at: 2026-07-14T20:54:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.20 intarray — manipulate arrays of integers"
maps_to_skill: [access-method-apis, type-cache]
---

# Docs distilled — intarray (int[] set operators + dual GiST + GIN opclasses)

Operators + opclasses for 1-D **non-null** integer arrays treated as sets. The
canonical example of an opclass family that ships **two GiST strategies for the
same type** — an exact range-list for small sets and a lossy bitmap signature
for large sets — plus a `query_int` boolean query type. RD-tree with built-in
lossy compression.

## Non-obvious claims

- **Operates only on 1-D arrays of non-NULL `int4`.** A NULL element raises an
  error; multi-dimensional input is flattened to storage order. [from-docs]
- **Two GiST opclasses, chosen by set size:**
  - `gist__int_ops` (**default**) — approximates the set as an **array of
    integer ranges** (exact-ish, RD-tree). Parameter `numranges`, **default
    100**, valid 1–253 [from-docs]. The compile-time ceiling is computed:
    `G_INT_NUMRANGES_MAX = (GISTMaxIndexKeySize - VARHDRSZ) / (2*sizeof(int32))`
    [[_int.h:7]]. [verified-by-code @ 1863452a4bfe]
  - `gist__intbig_ops` (**for large sets**) — approximates the set as a
    **lossy bitmap signature**. Parameter `siglen`.
    **⚠ DOCS BUG:** the current docs state the default siglen is "16 bytes",
    but the opclass actually registers **`SIGLEN_DEFAULT = (63 * 4)` = 252
    bytes** — `add_local_int_reloption(relopts, "siglen", …, SIGLEN_DEFAULT,
    1, SIGLEN_MAX, …)` [[_intbig_gist.c:578]] with `#define SIGLEN_DEFAULT
    (63 * 4)` [[_int.h:58]]. Trust the code: default is 252 bytes, max is
    `GISTMaxIndexKeySize`. [verified-by-code @ 1863452a4bfe]
- **`gin__int_ops` (non-default GIN)** indexes `&&`, `@>`, `<@`, `@@`, and array
  equality. GIN is exact, so it avoids the recheck the lossy `gist__intbig_ops`
  forces. [from-docs]
- **`query_int` + `@@`** give boolean set-membership queries: `'1&(2|3)'::query_int`
  matches arrays containing 1 AND (2 OR 3), with `&`(AND) `|`(OR) `!`(NOT) and
  parentheses. Both GiST opclasses and `gin__int_ops` accelerate `@@`.
  [from-docs]
- **Set operators**: `&&` overlap, `@>`/`<@` containment, `|` union, `&`
  intersection, `+` append/concat, `-` difference, `#` count(prefix) or
  index-of(infix). [from-docs]
- **Signature bitmap idiom** shared with `ltree`/`pg_trgm`: `SIGLENBIT(siglen)
  = siglen*BITS_PER_BYTE`, `GETBIT`/`SETBIT`/`CLRBIT` [[_int.h:59]], with an
  `ALLISTRUE 0x04` all-ones fast path [[_int.h:81]]. [verified-by-code @ 1863452a4bfe]
- **Helper functions**: `icount`, `sort`/`sort_asc`/`sort_desc`, `uniq`
  (dedup *adjacent* — sort first), `idx`, `subarray`, `intset`. [from-docs]

## Links into corpus

- `access-method-apis` skill — intarray is the reference for **choosing between
  exact and lossy GiST strategies for one type**; the `gist__int_ops` (range
  list) vs `gist__intbig_ops` (signature) split is the design lesson. The
  signature side is identical machinery to `[[docs-distilled/ltree.md]]` and
  `[[docs-distilled/hstore.md]]`.
- `[[docs-distilled/btree-gin.md]]` / `[[docs-distilled/gin.md]]` — the GIN
  opclass (`gin__int_ops`) contract and exact-vs-lossy recheck.
- **hf(docs) candidate**: the intarray page's `gist__intbig_ops` siglen default
  ("16 bytes") is wrong vs source (`63*4 = 252`) — an upstream doc-fix worth a
  `pgsql-docs` note.
