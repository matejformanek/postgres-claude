# jsquery — a whole json query language shipped as one extension TYPE, with its own grammar and its own GIN index-acceleration story

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgrespro/jsquery` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-07-17 (see Sources footer). jsquery is C-on-PGXS by
> Teodor Sigaev / Alexander Korotkov / Oleg Bartunov (Postgres Professional),
> the same people who drove core `jsonb` and later SQL/JSON `jsonpath` — so read
> this alongside the `.claude/skills/jsonpath-and-jsonb/SKILL.md` core note and
> the sibling `[[pgJQ]]` (a different "jq as a PG type" take). This is the
> **historical ancestor** of what core absorbed as jsonpath.

## Domain & purpose

jsquery is "a language to query jsonb data type" whose "primary goal is to
provide … a simple and effective way to search in nested objects and arrays,
more comparison operators with indexes support" (`README.md:11-17`)
`[from-README]`. It ships as a single SQL-visible base type — "released as
jsquery data type (similar to `tsquery`) and `@@` match operator for jsonb"
(`README.md:20-21`) `[from-README]` — so a whole predicate like
`name IS STRING AND points.#:(x IS NUMERIC AND y IS NUMERIC)` is one `jsquery`
value that a `jsonb @@ jsquery` operator evaluates against a document
(`README.md:199-207`) `[from-README]`.

The historical significance, and the reason to keep this note: jsquery (2014,
PostgreSQL 9.4-era) predates core SQL/JSON `jsonpath` (PG 12, 2019) and was
authored by the same team, which openly hoped "jsquery will be eventually a
part of PostgreSQL" (`README.md:17-18`) `[from-README]`. Core did not adopt
jsquery's surface verbatim, but it adopted its *architecture*: a JSON query
language compiled to a serialized on-disk type at input time, matched by a
`jsonb @@ <query>` boolean operator, with GIN acceleration. The specific
claim "core `@?`/`@@` jsonpath operators and `jsonb_path_query` descend
causally from jsquery" is `[inferred]` from shared authorship + the README's
stated intent; the jsquery repo does not itself narrate the lineage
`[unverified]`. What *is* verifiable in-repo is the shape core later echoed:
a grammar-backed query type (below) and a recheck-based GIN opclass pair
(below).

## How it hooks into PG

jsquery is a `MODULE_big` contrib module (`Makefile:3-5`) `[verified-by-code]`
linking six objects — `jsquery_gram`, `jsquery_scan` (embedded), `jsquery_io`,
`jsquery_op`, `jsquery_constr`, `jsquery_support`, `jsonb_gin_ops` — and it
declares `PG_MODULE_MAGIC` in `jsquery_io.c:24` `[verified-by-code]`. The
control file is unremarkable: `relocatable = true`, `default_version = '1.1'`,
comment "data type for jsonb inspection" (`jsquery.control:2-5`)
`[verified-by-code]`. Everything interesting is in what the SQL script builds
on top.

- **A new base TYPE with a full bison/flex front end.** `CREATE TYPE jsquery`
  is a two-step shell-type dance (`jsquery--1.1.sql:4`, then the full
  definition at `:16-21`) with `INPUT = jsquery_in`, `OUTPUT = jsquery_out`,
  `INTERNALLENGTH = -1` (varlena), `STORAGE = extended` `[verified-by-code]`.
  The C struct is a bare varlena header (`jsquery.h:24-27`)
  `[verified-by-code]`. `jsquery_in` runs `parsejsquery()` then flattens the
  parse tree into the varlena (`jsquery_io.c:150-171`) `[verified-by-code]`;
  `parsejsquery` drives a flex/bison parser (`jsquery_scan.l:390-402`,
  declared `jsquery.h:168`) `[verified-by-code]`. The grammar
  (`jsquery_gram.y`) and lexer (`jsquery_scan.l`, `#include`d into the
  generated parser at `jsquery_gram.y:383`) are a self-contained language
  front-end living *inside an extension*.
