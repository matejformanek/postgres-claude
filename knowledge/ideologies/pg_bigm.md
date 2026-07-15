# pg_bigm — ideology / divergence notes

Extension: **pgbigm/pg_bigm** (`master`, control `default_version = '1.2'`,
`relocatable = true`, `module_pathname = '$libdir/pg_bigm'`)
`[verified-by-code: pg_bigm.control:1-5]`. A near-fork of core
`contrib/pg_trgm` that swaps the trigram (3-gram) index key for a **bigram
(2-gram)** key, so that full-text `LIKE '%…%'` search stays index-eligible on
short keywords and on non-alphabetic / multibyte text (Japanese especially) —
the regime where trigram indexing degrades to sequential / full-index scans.
It ships a single GIN operator class `gin_bigm_ops` over `text`, a similarity
operator `=%`, and its own GUC knobs. Originally by NTT DATA (2013), now the
pg_bigm Development Group.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched repo files (`bigm.h`,
> `bigm_op.c`, `bigm_gin.c`, `pg_bigm--1.2.sql`, `pg_bigm--1.0--1.1.sql`,
> `pg_bigm--1.1--1.2.sql`, `pg_bigm.control`, `Makefile`, `README.md`,
> `docs/pg_bigm_en.md`), **not** `source/`. Cites verified against files
> fetched 2026-07-14 (see Sources footer). This is a member of the
> **"custom GIN opclass for full-text / similarity search"** cluster — its
> direct core sibling is `[[contrib-pg_trgm]]` (trigram), and its divergence is
> best read as a controlled diff against it. Contrast the tokenizer-based CJK
> FTS cluster `[[zhparser]]` / `[[pg_jieba]]` (word segmentation feeding core
> `tsvector`) and the heavier engines `[[pgroonga]]` (embedded Groonga column
> store) / `[[pg_textsearch]]` (BM25). Similarity siblings: `[[smlar]]`,
> `[[pg_similarity]]`. Its distinguishing move is *lowering the n-gram size to
> keep the multibyte character verbatim in the key* — a change small in code
> but large in the class of queries it makes indexable.

---

## Domain & purpose

pg_bigm "provides full text search capability in PostgreSQL … [by allowing] a
user to create **2-gram (bigram) index** for faster full text search"
(`README.md:3-4`) `[from-README]`. The unit of work is a `text` column indexed
with a GIN index using the `gin_bigm_ops` operator class; queries run as
ordinary `LIKE '%keyword%'` pattern matches (or the `=%` similarity operator),
and the index accelerates them by decomposing both indexed values and query
into 2-grams (`docs/pg_bigm_en.md:220-262`) `[from-README]`.

The reason-for-being is stated as a direct comparison table against pg_trgm
(`docs/pg_bigm_en.md:26-95`) `[from-README]`: trigram indexing is "Not
supported" for non-alphabetic languages such as Japanese (unless one
recompiles pg_trgm with `KEEPONLYALNUM` commented out) and "Slow" for 1–2
character keywords, "because … only sequential scan or index full scan (not
normal index scan) can run" (`docs/pg_bigm_en.md:63-91`) `[from-README]`. A
2-gram keeps two-character keywords indexable and — critically — a bigram of
two multibyte characters is a valid, discriminating key where a trigram of a
2-character CJK string cannot even be formed. The tradeoff surfaced honestly:
bigram indexed columns cap at ~102 MB vs trigram's ~228 MB, because the per-key
struct is larger (`docs/pg_bigm_en.md:78-82,554-568`) `[from-README]`.

The extension is a **lens over user-owned `text`**: no new stored type, no new
access method — it registers support functions inside core's existing GIN AM.

---

## How it hooks into PG

pg_bigm is a loadable C extension that plugs into the **existing GIN access
method** via a custom operator class, plus a handful of SQL-callable helper
functions and four GUCs. Contrary to the "pure opclass, no init" shape one
might guess, it **does** define `_PG_init` — but only to register GUCs; there
is **no `ProcessUtility_hook`, planner_hook, background worker, or custom AM**
(`bigm_op.c:61-116`) `[verified-by-code]`. `PG_MODULE_MAGIC;` at
`bigm_op.c:28`.

