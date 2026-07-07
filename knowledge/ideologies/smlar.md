# smlar — array similarity (cosine / TF-IDF / overlap) made GiST- and GIN-indexable, with the formula chosen at runtime by a GUC

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `jirutka/smlar` @ branch `master` — a maintained fork of the original
> Sigaev & Bartunov smlar (sigaev.ru / `sai-agora`). The README is a plain
> `README` file (no extension). All `file:line` cites below point into that repo
> (not `source/`), since this doc characterizes an *external* extension's
> divergence from core idioms. Cites verified against the files fetched on
> 2026-07-06 (see Sources footer). smlar is by the same authors as core GiN/GiST,
> intarray, and pg_trgm, so its opclass code is deeply idiomatic PG — the
> divergences are semantic, not stylistic.

## Domain & purpose

smlar computes a **float4 similarity between two one-dimensional arrays** of the
same element type (`README:1-20`). Three formulas are offered: **cosine**
(`|A∩B| / sqrt(|A|·|B|)`), **TF-IDF** (frequency-weighted cosine over a
set-wide statistics table), and **overlap** (raw `|A∩B|`) `[from-README]`
(`README:58-60`). The headline is that this similarity is made **indexable**:
`a % b` ("a is similar to b above a threshold") and `a && b` (overlap) are
accelerated by both **GiST** and **GIN** operator classes across ~24 array types
(`README:90-116`) `[from-README]`. So "find rows whose tag/keyword/feature array
is similar to this one" becomes an index scan rather than a seq-scan
`smlar()` over the whole table. It is a set-similarity engine, and the whole
design is oriented around mapping a *real-valued threshold predicate* onto the
index AM's *boolean consistent* contract.

## How it hooks into PG

- **`PG_MODULE_MAGIC`** at `smlar.c:25` `[verified-by-code]`. The extension is a
  `MODULE_big` of seven objects (`Makefile:2-4`).
- **No `_PG_init`.** Grepping the C sources finds no `_PG_init`
  `[verified-by-code]` — unusual for a GUC-registering extension. Instead the
  six GUCs are registered **lazily** by `initSmlarGUC()`, guarded by a static
  `smlar_guc_inited` flag (`smlar_guc.c:56-60,144`), and every GUC getter calls
  it on first use (e.g. `getSmlType` → `initSmlarGUC()` at
  `smlar_guc.c:183-190`) `[verified-by-code]`. The GUCs therefore materialize the
  first time any smlar function runs in a backend, not at load time. Consequence:
  the GUCs are invisible to `SHOW`/`postgresql.conf` validation until a smlar
  function has been called in that session — a real divergence from the
  `_PG_init`-registers-everything idiom (contrast `.claude/skills/gucs-config/SKILL.md`).
- **The operator/opclass/type catalog wiring lives in the install SQL**
  (`smlar--1.0.sql`): the `%` operator (`CREATE OPERATOR %`,
  `smlar--1.0.sql:34-41`), a GiST STORAGE type `gsmlsign` with fake I/O
  (`smlar--1.0.sql:77-81`), and per-array-type `CREATE OPERATOR CLASS … USING gist`
  / `… USING gin` blocks (`smlar--1.0.sql:121-133`, `463-472`)
  `[verified-by-code]`.
- **Strategy numbers**: `SmlarOverlapStrategy = 1`, `SmlarSimilarityStrategy = 2`
  (`smlar.h:85-86`). In the opclasses, strategy 1 is `&&` and strategy 2 is `%`
  (`smlar--1.0.sql:124-125`). The `&&` (overlap) operator is **core PG's built-in
  array-overlap operator, reused** — smlar never declares its own `&&`
  (grep finds only opclass references, never a `CREATE OPERATOR &&`)
  `[inferred]`. Only `%` is smlar's own.