- **The `@@` match operator, defined both ways.** Two commutator operators
  `jsquery @@ jsonb` and `jsonb @@ jsquery`, procedures `jsquery_json_exec` /
  `json_jsquery_exec`, both `RESTRICT = contsel, JOIN = contjoinsel`
  (`jsquery--1.1.sql:33-49`) `[verified-by-code]`; the C entry points sit at
  `jsquery_op.c:781-803` and `:805-827` `[verified-by-code]`. A third operator
  `jsonb ~~ jsquery` returns the matching sub-values as `jsonb`
  (`json_jsquery_filter`, `jsquery--1.1.sql:51-60`, `jsquery_op.c:829-863`)
  `[verified-by-code]`.
- **btree + hash opclasses on the query type itself.** `jsquery_cmp` /
  `jsquery_hash` back `jsquery_ops` for `USING btree` and `USING hash`
  (`jsquery--1.1.sql:188-210`; C at `jsquery_op.c:975-1213`)
  `[verified-by-code]` — so `jsquery` values are themselves orderable and
  hashable like any first-class scalar.
- **Two GIN opclasses over `jsonb` with the full support-function set.**
  `jsonb_value_path_ops` and `jsonb_path_value_ops`, each registering
  `FUNCTION 1..6` (compare / extractValue / extractQuery / consistent /
  comparePartial / triConsistent), `OPERATOR 7 @>` and
  `OPERATOR 14 @@ (jsonb, jsquery)`, `STORAGE bytea`
  (`jsquery--1.1.sql:242-294`) `[verified-by-code]`; C in `jsonb_gin_ops.c`.
  See `.claude/skills/access-method-apis/SKILL.md` and
  `[[gin-scan-and-consistent]]` for what those six slots mean.

## Where it diverges from core idioms

### 1. A query language stored AS a first-class type value

This is the central bet, and the one core later ratified. jsquery is not a set
of functions taking a query string per call — it is a **type** whose stored
datum *is* the compiled query. `jsquery_in` parses text into a
`JsQueryParseItem` tree (`jsquery_io.c:156`) then `flattenJsQueryParseItem`
serializes that tree into the varlena with int32 position offsets between nodes
(`jsquery_io.c:26-148`) `[verified-by-code]`. The on-disk layout is
deliberately operand-first: the header comment explains that "the first/main
node is not an operation but left operand of expression. That allows to
implement cheap follow-path descending in jsonb structure and then execute
operator with right operand which is always a constant" (`jsquery.h:77-84`)
`[from-comment]`. Deserialization is a pointer-walk over that buffer
(`jsqInitByBuffer`, `jsquery_support.c:55-127`; `jsqGetNext`/`jsqGetArg`/
`jsqGetLeftArg`/`jsqGetRightArg`, `:130-196`) `[verified-by-code]`.

Draw the contrast carefully, because it is subtle rather than total: **core
jsonpath is also a type parsed to a serialized form at input time** (its own
`jsonpath_gram.y` / `jsonpath_scan.l`), so jsquery did not diverge from core
jsonpath — it *is the pattern core jsonpath adopted* `[inferred, see
jsonpath-and-jsonb skill]`. Where jsquery diverged was from *2014 core*, where
no such "query-language-as-a-user-type" existed outside `tsquery` (which the
README explicitly names as the model, `README.md:20-21`) `[from-README]`.
jsquery generalized the `tsquery` idea from full-text to arbitrary jsonb
predicates, and core generalized it again into jsonpath. Cross-ref
`[[catalog-conventions]]`, `.claude/skills/catalog-conventions/SKILL.md`.

### 2. Its own bison/flex grammar, parallel to core's scan.l/gram.y