- **Control file** `pg_bigm.control`: `comment = 'text similarity measurement
  and index searching based on bigrams'`, `default_version = '1.2'`,
  `module_pathname = '$libdir/pg_bigm'`, `relocatable = true`
  (`pg_bigm.control:1-5`) `[verified-by-code]`.

- **`_PG_init` defines four custom GUCs** (`bigm_op.c:61-116`)
  `[verified-by-code]`, all `pg_bigm.*`-prefixed and closed with
  `EmitWarningsOnPlaceholders("pg_bigm")` (`bigm_op.c:115`):
  - `pg_bigm.enable_recheck` — bool, `PGC_USERSET`, default `true`
    (`bigm_op.c:65-75`). Whether the heap recheck against the query runs.
  - `pg_bigm.gin_key_limit` — int, `PGC_USERSET`, default 0 (= no limit),
    range 0..`INT_MAX` (`bigm_op.c:77-88`). Caps how many bigram keys a query
    feeds to the GIN scan.
  - `pg_bigm.similarity_limit` — real, `PGC_USERSET`, default `0.3`, range
    0.0..1.0 (`bigm_op.c:90-101`). Threshold for `=%`.
  - `pg_bigm.last_update` — string, `PGC_INTERNAL`, `GUC_REPORT |
    GUC_NOT_IN_SAMPLE | GUC_DISALLOW_IN_FILE`, seeded from
    `BIGM_LAST_UPDATE "2025.09.03"` (`bigm_op.c:31,104-113`). A read-only
    "which build am I running" report knob. See `[[gucs-config]]`.

- **The GIN operator class** `gin_bigm_ops FOR TYPE text USING gin`
  (`pg_bigm--1.2.sql:55-65`) `[verified-by-code]` wires two operator strategies
  and five (later six) support functions into core GIN:
  - `OPERATOR 1  pg_catalog.~~ (text,text)` — i.e. `LIKE`
    (`pg_bigm--1.2.sql:58`), matching `LikeStrategyNumber = 1`
    (`bigm.h:32`).
  - `OPERATOR 2  =% (text,text)` — similarity (`pg_bigm--1.2.sql:59`),
    matching `SimilarityStrategyNumber = 2` (`bigm.h:33`).
  - `FUNCTION 1  bigmtextcmp` (compare), `FUNCTION 2 gin_extract_value_bigm`,
    `FUNCTION 3 gin_extract_query_bigm`, `FUNCTION 4 gin_bigm_consistent`,
    `FUNCTION 5 gin_bigm_compare_partial` (`pg_bigm--1.2.sql:60-64`), plus
    `STORAGE text` (`pg_bigm--1.2.sql:65`) — the key stored in the index is
    itself a `text` bigram, not an opaque hash.
  - `FUNCTION 6 gin_bigm_triconsistent` is added conditionally (server ≥ 9.4)
    via `ALTER OPERATOR FAMILY … ADD` inside a `DO` block
    (`pg_bigm--1.2.sql:78-92`) `[verified-by-code]`. See `[[access-method-apis]]`
    and the data-structure note on GIN's amproc slots.

- **The `=%` operator** is `CREATE OPERATOR =% (LEFTARG=text, RIGHTARG=text,
  PROCEDURE=bigm_similarity_op, COMMUTATOR='=%', RESTRICT=contsel,
  JOIN=contjoinsel)` (`pg_bigm--1.2.sql:19-26`) `[verified-by-code]` — a
  self-commutating operator that borrows core's containment selectivity
  estimators `contsel`/`contjoinsel`.

- **SQL-callable helpers** (`pg_bigm--1.2.sql`): `show_bigm(text)→text[]`
  (debug: dump the bigrams), `bigm_similarity(text,text)→float4`,
  `bigm_similarity_op(text,text)→bool`, `likequery(text)→text`,
  `pg_gin_pending_stats(regclass)→(pages int4, tuples int8)`
  (`pg_bigm--1.2.sql:4-15,49-52,67-75`) `[verified-by-code]`. Volatility is
  deliberate: readers are `IMMUTABLE STRICT`, but `bigm_similarity_op` is
  `STRICT STABLE` "because depends on pg_bigm.similarity_limit"
  (`pg_bigm--1.2.sql:14-17`) `[verified-by-code]` — a GUC read makes it
  non-immutable, so it cannot be constant-folded.