- **GiST support functions** are the full classic set: consistent/union/compress/
  decompress/penalty/picksplit/same as FUNCTION 1–7
  (`smlar--1.0.sql:126-132`). **GIN** wires FUNCTION 1 = the type's btree
  `cmp` (e.g. `btint4cmp`), 2 = `smlararrayextract` (extractValue), 3 =
  `smlarqueryarrayextract` (extractQuery), 4 = `smlararrayconsistent`
  (`smlar--1.0.sql:468-471`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. GUC-selected operator semantics — the `%` operator's meaning is session state

The similarity formula is an **enum GUC**, `smlar.type ∈ {cosine, tfidf, overlap}`
at `PGC_SUSET` (`smlar_guc.c:90-102`), and every evaluation path dispatches on
`getSmlType()` at runtime: the scalar `smlar()` (`smlar.c:688`), the `%`
predicate `arraysml_op` (`smlar.c:823`), the GiST consistent (`smlar_gist.c:1044,
1092,1133`) and GIN consistent (`smlar_gin.c:98-145`) `[verified-by-code]`.
`smlar.threshold` (the `%` cutoff, `PGC_USERSET`, `smlar_guc.c:62-75`),
`smlar.tf_method` (`PGC_SUSET`, `smlar_guc.c:130-142`), and `smlar.idf_plus_one`
(`smlar_guc.c:117-128`) further mutate the result. So **the same `a % b` returns
different booleans depending on session GUCs** — operator semantics as mutable
state, exactly the uuidv47 / postgresql-unit divergence axis.

The immutability story is inconsistent and, for indexing, unsafe: `smlar(anyarray,
anyarray)` is declared `IMMUTABLE` (`smlar--1.0.sql:4-7`) even though its output
depends on `smlar.type`/`threshold`/`tf_method`/`stattable`. The `%` operator's
own procedure `smlar_op` is more honestly declared `STABLE`
(`smlar--1.0.sql:29-32`) `[verified-by-code]`. Because `%` and `&&` back GiST/GIN
opclasses, an index built while `smlar.type = cosine` and then queried while
`smlar.type = tfidf` will apply mismatched math in `consistent` — the
threshold-to-boolean mapping is only valid when the session's GUC matches the
formula the caller intends. This is the extension's sharpest break with core's
"an indexable operator has fixed semantics" contract.

### 2. Similarity defined by a runtime SQL formula string, executed via SPI

The third form, `smlar(a, b, 'N.i / sqrt(N.a * N.b)')` (`README:10-20`), takes a
**text formula** with variables `N.i` (intersection size), `N.a`, `N.b` (the two
cardinalities) and evaluates it by *building a SQL query string and running it
through SPI* (`arraysml_func`, `smlar.c:856-942`): it `stpcpy`s the user formula
into `SELECT (<formula>)::float4 FROM (SELECT $1 AS i, …) AS N`, `SPI_prepare`s
it, and `SPI_saveplan`s it in a **one-slot static cache** (`cachedFormula` /
`cachedPlan`, `smlar.c:851-854,894-923`) keyed by the raw formula bytes
`[verified-by-code]`. Operator semantics supplied as a runtime-compiled SQL
expression, cached across calls in a process-global, is far outside any core
idiom.

### 3. TF-IDF weights read from a user statistics table via SPI

With `smlar.type = tfidf`, the extension reads a **user catalog table** named by
the `smlar.stattable` string GUC (`GUC_IS_NAME`, `PGC_USERSET`,
`smlar_guc.c:77-88`). `initStatCache` runs `SELECT * FROM "<tbl>" ORDER BY 1`
through SPI (`smlar_stat.c:52-54`), expects a `(value, ndoc int4|int8)` table,
treats the **row with a NULL value as the total document count**
(`smlar_stat.c:95-104`), and precomputes `idf = log(totaldocs/df + oneAdd)` per
element (`smlar_stat.c:135`) `[verified-by-code]`. This is a **data-driven
operator** — the similarity depends on the contents of another table — squarely
the zson-dictionary / postgresql-unit-catalog-lexer pattern. TF-IDF is rejected
for composite (weighted) element types (`smlar_stat.c:76-77`).

### 4. Three per-backend caches, two of them outside the MemoryContext discipline

smlar keeps **three** distinct caches, and the divergence is *where* they live:

- **`cacheProcs`** — a process-global, `malloc`/`realloc`'d, binary-searched array
  of per-element-type `ProcTypeInfo` (btree cmp + hash fmgr info, typlen/byval)
  (`smlar.c:187-350`). It is raw `malloc`, never freed, and lives for the whole
  backend; composite-type `TupleDesc`s are copied into `TopMemoryContext`
  (`smlar.c:218`) `[verified-by-code]`. Bypassing palloc for backend-lifetime
  metadata is deliberate but non-idiomatic.
- **`ArrayCache`** — a 16-entry (`NENTRIES`, `smlar_cache.c:21`) **LRU** of
  deconstructed/detoasted arrays (their sorted `SimpleArray` and GiST `SmlSign`
  forms), hung off `fn_extra` and allocated in the function's `fn_mcxt`
  MemoryContext (`smlar_cache.c:166-172`). Move-to-front list + binary search on
  raw datum bytes (`smlar_cache.c:32-65,180-247`) `[verified-by-code]`. This one
  is idiomatic (per-call context, auto-freed).
- **`StatCache`** (TF-IDF stats) — allocation mode is a GUC switch.
  `cacheAlloc` uses **`malloc` when `smlar.persistent_cache` is on, else
  `MemoryContextAlloc`** (`smlar_stat.c:12-28`) `[verified-by-code]`. When
  persistent, the stats are stashed in a static `PersistentDocStat` pointer
  (`smlar_stat.c:10,141-143`) that **survives across transactions** in
  malloc'd, transaction-independent memory — explicitly the divergence axis of
  zson's malloc TTL cache and pg_jsonschema's two-level cache.
  **Invalidation is GUC-assign-hook-driven**: changing `smlar.stattable`
  (`SmlarTableAssign`, `smlar_guc.c:25-29`) or `smlar.idf_plus_one`
  (`SmlarLogAssign`, `smlar_guc.c:33-37`) calls `resetStatCache()`, which
  `free()`s the persistent cache (`smlar_stat.c:148-168`) `[verified-by-code]`.
  There is no invalidation on the *underlying table's contents changing* — the
  persistent cache is stale until a GUC is re-assigned or the backend exits
  `[inferred]`.

### 5. "Similarity above a threshold" mapped onto the boolean `consistent` contract

This is the AM-machinery heart (cf. `.claude/skills/access-method-apis/SKILL.md`,
`[[knowledge/idioms/gin-scan-and-consistent]]`).

- **GiST** stores a `gsmlsign` — a varlena **bit-signature / hashed-array** key
  (`SmlSign`, `smlar_gist.c:13-19`; `SIGLEN = 61 ints`, `SIGLENBIT` bits,
  `smlar_gist.c:24-26`), a Bloom-filter-style signature identical in spirit to
  pg_trgm/intarray. A key is one of three flavors: `ARRKEY` (exact sorted array
  of element hashes, used at leaves), `SIGNKEY` (lossy bit signature, used at
  inner nodes), or `ALLISTRUE` (`smlar_gist.c:41-47`). `compress` builds the
  exact hashed array, then collapses to a signature once it exceeds
  `TOAST_INDEX_TARGET` (`smlar_gist.c:381-395`); `penalty`/`picksplit` are
  Hamming-distance over the signatures (`hemdistsign`, `smlar_gist.c:597-656,
  722-920`) `[verified-by-code]`. The clever part is `consistent`
  (`smlar_gist.c:946-1255`): for a *leaf* it computes the real cosine/TF-IDF and
  compares to `GetSmlarLimit()`; for an *inner* node it computes an **upper bound**
  on achievable similarity (e.g. cosine `sqrt(count/nelems) >= limit`,
  `smlar_gist.c:1230`) so a subtree can be pruned only when *no* descendant can
  clear the threshold. It sets `*recheck = true` for the lossy similarity paths
  (`smlar_gist.c:966`) `[verified-by-code]`.
- **GIN** stores the plain element values (`STORAGE int4`, etc.). `extractValue`/
  `extractQuery` return the sorted-unique element Datums (`smlararrayextract`,
  `smlar_gin.c:14-49`), and signal "impossible" by returning `nentries = -1` for
  an empty query array under the overlap/similarity strategies
  (`smlar_gin.c:35-45`). `consistent` (`smlar_gin.c:62-152`) counts how many query
  keys the candidate matched (`cnt`, `smlar_gin.c:91-92`) and turns that into the
  boolean: overlap `cnt >= limit` with `recheck=false` (exact,
  `smlar_gin.c:82,139-142`), cosine `cnt/sqrt(nelems·cnt) >= limit` with recheck,
  and TF-IDF **only when `smlar.tf_method = const`** (else it errors,
  `smlar_gin.c:106-107`) `[verified-by-code]`. Mapping a real threshold onto GIN's
  ternary `check[]` array — using `cnt` as a lower bound on the indexed array's
  match count — is the non-obvious contract bridge.

### 6. A GiST STORAGE type with deliberately non-functional I/O

`gsmlsign` is a first-class type (`CREATE TYPE gsmlsign`, `smlar--1.0.sql:77-81`)
whose `gsmlsign_in`/`gsmlsign_out` both just `elog(ERROR, "not implemented")`
(`smlar_gist.c:62-78`) `[verified-by-code]`. The type exists only as an index
STORAGE key; it has no textual representation. Standard GiST-signature idiom, but
worth noting as a "type you can never SELECT" divergence.

## Notable design decisions (cited)

- **Internal sorted/de-duplicated array is `SimpleArray`, not `tsarr.c`.**
  `Array2SimpleArrayU` sorts with `qsort_arg` on the element type's btree cmp,
  de-duplicates in place, and accumulates per-element term frequency into `df[]`
  (`smlar.c:464-569`) `[verified-by-code]`. `tsarr.c` is *only* the
  `tsvector2textarray` converter (`tsarr.c:7-37`) — the task's premise that
  tsarr.c holds the sorted-array rep is not borne out `[verified-by-code]`.
- **Fixed collations.** Comparisons use `C_COLLATION_OID` (`FCall2` macro,
  `smlar.h:142`); hashing uses `DEFAULT_COLLATION_OID` (`smlar_gist.c:176`)
  `[verified-by-code]` — no per-column collation plumbing.
- **Composite/weighted element types.** `smlar(anyarray, anyarray, bool)`
  supports composite element type `(element, weight float4)` with an
  `useIntersect` denominator toggle (`arraysmlw`, `smlar.c:718-797`); the second
  field must be `float4` (`smlar.c:215-216`) `[verified-by-code]`. TF-IDF and
  GiST/GIN indexing are unsupported for composite types
  (`smlar_stat.c:76-77`, `smlar_gist.c:166-167`).
- **`%` uses a cheap pre-filter.** `arraysml_op` rejects on a cardinality bound
  (`Min(|a|,|b|)/sqrt(|a|·|b|) < limit`) before the exact intersection scan
  (`smlar.c:834-837`) `[verified-by-code]`.
- **Deprecated `set_smlar_limit`/`show_smlar_limit`** still ship, now thin
  wrappers over `set_config_option("smlar.threshold", …)` (`smlar_guc.c:201-228`);
  the README steers users to the GUC instead (`README:25-32`) `[from-README]`.
- **`relocatable = true`, no `superuser` gate** in the control file
  (`smlar.control:1-4`) despite the SPI-into-arbitrary-table stat feature
  `[verified-by-code]`.

## Links into corpus

- `[[knowledge/ideologies/pgvector]]` — the other "similarity search via index"
  extension. Direct contrast: pgvector adds a *new* distance-ordered path and its
  own ivfflat/hnsw AMs for dense-vector distance; smlar **reuses core GiST and
  GIN** for sparse *set* similarity, mapping a threshold onto the existing
  boolean `consistent` contract rather than an ordering operator.
- `[[knowledge/ideologies/pg_similarity]]` — sibling "many similarity functions
  as operators" extension; smlar's differentiator is index acceleration.
- `[[knowledge/ideologies/pg_trgm]]` — the same-author signature-GiST lineage
  smlar's `SmlSign` bit-signature descends from (need not exist).
- `[[knowledge/ideologies/zson]]`, `[[knowledge/ideologies/postgresql-unit]]`,
  `[[knowledge/ideologies/uuidv47]]` — GUC/catalog-dependent operator & I/O
  siblings: smlar's GUC-selected formula (uuidv47/unit) and stat-table-driven
  TF-IDF (zson dictionary) share the "output depends on external/session state,
  yet declared IMMUTABLE" tension.
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` / `FunctionCall*Coll`
  entry points and the `ProcTypeInfo` fmgr-info cache.
- `[[knowledge/idioms/gin-scan-and-consistent]]`,
  `[[knowledge/idioms/gin-tree-structure]]` — the GIN extract/consistent contract
  smlar bends to threshold semantics.
- `[[knowledge/idioms/gin-gist-opclass]]` — opclass/strategy/support-function
  registration (need not exist).
- `.claude/skills/access-method-apis/SKILL.md` — GiST/GIN opclass callbacks,
  strategy numbers, support-function slots.
- `.claude/skills/gucs-config/SKILL.md` — the six `DefineCustom*Variable` calls,
  `PGC_SUSET` vs `PGC_USERSET` choice, and the assign-hook invalidation trio.

## Sources

Fetched 2026-07-06, branch `master`. The README is a plain `README` (no
extension); `README.md` 404s.

- `https://raw.githubusercontent.com/jirutka/smlar/master/README` @ 2026-07-06 → HTTP 200 (116 lines, 4.4 KB) — function/GUC/opclass catalog `[from-README]`.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar.c` @ 2026-07-06 → HTTP 200 (1021 lines, 22.7 KB) — `PG_MODULE_MAGIC`, `ProcTypeInfo` malloc cache, `SimpleArray` sort/dedup/TF, the three `smlar()` forms, `%` op, the SPI formula evaluator.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar.h` @ 2026-07-06 → HTTP 200 (144 lines, 3.3 KB) — struct defs, strategy numbers, `ST_*`/`TF_*` enums, `FCall2` collation macro.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar_guc.c` @ 2026-07-06 → HTTP 200 (229 lines, 3.8 KB) — lazy `initSmlarGUC`, the six GUCs, assign hooks, deprecated setter/getter.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar_cache.c` @ 2026-07-06 → HTTP 200 (301 lines, 5.9 KB) — the 16-entry LRU `ArrayCache` in `fn_mcxt`.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar_stat.c` @ 2026-07-06 → HTTP 200 (206 lines, 5.1 KB) — SPI stat-table load, `cacheAlloc` malloc-vs-context switch, `PersistentDocStat` + `resetStatCache`.
- `https://raw.githubusercontent.com/jirutka/smlar/master/tsarr.c` @ 2026-07-06 → HTTP 200 (38 lines, 755 B) — `tsvector2textarray` only.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar_gist.c` @ 2026-07-06 → HTTP 200 (1255 lines, 26.9 KB) — `SmlSign` signature, compress/decompress/union/same/penalty/picksplit, the bound-based `consistent`, fake I/O.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar_gin.c` @ 2026-07-06 → HTTP 200 (152 lines, 3.5 KB) — extractValue/extractQuery, threshold→boolean `consistent`.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar.control` @ 2026-07-06 → HTTP 200 (5 lines, 137 B) — `relocatable = true`, `default_version = '1.0'`.
- `https://raw.githubusercontent.com/jirutka/smlar/master/smlar--1.0.sql` @ 2026-07-06 → HTTP 200 (714 lines, 25.3 KB) — `%` operator, `gsmlsign` type, GiST + GIN opclasses (strategy 1 `&&` / 2 `%`, support fns).
- `https://raw.githubusercontent.com/jirutka/smlar/master/Makefile` @ 2026-07-06 → HTTP 200 (26 lines, 694 B) — `MODULE_big`, OBJS, PGXS wiring.

All `file:line` cites into the `.c`/`.h`/`.sql` files are `[verified-by-code]`
against the fetched copies. The "`&&` is core PG's array-overlap operator reused"
and "persistent stat cache not invalidated on table-content change" claims are
`[inferred]` (absence of a `CREATE OPERATOR &&` and of a content-invalidation
path, respectively). Formula/threshold semantics narration is `[from-README]`.