Most extensions never ship a grammar; jsquery ships a complete one. The parser
is `%pure-parser` with `%name-prefix="jsquery_yy"` and a
`%parse-param {JsQueryParseItem **result}` (`jsquery_gram.y:219-223`)
`[verified-by-code]`, wired to palloc via `#define YYMALLOC palloc` /
`YYFREE pfree` so a parse error mid-input leaks nothing
(`jsquery_gram.y:32-33`) `[verified-by-code]`, and with flex's `fprintf`
redirected into `ereport(ERROR)` (`jsquery_gram.y:36-43`) `[verified-by-code]`
— the same defensive tricks core's own `scan.l` families use. Operator
precedence is declared `%left OR_P`, `%left AND_P`, `%right NOT_P`
(`jsquery_gram.y:247-251`) `[verified-by-code]`. The path grammar encodes the
placeholder vocabulary directly: `*` (any), `#` (any array elem), `%` (any
key), `$` (current/whole doc), `@#` (length), `#N` (Nth index), and the
"every" colon-forms `*:`/`#:`/`%:` (`jsquery_gram.y:338-363`, path rules
`:374-379`) `[verified-by-code]`; right-hand operators `= < > <= >= @> <@ &&
IN IS` live in `right_expr` (`jsquery_gram.y:299-316`) `[verified-by-code]`.

The lexer is a three-start-state flex scanner (`xQUOTED`, `xNONQUOTED`,
`xCOMMENT`) (`jsquery_scan.l:48-51`) `[verified-by-code]` with a
length-then-alpha sorted keyword table binary-searched by `checkSpecialVal`
(`jsquery_scan.l:234-288`) `[verified-by-code]`, and a `parseUnicode`
"adopted from `json_lex_string()` in `src/backend/utils/adt/json.c`"
(`jsquery_scan.l:417-422`) `[from-comment]` — an explicit copy of core's
scanner logic into the extension because core did not expose it. Cross-ref
`.claude/skills/jsonpath-and-jsonb/SKILL.md`.

### 3. In-query index HINTS embedded in comments — an imperative optimizer

The most idiosyncratic feature, and one core jsonpath did *not* adopt: the
query text can carry `/*-- index */` and `/*-- noindex */` comment hints that
override the GIN optimizer. The lexer's `xCOMMENT` state recognizes them and
returns a `HINT_P` token (`jsquery_scan.l:185-196`, `checkHint`
`:290-312`) `[verified-by-code]`; the hint is stored in the top 3 bits of the
node type byte (`JsQueryHint`, `jsquery.h:69-75`) `[verified-by-code]` — a
deliberate bit-stealing that the serializer asserts against
(`Assert((item->type & JSQ_HINT_MASK) == 0)`, `jsquery_io.c:34-35`)
`[verified-by-code]`. The README frames why this exists: "jsonb have no
statistics yet. That's why JsQuery optimizer has to do imperative decision"
and hints let a human force the choice (`README.md:308-344`) `[from-README]`.
This is a divergence from core's cost-based, statistics-driven planning
philosophy — jsquery hard-codes a selectivity ranking and lets comments
override it.

### 4. The GIN extract-query "which keys does this query need" machinery

This is the other half of what core absorbed, and the heaviest code in the
extension. A GIN `extractQuery` support function must turn a query into the set
of index keys to probe. jsquery does this through a reusable pipeline in
`jsquery_extract.c`: `extractJsQuery` runs `recursiveExtract` →
`flatternTree` → `simplifyRecursive` → `setSelectivityClass` → `makeEntries`
(`jsquery_extract.c:815-832`) `[verified-by-code]`.

- **`recursiveExtract`** lowers the query tree into an `ExtractedNode` tree
  (`jsquery.h:211-239`) of leaf conditions (`eExactValue`, `eInequality`,
  `eIs`, `eAny`, `eEmptyArray`) under `eAnd`/`eOr`, pushing NOT down by
  flipping a `not` flag and returning NULL for un-indexable branches
  (`jsquery_extract.c:45-287`) `[verified-by-code]`. Each leaf carries a
  `PathItem` chain (`jsquery.h:181-189`) reconstructed from the query path.