- **Parallelism**: a `DO` block labels every function `PARALLEL SAFE` on server
  ≥ 9.6 (`pg_bigm--1.2.sql:94-114`) `[verified-by-code]`.

- **Build**: PGXS `MODULE_big = pg_bigm`, `OBJS = bigm_op.o bigm_gin.o`,
  `DATA = pg_bigm--1.2.sql pg_bigm--1.1--1.2.sql pg_bigm--1.0--1.1.sql`,
  `REGRESS = pg_bigm pg_bigm_ja` (`Makefile:1-8`) `[verified-by-code]`. A
  `pg_bigm_ja` regress suite (Japanese) is a first-class test, and an
  `installcheck-trgm` target runs the suite against a `load_trgm`-preloaded
  cluster to prove coexistence with pg_trgm (`Makefile:21-22`)
  `[verified-by-code]`. See `[[extension-development]]`.

---

## Where it diverges from core idioms

### 1. The GIN key is a variable-byte bigram struct, not a fixed hashed trigram

Core pg_trgm packs each trigram into a fixed 3-byte `trgm` and, for multibyte
input, **hashes** the character down (`compact_trigram`) so the key stays
3 bytes. pg_bigm instead keeps the raw bytes. Its key struct is:

```
typedef struct {
    bool  pmatch;      /* partial match is required? */
    int8  bytelen;     /* byte length of bi-gram string */
    char  str[8];      /* two chars, ≤4 bytes each */
} bigm;
```
(`bigm.h:35-45`) `[verified-by-code]`. Two multibyte characters at up to 4
bytes each ⇒ `str[8]`, and `bytelen` records the actual length. The naming is
explicit about the divergence: `compact_bigram` is "named … to maintain
consistency with pg_trgm, though it **does not reduce multibyte characters to
hash values** like in compact_trigram" (`bigm_op.c:214-223`) `[from-comment]`.
Consequences that follow directly:
- Comparison is a raw byte compare (`bigmstrcmp`, `bigm.h:49-66`; `CMPBIGM`,
  `bigm.h:68`) `[verified-by-code]`, so the ordering is bytewise on the encoded
  form, and similarity is **case-sensitive** — "ABC" vs "abc" scores 0, unlike
  pg_trgm's case-insensitive `similarity` (`docs/pg_bigm_en.md:399-413`)
  `[from-README]`.
- The larger per-key struct (`BIGMSIZE = sizeof(bigm)`, `bigm.h:47`;
  `CALCGTSIZE`, `bigm.h:86`) is *why* the indexed-column cap is ~102 MB, half
  of pg_trgm's ~228 MB (`docs/pg_bigm_en.md:78-82`) `[from-README]`,
  `[inferred]` (the byte-count follows from `sizeof(bigm)` vs `sizeof(trgm)=3`).
- The `bigm` set is materialized as a varlena `BIGM` (`bigm.h:80-88`), sorted
  and de-duplicated by `qsort_arg`+`unique_array` before storage
  (`bigm_op.c:339-346,137-156`) `[verified-by-code]`.

### 2. Bigram generation preserves multibyte boundaries and flags single-char keys

`generate_bigm` pads each word with a single leading and trailing space
(`LPADDING = RPADDING = 1`, `bigm.h:28-29`; padding applied `bigm_op.c:308-322`)
`[verified-by-code]` — so "ABC" ⇒ `" A"`, `"AB"`, `"BC"`, `"C "`
(`docs/pg_bigm_en.md:343-345`) `[from-README]`. `make_bigrams`
(`bigm_op.c:228-274`) has three paths `[verified-by-code]`:
- **`charlen < 2`** (a lone character): emit **one** bigram and set
  `bptr->pmatch = true` (`bigm_op.c:233-239`) — a partial-match key, meaning
  the GIN scan must treat it as a prefix rather than an exact key. This is the
  mechanism that keeps single-character keywords indexable.
- **multibyte path** (`bytelen > charlen`): walk `pg_mblen` boundaries so each
  emitted bigram is exactly two whole characters (`bigm_op.c:241-259`).
- **fast ASCII path** (`bytelen == charlen`): stride one byte at a time
  (`bigm_op.c:260-271`).

`find_word` splits the input on whitespace via `iswordchr` = `!t_isspace`
(`bigm_op.c:186,192-212`) `[verified-by-code]`. Word boundaries themselves
become searchable because of the space padding.

### 3. Wildcard-aware query extraction, borrowed from pg_trgm and kept in sync

For `LIKE`, `gin_extract_query_bigm` calls `generate_wildcard_bigm`
(`bigm_gin.c:133`, `bigm_op.c:515-584`) `[verified-by-code]`, whose
`get_wildcard_part` (`bigm_op.c:368-504`) is a near-verbatim adaptation of
pg_trgm's same-named routine: it extracts each non-wildcard substring bounded
by `%`/`_` meta-characters (`ISWILDCARDCHAR`, `bigm.h:78-79`), honoring `\`
escapes (`ISESCAPECHAR`, `bigm.h:77`), and pads only the boundaries not
abutting a wildcard (`bigm_op.c:415-500`). "given pattern 'a%bcd%' the bigrams
' a', 'bcd' would be extracted" (`bigm_op.c:509-512`) `[from-comment]`. The
divergence from core is purely the n-gram size baked into `make_bigrams`, not
the wildcard machinery — a deliberate "diff against pg_trgm, change one knob"
design.

### 4. Recheck can be *skipped* for provably-exact single-bigram queries

Core GIN always sets recheck for `LIKE` (the index is lossy). pg_bigm adds a
correctness optimization: `gin_extract_query_bigm` computes whether the query
is one that the index can answer exactly. "If the search word consists of one
or two characters and doesn't contain any space character, we can guarantee
that the index test would be exact" (`bigm_gin.c:141-165`) `[from-comment]`.
When `bgmlen == 1 && !removeDups` and the keyword has no whitespace, it stashes
`recheck = false` through `extra_data` (`bigm_gin.c:149-171`)
`[verified-by-code]`; otherwise `recheck = true`. Then `gin_bigm_consistent`
sets `*recheck = bigm_enable_recheck && ((nkeys != 1) || *((bool *)
extra_data[0]))` (`bigm_gin.c:244-245`) `[verified-by-code]`, and the parallel
`gin_bigm_triconsistent` returns `GIN_TRUE` (vs `GIN_MAYBE`) in exactly that
case (`bigm_gin.c:319-322,350-351`) `[verified-by-code]`. So the two GUCs and
the exactness proof combine: recheck is skipped only when both the user allows
it (`pg_bigm.enable_recheck`) and the query is provably exact. This is a
sharper recheck story than core's blanket lossy flag. See
`[[gin-scan-and-consistent]]`.

### 5. `LIKE`-consistency is an AND over all keys; similarity is a bounded ratio

For `LikeStrategyNumber`, consistency requires **every** extracted bigram to be
present — a plain AND loop, `res = false` on the first missing key
(`bigm_gin.c:247-256`) `[verified-by-code]`. For `SimilarityStrategyNumber`, it
counts present keys and applies an **upper-bound** shortcut: the true
similarity is `c / (len1+len2−c)` (or `c / max(len1,len2)`), but len2 is
unknown at consistency time, so it bounds it by `c / len1` = `ntrue / nkeys`
and compares to `bigm_similarity_limit` (`bigm_gin.c:258-286`) `[from-comment]`
`[verified-by-code]`. The exact score is recomputed at recheck by
`cnt_sml_bigm` (`bigm_op.c:625-665`), whose formula is compile-time selectable
via `DIVUNION` (`bigm_op.c:660-664`) `[verified-by-code]`.

### 6. `gin_bigm_compare_partial` compares only the *first* character of a key

Because single-char keywords produce a `pmatch` bigram (§2), GIN's partial-match
scan needs a comparator that treats keys sharing a leading character as a match.
`gin_bigm_compare_partial` compares the first multibyte character of the two
keys: if `pg_mblen` differs it returns 1 (no match); otherwise `memcmp` of that
one character, returning 0 (match) or 1 (`bigm_gin.c:363-385`)
`[verified-by-code]`. This is bespoke partial-match semantics that only make
sense given the space-padded single-char-key design; core pg_trgm has no
equivalent single-character path.

### 7. Ships a GIN pending-list introspection function core lacks

`pg_gin_pending_stats(regclass)` reaches into the GIN metapage
(`GIN_METAPAGE_BLKNO`, `GinPageGetMeta`) and reports `nPendingPages` /
`nPendingHeapTuples` (`bigm_gin.c:391-459`) `[verified-by-code]`, guarding
against non-GIN relations (`relam != GIN_AM_OID`) and other-session temp
indexes (`bigm_gin.c:406-421`). This is FASTUPDATE-pending-list observability
that core does not expose as a first-class function (it lives only in
`pageinspect`). See `[[gin-fastupdate-pending]]` and `[[gin-tree-structure]]`.

### 8. Portability shims that track upstream churn inside the extension

The extension copies core code that upstream *removed*: `t_isspace` "was part of
PostgreSQL 17 and earlier but was removed in commit d3aad4ac57c. This version
is copied from PostgreSQL 17" and re-exported for PG ≥ 18
(`bigm_op.c:158-184`, decl `bigm.h:90-92`) `[verified-by-code]` `[from-comment]`.
`bigm_gin.c` is threaded with `PG_VERSION_NUM` guards spanning 9.3 → 19
(`bigm_gin.c:21-31,49-52,435-439`; triconsistent gated at `bigm_op.c` /
`pg_bigm--1.2.sql:77-92`) `[verified-by-code]`. This is the maintenance cost of
being a long-lived out-of-tree fork of a moving core module. See
`[[extension-development]]`.

---

## Notable design decisions (with cites)

- **`likequery` as a convenience wrapper.** Converts a raw keyword into a
  `LIKE` pattern by wrapping in `%…%` and escaping `%`, `_`, `\`
  (`bigm_op.c:699-742`) `[verified-by-code]`; multibyte characters are copied
  whole via `pg_mblen` (`bigm_op.c:727-733`). Returns NULL for empty input
  (`bigm_op.c:713-714`). "Usually a client application should be responsible
  for this conversion. But you can save the effort … by using likequery"
  (`docs/pg_bigm_en.md:311-316`) `[from-README]`.
- **Overflow guards before palloc.** Both generators reject inputs where
  `slen` would overflow the `sizeof(bigm)` multiplication, erroring with
  `ERRCODE_PROGRAM_LIMIT_EXCEEDED` "out of memory" (`bigm_op.c:292-296,532-536`)
  `[verified-by-code]` — this is the mechanism behind the ~102 MB column cap
  (`docs/pg_bigm_en.md:554-568`) `[from-README]`. See `[[error-handling]]`.
- **`gin_key_limit` trades recall for scan cost.** When set, both strategies
  clamp `*nentries = Min(bigm_gin_key_limit, bgmlen)` (`bigm_gin.c:136-137,
  178-179`) `[verified-by-code]`; fewer keys ⇒ cheaper GIN scan but more false
  candidates and heavier recheck (`docs/pg_bigm_en.md:524-543`) `[from-README]`.
- **Empty-keyword fallback to full-index scan.** If no bigram is extractable,
  `searchMode = GIN_SEARCH_MODE_ALL` (`bigm_gin.c:213-214`) `[verified-by-code]`
  — the query still returns correct results, just via a full index scan.
- **`STORAGE text` keeps keys human-readable.** The GIN entries are the actual
  bigram text (`pg_bigm--1.2.sql:65`), which is what lets `show_bigm` round-trip
  keys as `text[]` for debugging (`bigm_op.c:586-623`) `[verified-by-code]`.
- **`=%` self-commutes and reuses containment selectivity.** `COMMUTATOR='=%'`,
  `RESTRICT=contsel`, `JOIN=contjoinsel` (`pg_bigm--1.2.sql:19-26`)
  `[verified-by-code]` — no bespoke selectivity estimator; it leans on core's
  containment heuristics.
- **The 1.0→1.1 upgrade renamed the opclass off a collision.** pg_bigm 1.0's
  operator class was named **`gin_trgm_ops`** — the *same name pg_trgm uses* —
  so 1.0 could not coexist with pg_trgm in one database; the `1.0--1.1` upgrade
  drops it (`pg_bigm--1.0--1.1.sql:4-5`) `[verified-by-code]`, and from 1.1 the
  class is `gin_bigm_ops`, allowing coexistence
  (`docs/pg_bigm_en.md:93-94`) `[from-README]`. The `installcheck-trgm` target
  (`Makefile:21-22`) is the regression proof of that coexistence.
- **The `1.1--1.2` upgrade added `gin_bigm_triconsistent` (amproc 6).** Same
  conditional-`DO`-block shape as the base install (`pg_bigm--1.1--1.2.sql:4-19`)
  `[verified-by-code]`, wiring GIN ternary consistency for servers ≥ 9.4.

---

## Links into corpus

- **`[[contrib-pg_trgm]]`** — the core trigram sibling and the whole point of
  contrast. pg_bigm is essentially pg_trgm with the n-gram size dropped from 3
  to 2 and the multibyte hash removed: the wildcard-part extraction
  (`get_wildcard_part`, `bigm_op.c:368-504`), the extract-value / extract-query
  / consistent / triconsistent support-fn set, and the space-padding convention
  are all descended from pg_trgm; the differences are (a) key size / no hashing
  (§1), (b) the single-char `pmatch` path (§2, §6), (c) GIN-only + LIKE-only
  scope, and (d) case-sensitivity. pg_trgm additionally supports GiST, ILIKE,
  and regex (`~`,`~*`) which pg_bigm drops (`docs/pg_bigm_en.md:47-84`).
- **`[[gin-scan-and-consistent]]`** — the `consistent` / `triConsistent`
  callbacks and the recheck-skipping exactness proof (§4, §5);
  `bigm_gin.c:219-361`.
- **`[[gin-fastupdate-pending]]`** — `pg_gin_pending_stats` reads the pending
  list off the metapage (§7); `bigm_gin.c:391-459`.
- **`[[gin-tree-structure]]`** — GIN entry-tree / `STORAGE text` keys, metapage
  layout the introspection function walks.
- **`[[access-method-apis]]`** — opclass strategy numbers (`LikeStrategyNumber`,
  `SimilarityStrategyNumber`, `bigm.h:31-33`) and amproc slots 1–6
  (`pg_bigm--1.2.sql:55-92`); registration via `CREATE OPERATOR CLASS` /
  `ALTER OPERATOR FAMILY`.
- **`[[gucs-config]]`** — the four `DefineCustom*Variable` calls + the
  `PGC_INTERNAL` read-only `last_update` report knob (`bigm_op.c:61-116`).
- **`[[fmgr-and-spi]]`** — `PG_FUNCTION_INFO_V1` entry points, `PG_GETARG_TEXT_*`
  / `PG_RETURN_*`, `construct_array` in `show_bigm`, `DirectFunctionCall2` in
  `bigm_similarity_op` (`bigm_op.c:586-697`).
- **`[[extension-development]]`** — PGXS `MODULE_big`, `_PG_init` GUC-only init,
  install + upgrade scripts, `PG_VERSION_NUM` portability shims (§8).
- **`[[catalog-conventions]]`** — `CREATE OPERATOR`, `CREATE OPERATOR CLASS`,
  `ALTER OPERATOR FAMILY`, conditional catalog edits via `DO` blocks.
- Sibling FTS / similarity ideologies (the divergence axis is the *mechanism*):
  **`[[zhparser]]`** and **`[[pg_jieba]]`** attack CJK search by *tokenizing*
  into words and feeding core `tsvector`/GIN — pg_bigm sidesteps segmentation
  entirely by fixed 2-gram decomposition (no dictionary, "supports all
  PostgreSQL encoding and locale", `docs/pg_bigm_en.md:172`). **`[[pgroonga]]`**
  embeds a whole external inverted-index engine (Groonga) and supports regex +
  ranking; pg_bigm stays inside core GIN. **`[[pg_textsearch]]`** brings BM25
  ranking. **`[[smlar]]` / `[[pg_similarity]]`** are the similarity-operator
  cousins — pg_bigm's `=%` + `bigm_similarity` overlap with their string-metric
  operators but pg_bigm's set is fixed at "bigram cosine-ish overlap"
  (`cnt_sml_bigm`, `bigm_op.c:625-665`) rather than a menu of algorithms.

> Corpus gap: the "long-lived out-of-tree fork of a core contrib module,
> carrying copied-forward core code across `PG_VERSION_NUM` boundaries" pattern
> (§8; `t_isspace` copied from PG17 after core removed it) has no idiom doc.
> pg_bigm and any pg_trgm-derived extension would anchor it. `[inferred]`

---

## Sources

Fetched 2026-07-14 (branch `master`), all via `raw.githubusercontent.com`,
base `https://raw.githubusercontent.com/pgbigm/pg_bigm/master/`. Probe pass at
2026-07-14T23:10:07Z, fetch pass at 2026-07-14T23:10:19Z. HTTP status per file:

- `README.md` → **200** (29 lines; purpose, doc index, license, copyright).
- `bigm_gin.c` → **200** (459 lines; deep-read — the five/six GIN support
  functions, recheck-exactness logic, similarity upper-bound consistency,
  partial-match comparator, pending-list stats).
- `bigm_op.c` → **200** (755 lines; deep-read — `_PG_init` GUCs, bigram
  generation `generate_bigm` / `generate_wildcard_bigm` / `make_bigrams` /
  `get_wildcard_part`, similarity `cnt_sml_bigm`, `likequery`, `t_isspace`
  shim).
- `bigm.h` → **200** (97 lines; `bigm` + `BIGM` structs, strategy numbers,
  padding, macros, function prototypes).
- `pg_bigm--1.2.sql` → **200** (114 lines; functions, `=%` operator,
  `gin_bigm_ops` opclass, conditional triconsistent, parallel-safe labels).
- `pg_bigm--1.0--1.1.sql` → **200** (5 lines; drops the collision-named
  `gin_trgm_ops`).
- `pg_bigm--1.1--1.2.sql` → **200** (41 lines; adds `gin_bigm_triconsistent`
  amproc 6 + parallel-safe labels).
- `pg_bigm.control` → **200** (5 lines; `default_version = '1.2'`,
  `relocatable = true`).
- `docs/pg_bigm_en.md` → **200** (574 lines; the English manual — pg_trgm
  comparison table, usage, recheck explanation, GUC docs, column-size limit).
- `Makefile` → **200** (22 lines; PGXS wiring, `REGRESS = pg_bigm pg_bigm_ja`,
  `installcheck-trgm` coexistence target).

**404s (probed, absent):** `bigm_gin.h`, `pg_bigm--1.0.sql`, `pg_bigm--1.1.sql`
— pg_bigm ships only the current base script (`pg_bigm--1.2.sql`) plus the two
upgrade scripts; there is no `bigm_gin.h` (all shared declarations live in
`bigm.h`). No other `*.c` beyond `bigm_op.c` / `bigm_gin.c` (confirmed by
`Makefile:2` `OBJS`).

All cites are `[verified-by-code]` against the fetched files except motivation /
usage / limits (`[from-README]` from `README.md` + `docs/pg_bigm_en.md`),
in-code rationale (`[from-comment]`), and the two reasoned points tagged
`[inferred]` (the ~102 MB cap following from `sizeof(bigm)`, §1; the missing
fork-maintenance idiom, Links). pg_trgm internals are cited from the corpus
doc `[[contrib-pg_trgm]]`, not re-fetched here.