- **`flatternTree`** collapses nested binary AND/OR into n-ary nodes
  (`jsquery_extract.c:354-379`) `[verified-by-code]`.
- **`simplifyRecursive`** sorts an AND's children by path (`compareNodes`,
  `:432-459`) and merges multiple conditions on the same field into one —
  e.g. two inequalities become a single range (`processGroup`,
  `jsquery_extract.c:504-664`) `[verified-by-code]`.
- **`setSelectivityClass`** assigns each leaf a `SelectivityClass` ordered
  `sEqual < sRange < sInequal < sIs < sAny` (`jsquery.h:202-209`,
  `getScalarSelectivityClass` `jsquery_extract.c:669-691`)
  `[verified-by-code]`, propagating Min across AND and Max across OR
  (`:797-800`) `[verified-by-code]`.
- **`makeEntries`** is where the payoff lands: under an AND it **skips a child
  whose selectivity class is worse than the node's, unless forced**
  (`child->sClass > node->sClass && node->type == eAnd && !child->forceIndex`,
  `jsquery_extract.c:708-712`) `[verified-by-code]`, and honors the
  `jsqNoIndex` hint by dropping the entry entirely (`:742-743`)
  `[verified-by-code]`. So `x = 1 AND y > 0` probes the index only for
  `x = 1`, the more selective term (`README.md:320-327`) `[from-README]`.

The whole pipeline is parameterized by two callbacks — `MakeEntryHandler` and
`CheckEntryHandler` (`jsquery.h:241-249`) `[verified-by-code]` — so the same
optimizer serves both GIN opclasses, each supplying its own key-construction
handler. At scan time the extracted tree is re-evaluated over GIN's `check[]`
bitmap by `execRecursive` (boolean) and `execRecursiveTristate` (ternary)
(`jsquery_extract.c:837-890`) `[verified-by-code]`. This extract-then-recheck
factoring is exactly the shape core's jsonpath GIN support and the sibling
`[[gin-scan-and-consistent]]` idiom describe.

### 5. Two GIN entry encodings — path-hash-value vs value-bloom-path

Core `jsonb_ops` / `jsonb_path_ops` offer two encodings; jsquery independently
invented its own two, tuned for *query* predicates rather than containment.
Both decompose a document into `(path, value)` entries, "each array element
marked with the same `#`" since jsquery has no per-index array search
(`README.md:227-244`) `[from-README]`. They differ in which half is the
high-order sort key:

- **`jsonb_path_value_ops`** keys on `(hash(full path); value)`
  (`README.md:251-262`) `[from-README]`; the extractor rolls a path hash by
  XOR-and-rotate down the `PathItem` chain (`get_query_path_hash`,
  `jsonb_gin_ops.c:932-965`; document side `gin_extract_jsonb_path_value_internal`
  `:1082-1171`) `[verified-by-code]`. Because the path is the high bits, a
  query must know the *full* path — so a `%` or `*` wildcard makes the path
  un-hashable and the handler returns `-1`, dropping the entry
  (`get_query_path_hash` returns false on `iAny`/`iAnyKey`,
  `:946-949`; `make_path_value_entry_handler` `:977-1000`)
  `[verified-by-code]`.
- **`jsonb_value_path_ops`** keys on `(value; bloom(path items))`
  (`README.md:264-277`) `[from-README]`; each path item contributes
  `BLOOM_BITS = 2` bits (`jsonb_gin_ops.c:56`, `get_bloom_value` `:146-171`,
  `get_path_bloom` `:173-188`) `[verified-by-code]`. Because the value is the
  high bits, wildcards *are* tolerated — the bloom just becomes lossy and
  forces partial-match filtering (`get_query_path_bloom` sets `*lossy`,
  `:190-214`; the consistency-time bloom test `(key->hash & extra->hash) !=
  extra->hash`, `:614-624`) `[verified-by-code]`.

The shared `GINKey` is a varlena `{ hash, type, data[] }`
(`jsonb_gin_ops.c:34-42`) `[verified-by-code]` where strings are stored as a
32-bit hash (`make_gin_key`, `:295-303`) `[verified-by-code]` — lossy by
construction, which is why the opclass always rechecks (next section).
`make_gin_query_key` maps each `ExtractedNode` to a probe key and flags
partial-match for inequalities, `IS`, and existence (`eAny`)
(`jsonb_gin_ops.c:367-441`) `[verified-by-code]`; range scans ride
`compare_partial` (`:562-643`, `:1022-1080`) `[verified-by-code]`.

### 6. The GIN opclass is a pure filter — always lossy, always recheck

Every consistent path sets `*recheck = true` unconditionally
(`jsonb_gin_ops.c:837`, `:1262`) `[verified-by-code]`, and the tri-state
consistent functions downgrade a definite `GIN_TRUE` to `GIN_MAYBE` before
returning under the `@@` strategy (`if (res == GIN_TRUE) res = GIN_MAYBE`,
`:919-921`, `:1343-1345`) `[verified-by-code]`. The design authority is the
executor: the index narrows candidates, then `recursiveExecute` in
`jsquery_op.c` re-runs the *full* predicate on each heap tuple. This is a
deliberate division of labor — the GIN side never claims a definite match
because its keys are hash/bloom-lossy — and it mirrors how core's own
`jsonb_path_ops` treats its hashed keys (the comment at `:902-908` /
`:1326-1332` is lifted almost verbatim from core `jsonb_gin_ops.c`)
`[from-comment]`. Cross-ref `[[gin-scan-and-consistent]]`,
`[[gin-tree-structure]]`.

### 7. Memory handling in the recursive match executor

`recursiveExecute` (`jsquery_op.c:451-779`) is a single ~330-line recursive
switch guarded by `check_stack_depth()` at entry (`:458`) `[verified-by-code]`,
and every recursive helper — `recursiveAny`, `recursiveAll`, `compareJsQuery`,
`hashJsQuery` — repeats that guard (`:119`, `:155`, `:872`, `:1120`)
`[verified-by-code]`, because a hostile deeply-nested `jsquery` or `jsonb`
could otherwise blow the C stack. The executor carries a `ResultAccum` only for
the `~~` filter path, and uses a `missAppend` flag to suppress result
collection under NOT/filter contexts while still evaluating for truth
(`jsquery_op.c:502-514`, `:753-772`) `[verified-by-code]` — a manual
save/restore of accumulator state rather than a fresh memory context per
sub-evaluation. Values pulled out of the container (`findJsonbValueFromContainer`)
are `pfree`d immediately after use (`:533`) `[verified-by-code]`. Cross-ref
`[[knowledge/idioms/memory-contexts]]`, `.claude/skills/jsonpath-and-jsonb/SKILL.md`.

## Notable design decisions (cited)

- **Every SQL function is `IMMUTABLE STRICT`** (`jsquery--1.1.sql` throughout,
  e.g. `:6-14`, `:23-31`) `[verified-by-code]`, which is the whole reason the
  `@@` operator "is immutable and can be used in CHECK constraint"
  (`README.md:195-197`) `[from-README]` — the marquee use case is document
  schema validation via a table `CHECK (data @@ '…'::jsquery)`
  (`README.md:199-207`) `[from-README]`. This is the same
  validation-via-CHECK niche the sibling `[[pg_jsonschema]]` occupies, reached
  by a completely different mechanism (a query DSL vs a JSON Schema validator).
- **Legacy CRC-32 for `pg_upgrade` compatibility.** `jsquery_hash` deliberately
  pins `INIT_LEGACY_CRC32` / `COMP_LEGACY_CRC32` "in order to be
  pg_upgradeable" across the 9.5 CRC change (`jsquery_op.c:21-29`)
  `[from-comment]` — an on-disk-stability discipline core itself practices.
- **Query-algebra operators on the type.** `&` (and), `|` (or), `!` (not)
  build new `jsquery` values from existing ones by splicing serialized buffers
  (`jsquery--1.1.sql:62-94`; `joinJsQuery` / `jsquery_not` in
  `jsquery_constr.c:153-261`) `[verified-by-code]` — the query type is closed
  under composition, like `tsquery`.
- **Selectivity classes are hard-coded, not measured.** The ranking
  Equality > Range > Inequality > Is > Any (`README.md:311-318`)
  `[from-README]` is baked into `getScalarSelectivityClass`
  (`jsquery_extract.c:669-691`) `[verified-by-code]`; there is no
  `pg_statistic` input, which is precisely why the comment-hint escape hatch
  exists (§3).
- **A debug window into the optimizer, because opclasses can't touch EXPLAIN.**
  `gin_debug_query_path_value` / `gin_debug_query_value_path`
  (`jsquery--1.1.sql:296-304`; `jsonb_gin_ops.c:743-754`, `:1182-1194`)
  print the extracted entry tree as text, since "opclasses aren't allowed to
  put any custom output in an EXPLAIN" (`README.md:281-285`) `[from-README]` —
  an extension working around a genuine core observability gap.
- **`extractQuery` stashes the extracted tree in per-key `extra_data`.** The
  root `ExtractedNode*` is written into every key's `KeyExtra` so `consistent`
  can re-run `execRecursive` over it (`jsonb_gin_ops.c:803-804`, `:1228-1229`,
  consumed at `:856`, `:1280`) `[verified-by-code]` — the GIN `extra_data`
  channel used as a query-plan carry-along.

## Links into corpus

- `[[pg_jsonschema]]` — the other "validate a jsonb column via CHECK" extension
  in the corpus; jsquery reaches the same niche with a query DSL + `@@` instead
  of a JSON Schema validator, and with a full GIN acceleration story
  pg_jsonschema has no equivalent of.
- `[[pgJQ]]` — a sibling "query language for json as a PG type" (jq), useful as
  a design-space neighbor.
- `[[rum]]` — same authors' successor index AM; jsquery's GIN
  extract/consistent factoring is the direct precursor idiom.
- `[[gin-scan-and-consistent]]`, `[[gin-tree-structure]]` — the extractQuery /
  consistent / triConsistent contract jsquery implements twice, and the lossy-
  key + always-recheck discipline of §6.
- `[[catalog-conventions]]` — a base type + operator + opclass registration
  done entirely from an extension SQL script (`jsquery--1.1.sql`).
- `[[knowledge/idioms/memory-contexts]]` — the `check_stack_depth` /
  palloc-parser / immediate-pfree memory discipline of §2 and §7.
- `.claude/skills/jsonpath-and-jsonb/SKILL.md` — core SQL/JSON jsonpath, the
  descendant architecture; read it against §1 for the lineage contrast.
- `.claude/skills/access-method-apis/SKILL.md` — GIN opclass FUNCTION 1..6
  slots and `CREATE OPERATOR CLASS` mechanics.
- `.claude/skills/catalog-conventions/SKILL.md` — type / operator / opclass
  catalog registration.

## Anthropology takeaway

jsquery is a self-contained programming language — grammar, lexer, serializer,
optimizer, bytecode-ish on-disk form, and executor — smuggled into PostgreSQL
as *one user-defined type plus one operator*. That packaging is the thesis. Core
in 2014 had no notion of a compiled JSON query outside `tsquery`; jsquery took
the `tsquery`-as-a-type idea and stretched it to arbitrary nested-jsonb
predicates, and then core stretched it once more into SQL/JSON `jsonpath`. Two
things make jsquery worth keeping as an ancestor exhibit rather than just a
retired extension. First, the **query-as-a-type** decision (§1): the stored
datum is the compiled query in operand-first order for cheap path descent
(`jsquery.h:77-84`), a layout choice core jsonpath reprised. Second, the **GIN
extract-query optimizer** (§4-§6): a reusable extract → flatten → simplify →
classify → make-entries pipeline (`jsquery_extract.c:815-832`) that prunes
low-selectivity AND terms (`:708-712`), honors human `/*-- index */` hints in
the absence of statistics (§3), materializes two different lossy entry
encodings (§5), and always defers the final verdict to a full recheck in the
executor (§6). The comment-hint optimizer is the one part core deliberately
*didn't* inherit — a reminder that jsquery predates jsonb statistics and had to
legislate selectivity by hand. Where `[[pg_jsonschema]]` grows a private cache
core refuses to provide, jsquery grows a private *query planner* core hadn't yet
built — and this time core did, eventually, build its own.

## Sources

Fetched 2026-07-17 (branch `master`, `raw.githubusercontent.com/postgrespro/jsquery/master/`):

- `README.md` → HTTP 200 (356 lines; deep-read — language spec, GIN opclass
  design, optimizer + hints, CHECK-constraint use case, authorship). NB: an
  initial fetch returned an unrelated PoWA README (a transient proxy-cache
  glitch); the re-fetch returned the correct jsquery README, which all
  `README.md:` cites reference.
- `jsquery.h` → HTTP 200 (261 lines; deep-read — `JsQuery` varlena,
  `JsQueryItemType`/`JsQueryHint`, `JsQueryItem`/`JsQueryParseItem`,
  `ExtractedNode`/`PathItem`/`SelectivityClass`, handler typedefs).
- `jsquery_gram.y` → HTTP 200 (383 lines; deep-read — grammar, palloc/ereport
  wiring, precedence, path/right_expr rules, HINT_P).
- `jsquery_scan.l` → HTTP 200 (509 lines; deep-read — start states, keyword
  table, `checkHint`, `parseUnicode`, `parsejsquery`).
- `jsquery_io.c` → HTTP 200 (412 lines; deep-read — `flattenJsQueryParseItem`,
  `jsquery_in`/`jsquery_out`).
- `jsquery_support.c` → HTTP 200 (267 lines; deep-read — `jsqInitByBuffer`
  deserialization, `jsqGet*`/iterate accessors, `alignStringInfoInt`).
- `jsquery_op.c` → HTTP 200 (1214 lines; deep-read — `recursiveExecute`,
  `@@`/`~~` entry points, `compareJsQuery`/`hashJsQuery`, legacy CRC).
- `jsquery_constr.c` → HTTP 200 (262 lines; deep-read — `copyJsQuery`,
  `joinJsQuery`, `jsquery_not` for `& | !`).
- `jsquery_extract.c` → HTTP 200 (1066 lines; deep-read — the extractQuery
  optimizer pipeline, selectivity classes, `execRecursive[Tristate]`, debug).
- `jsonb_gin_ops.c` → HTTP 200 (1355 lines; deep-read — `GINKey`, the two
  opclass extract/compare/consistent/triconsistent/comparePartial functions,
  bloom + path-hash encodings, debug functions).
- `jsquery--1.1.sql` → HTTP 200 (304 lines; deep-read — type, operators, btree
  / hash / two GIN opclasses).
- `jsquery.control` → HTTP 200 (6 lines; full).
- `Makefile` → HTTP 200 (45 lines; full — object list, UTF8 regress).
- `jsquery--1.0--1.1.sql` → HTTP 200 (11 lines; skimmed — upgrade script).

404 / gaps: `jsquery_gin.c` (probe) → HTTP 404 — the GIN code is
`jsonb_gin_ops.c`, fetched above. Plain `README` (no `.md`) → HTTP 404. The
causal jsquery→jsonpath lineage is `[inferred]`/`[unverified]` — asserted from
shared authorship (`README.md:23-28`) and the stated intent
(`README.md:17-18`), not narrated by the repo. The regression `.sql`/`.out`
expected files and `jsquery.h`'s numeric-input version shims were not audited
beyond what the fetched sources show.
