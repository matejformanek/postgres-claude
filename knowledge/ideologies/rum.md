# rum — a GIN fork that hangs per-entry attribute data off every posting-list item, so the index itself can rank `tsvector <=> tsquery` and order by an attached column without ever touching the heap

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgrespro/rum` @ branch `master`. All `file:line` cites below point
> into THAT repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-07-16 (see Sources footer).
> Read alongside the sibling index-AM / FTS ideology docs: [[pg_textsearch]],
> [[zombodb]], [[pgroonga]], [[pgvector]], [[pgvectorscale]].

## Domain & purpose

RUM is a pluggable index access method — registered via `CREATE ACCESS METHOD
rum TYPE INDEX HANDLER rumhandler` — that is a near-line-for-line fork of core
GIN with one structural change: it stores **additional per-entry information
inside the posting lists and posting trees**, alongside every heap TID.
`[from-README]` `README.md:11-18`; `[from-README]` (META abstract) `META.json:4`:
"Unlike GIN, RUM stores additional information in posting lists/trees besides
item pointers. For example, those additional information might be lexemes
positions or timestamps." That single change is what lets RUM answer two query
shapes that core GIN fundamentally cannot serve from the index alone: (1)
relevance-ranked full-text search — `ORDER BY tsvector <=> tsquery` — because the
lexeme positions needed by the ranking function are co-located with each posting
`[from-README]` `README.md:21-25`; and (2) "order by an attached column" scans
such as `ORDER BY timestamp_col <=> '2016-05-16'` returned in distance order
straight out of the index `[from-README]` `README.md:26-27,199-224`. Core GIN,
by contrast, throws away positional information and can only return an unordered
bitmap that then needs a heap scan (for ranking) or a sort node (for ordering).
The cost of RUM's bargain is explicit in the README: slower build and insert,
and larger indexes, because every posting now carries a payload and RUM writes
via generic WAL `[from-README]` `README.md:35-37`.

For an anthropologist, RUM is the corpus's clearest case of *forking a core AM
wholesale to relax one design constraint*. GIN's ideology is "an inverted index
maps a key to a compressed set of TIDs, nothing more." RUM's counter-ideology is
"the TID set is the wrong granularity to stop at — attach a Datum to each TID and
the inverted index can also do ordering and ranking." Everything downstream
(the distance `<=>` operators, the `orderingFn`/`outerOrderingFn` support
procedures, the alternative on-disk item layout, the tuplesort-backed
`amgettuple`) follows from that one commitment.

## How it hooks into PG

**The handler.** `rumhandler` is the `PG_FUNCTION_INFO_V1` entry point
(`src/rumutil.c:37`) that fills and returns an `IndexAmRoutine`
(`src/rumutil.c:111-158`) `[verified-by-code]`. The AM-capability flags that
matter for RUM's identity:

- `amcanorderbyop = true` (`src/rumutil.c:119`) — **this is the flag GIN does not
  set.** It tells the planner RUM can satisfy `ORDER BY column <=> const`
  directly, which is the whole point of the extension `[verified-by-code]`.
- `amcanorder = false`, `amcanbackward = false` (`src/rumutil.c:118,120`) — no
  btree-style ordered/backward scan; ordering is only via the distance operator
  `[verified-by-code]`.
- `amcanmulticol = true`, `amoptionalkey = true`, `amstorage = true`,
  `ampredlocks = true` (`src/rumutil.c:122-128`) — multi-column, GIN-like storage
  type divergence from key type, and SSI predicate locking `[verified-by-code]`.
- `amcanparallel = false` (`src/rumutil.c:130`) — no parallel index scan
  `[verified-by-code]`.
- `amsupport = RUMNProcs` where `RUMNProcs = 10` (`src/rumutil.c:117`,
  `src/rum.h:855`) — RUM defines **10** support procedures vs GIN's smaller set
  `[verified-by-code]`.

**The IndexAmRoutine callbacks filled** (`src/rumutil.c:134-155`)
`[verified-by-code]`:

| slot | RUM function | notes |
| --- | --- | --- |
| `ambuild` | `rumbuild` | `src/rumutil.c:134` (decl `src/rum.h:448`) |
| `ambuildempty` | `rumbuildempty` | `src/rumutil.c:135` |
| `aminsert` | `ruminsert` | `src/rumutil.c:136` (decl `src/rum.h:451`) |
| `ambulkdelete` | `rumbulkdelete` | `src/rumutil.c:137` |
| `amvacuumcleanup` | `rumvacuumcleanup` | `src/rumutil.c:138` |
| `amcanreturn` | `NULL` | no index-only scan `src/rumutil.c:139` |
| `amcostestimate` | `gincostestimate` | **reuses core GIN's cost estimator verbatim** `src/rumutil.c:140` |
| `amoptions` | `rumoptions` | `src/rumutil.c:141` |
| `amproperty` | `rumproperty` | `src/rumutil.c:142` |
| `amvalidate` | `rumvalidate` | `src/rumutil.c:143` |
| `ambeginscan` | `rumbeginscan` | `src/rumutil.c:144` |
| `amrescan` | `rumrescan` | `src/rumutil.c:145` |
| `amgettuple` | `rumgettuple` | `src/rumutil.c:146` (decl `src/rum.h:796`) |
| `amgetbitmap` | `rumgetbitmap` | `src/rumutil.c:147` (decl `src/rum.h:795`) |
| `amendscan` | `rumendscan` | `src/rumutil.c:148` |
| `ammarkpos`/`amrestrpos` | `NULL` | `src/rumutil.c:149-150` |
| parallel-scan slots | `NULL` | `src/rumutil.c:152-154` |

That RUM borrows `gincostestimate` outright (`src/rumutil.c:140`) is a telling
anthropological detail: the extension is confident enough in its GIN lineage to
let the planner cost it *as if it were GIN*, even though its scans behave
differently `[verified-by-code]`.

**Support-procedure numbers.** RUM extends GIN's procedure set. It reuses GIN's
`GIN_COMPARE_PROC`, `GIN_EXTRACTVALUE_PROC`, `GIN_EXTRACTQUERY_PROC`,
`GIN_CONSISTENT_PROC`, `GIN_COMPARE_PARTIAL_PROC` (looked up in
`src/rumutil.c:320-366`) and adds five of its own (`src/rum.h:850-855`)
`[verified-by-code]`:

```
#define RUM_CONFIG_PROC             6   /* fills RumConfig: addInfo type + strategy map */
#define RUM_PRE_CONSISTENT_PROC     7   /* fast-scan pre-filter */
#define RUM_ORDERING_PROC           8   /* distance for ORDER BY key <=> query */
#define RUM_OUTER_ORDERING_PROC     9   /* distance for the attached/addon column */
#define RUM_ADDINFO_JOIN            10  /* merge two addInfo payloads (e.g. position lists) */
#define RUMNProcs                   10
```

**Strategy numbers for the distance operators** (`src/rum.h:29-32`)
`[verified-by-code]`:

```
#define RUM_DISTANCE        20   /* <=>  */
#define RUM_LEFT_DISTANCE   21   /* <=|  */
#define RUM_RIGHT_DISTANCE  22   /* |=>  */
```

These back the operators the README advertises: `tsvector <=> tsquery → float4`,
`timestamp <=> timestamp → float8`, plus the one-sided `<=|` / `|=>` for
range-limited distance `[from-README]` `README.md:93-101`.

**Opclasses shipped** (enumerated in `README.md:107-309`) `[from-README]`:
`rum_tsvector_ops` (lexemes + positions, supports `<=>` and prefix search),
`rum_tsvector_hash_ops` (hashed lexemes, `<=>` but no prefix search),
`rum_tsvector_addon_ops` / `rum_tsvector_hash_addon_ops` (lexemes + an arbitrary
attached scalar column), `rum_tsquery_ops` (stores query-tree branches as
addInfo — an inverted index over *queries*), `rum_anyarray_ops` (array elements +
array length, supports `&&`/`@>`/`<@`/`=`/`%` and `<=>` similarity ordering),
`rum_anyarray_addon_ops`, and the scalar `rum_TYPE_ops` family for int2/int4/
int8/float4/float8/money/oid/timestamp/timestamptz/date/etc.
`[from-README]` `README.md:172-183,265-309`.

**GUCs and reloptions.** `_PG_init` (`src/rumutil.c:53-105`) registers three
GUCs — `rum_fuzzy_search_limit`, `rum.array_similarity_threshold`,
`rum.array_similarity_function` — and three reloptions: `attach`, `to`, and
`order_by_attach` (`src/rumutil.c:82-104`). The `attach`/`to`/`order_by_attach`
reloptions are how a user wires up an addon-ordering index, e.g.
`WITH (attach = 'd', to = 't')` in `README.md:199-201` `[verified-by-code]`.

## Where it diverges from core idioms

### 1. The posting item carries a Datum — `RumItem` vs GIN's bare ItemPointer

Core GIN's posting lists are compressed streams of `ItemPointerData` and nothing
else. RUM replaces that unit with `RumItem` (`src/rum.h:171-176`)
`[verified-by-code]`:

```c
typedef struct RumItem {
    ItemPointerData iptr;
    bool            addInfoIsNull;
    Datum           addInfo;
} RumItem;
```

Every place GIN would move a TID, RUM moves a TID *plus* its `addInfo` Datum. The
non-leaf posting-tree node `RumPostingItem` (`src/rum.h:188-193`) embeds a
`RumItem` too, and the data-page right-bound is a `RumItem`
(`RumDataPageGetRightBound`, `src/rum.h:279`) `[verified-by-code]`. This is the
single structural change from which everything else follows.

### 2. Two on-disk item encodings, selected by `useAlternativeOrder`

RUM leaf data pages store TIDs varbyte-delta-compressed. The reader
`rumDataPageLeafReadItemPointer` (`src/rum.h:913-966`) decodes a block-number
increment then an offset, stealing one bit (`SEVENTHBIT`, `src/rum.h:904`) of the
offset word to carry `addInfoIsNull` `[verified-by-code]`. But when the index is
built for **ordering by the attached column** (`order_by_attach`), RUM switches
to `useAlternativeOrder`: the TID is stored raw (`memcpy` of `ItemPointerData`)
and the null flag is packed into the high bit of `ip_posid` via
`ALT_ADD_INFO_NULL_FLAG = 0x8000` (`src/rum.h:337`,
`rumDataPageLeafRead:983-1000`, and `rumDataPageLeafReadPointer:1069-1083`)
`[verified-by-code]`. The reason: alternative order sorts postings by
`(addInfo, tid)` rather than by `tid`, so the delta compression on TIDs no longer
holds `[inferred-from-code]` (`src/rum.h:977-1056`). `rumDataPageLeafRead` then
decodes the `addInfo` Datum inline according to `rumstate->addAttrs[attnum-1]`
attribute metadata — byval fast-path for 1/2/4/8-byte types, `att_align_pointer`
+ `fetch_att` + optional `datumCopy` for pass-by-reference
(`src/rum.h:1004-1054`) `[verified-by-code]`.

### 3. addInfo as raw Datum is "bogus" for varlena — a self-documented limitation

The header carries a candid `FIXME` (`src/rum.h:269-278`): `RumItem` and
`RumPostingItem` store `addInfo` as a raw `Datum`, which is fine for
pass-by-value but wrong for pass-by-reference (variable-length) data, because
posting-tree pages have a **fixed-length right bound and fixed-length non-leaf
items**. Consequently `initRumState` refuses to build an ordering index over a
pass-by-reference addInfo column: `elog(ERROR, "doesn't support order index over
pass-by-reference column")` (`src/rumutil.c:257-258`) `[verified-by-code]`. The
README restates this as a user-facing warning (`README.md:226`) and the
inspection functions surface it literally as the string `"varlena types in
posting tree is not supported"` (`README.md:411-419`) `[from-README]`. This is a
real architectural debt the fork took on to keep posting-tree internal nodes
fixed-size.

### 4. Ordering scans: `amgettuple` runs the scan into a tuplesort, then drains it

Core GIN has no `amcanorderbyop` and no ordered `amgettuple` result. RUM's
`rumgettuple` (`src/rumget.c:2561-2659`) does something GIN never does: on the
first call, when the scan requires sorting (`so->naturalOrder ==
NoMovementScanDirection`), it opens a RUM tuplesort
(`rum_tuplesort_begin_rum`, `src/rumget.c:2594-2596`), drives the *entire* scan
via `scanGetItem` pushing every match through `insertScanItem`
(`src/rumget.c:2598-2601`), calls `rum_tuplesort_performsort`
(`src/rumget.c:2602`), and thereafter returns rows in distance order by draining
the sort with `rum_tuplesort_getrum` (`src/rumget.c:2626-2657`)
`[verified-by-code]`. `insertScanItem` (`src/rumget.c:2450-2533`) computes one
`float8` ordering value per `orderBy` key with `keyGetOrdering` and stores them in
the sort tuple's `data[]`, later fed back to the executor as
`scan->xs_orderbyvals[]` (`src/rumget.c:2644-2652`) `[verified-by-code]`.

`keyGetOrdering` (`src/rumget.c:2379-2448`) is where the distance actually gets
computed. It has three modes `[verified-by-code]`:
- `useAddToColumn` → calls `outerOrderingFn[attrnAttachColumn-1]` with the
  attached column's value (`src/rumget.c:2386-2400`);
- `useCurKey` → calls `orderingFn[attnum-1]` on the current key
  (`src/rumget.c:2401-2415`);
- otherwise → gathers each entry's `curItem.addInfo` into `key->addInfo[]` and
  calls the 10-argument `orderingFn` via `FunctionCall10Coll`
  (`src/rumget.c:2417-2447`). The addInfo payloads are the ranking inputs — this
  is the mechanism by which stored positions feed the FTS rank.

### 5. Distance = reciprocal of relevance score

For FTS ranking, `rum_tsquery_distance` (`src/rum_ts_utils.c:2049-2069`) computes
a score from the query, the per-lexeme `addInfo` position payloads, and the
`check[]` array, then returns `1.0 / res` (or `+inf` when the score is 0) so that
**higher relevance sorts first under ascending `<=>`**
(`src/rum_ts_utils.c:2065-2068`) `[verified-by-code]`. `rum_ts_distance_tt` /
`rum_ts_distance_ttf` do the same reciprocal trick for the direct
`tsvector <=> tsquery` operator (`src/rum_ts_utils.c:2074-2110`)
`[verified-by-code]`.

### 6. tsvector positions become the addInfo payload at extract time

The bridge from FTS to RUM's payload slot lives in the extract path.
`extract_tsvector_internal` (`src/rum_ts_utils.c:1143-1195`) walks each
`WordEntry`; when the lexeme `haspos`, it `compress_pos`-es the
`WordEntryPosVector` into a `bytea` and hands it back as `(*addInfo)[i]`,
otherwise it marks `(*addInfoIsNull)[i] = true` (`src/rum_ts_utils.c:1168-1189`)
`[verified-by-code]`. `rum_tsvector_config` (`src/rum_ts_utils.c:2256-2264`) is
what tells RUM the addInfo type is `BYTEAOID` (`src/rum_ts_utils.c:2260`)
`[verified-by-code]`. At read time `checkcondition_rum`
(`src/rum_ts_utils.c:258-304`) decompresses those positions back out of `addInfo`
for phrase-search — and notably short-circuits with `TS_MAYBE` when positions are
absent because a timestamp is stored in addInfo instead
(`src/rum_ts_utils.c:271-292`) `[verified-by-code]`. `RUM_ADDINFO_JOIN`
(`rum_ts_join_pos`, `src/rum_ts_utils.c:2266-2289`) merges two position lists,
supporting the "attach column to a tsvector" composition
`[verified-by-code]`.

### 7. Multi-column scans with mixed orderings need a private TID bitmap

Because different scan keys can emit their matches in different orders (one
ordered by TID, another ordered by attached addInfo), RUM detects this with
`isScanWithAltOrderKeys` (`src/rumget.c:770-791`) and, when true, allocates a
private `RumTIDBitmap` in `startScan` (`so->scanWithAltOrderKeys = true;
so->tbm = rum_tbm_create(...)`, `src/rumget.c:845-849`) `[verified-by-code]`.
TID-ordered keys are collected into that bitmap via `collectAllCurItemsToBitmap`
(`src/rumget.c:1504-1555`) and intersected against the addInfo-ordered keys under
AND (`src/rumget.c:1566-1570`) `[verified-by-code]`. This whole apparatus — and
the ships-its-own `rumtidbitmap.c`/`RumTIDBitmap`, a vendored copy of core's
`tidbitmap.c` (`README.md:50`) — exists only because RUM streams results in
attribute order, a problem core GIN never has `[inferred-from-code]`.

### 8. WAL is generic; no custom rmgr

RUM never registers a custom WAL resource manager. Every page mutation goes
through PostgreSQL's **generic WAL** API: `GenericXLogStart` /
`GenericXLogRegisterBuffer` / `GenericXLogFinish` inside
`START_CRIT_SECTION()`/`END_CRIT_SECTION()` blocks in `rumInsertValue`
(`src/rumbtree.c:407-419`, `453-505`, `540-588`) `[verified-by-code]`. This is
exactly the trade-off the README flags: generic WAL is what makes RUM portable as
an out-of-tree extension but also what makes inserts heavier, and the "Todo" list
literally asks for core changes to teach generic WAL to record shifts
(`README.md:36-37,444`) `[from-README]`.

### 9. Locking / SSI mirror GIN

Descent uses coupling: `rumFindLeafPage` starts with `RUM_SHARE`, drops and
re-takes as `RUM_EXCLUSIVE` when it must move right/split
(`src/rumbtree.c:29-49`, `134-174`) `[verified-by-code]`. Page splits register
SSI predicate-lock transfers with `PredicateLockPageSplit`
(`src/rumbtree.c:489-493`, `560`) — consistent with `ampredlocks = true`
`[verified-by-code]`. The lock-mode macros are thin aliases over core
(`RUM_SHARE`/`RUM_EXCLUSIVE`/`RUM_UNLOCK = BUFFER_LOCK_*`, `src/rum.h:340-342`)
`[verified-by-code]`.

### 10. MemoryContext discipline: two scan contexts

`RumScanOpaqueData` holds two contexts (`src/rum.h:734-740`): `tempCtx` for
"consistent and ordering functions data" and `keyCtx` for "key and entry data"
`[verified-by-code]`. `startScan` switches into `keyCtx` to start each entry
(`src/rumget.c:802-807`) so per-entry allocations are freed as a unit at
rescan/endscan; per-tuple ordering work happens in `tempCtx`
`[inferred-from-code]`. The version-portable context constructor
`RumContextCreate` (`src/rum.h:1112-1127`) abstracts over PG-version churn in
`AllocSetContextCreate` signatures `[verified-by-code]`.

## Notable design decisions

- **Store attribute data per posting item, not per key.** `RumItem` bundles
  `{iptr, addInfoIsNull, addInfo}` so ordering/ranking never needs the heap
  (`src/rum.h:171-176`) `[verified-by-code]`.
- **Advertise `amcanorderbyop` while keeping GIN's cost model.** RUM claims
  order-by-operator capability (`src/rumutil.c:119`) yet delegates costing to
  `gincostestimate` (`src/rumutil.c:140`) — pragmatic reuse over a bespoke
  estimator `[verified-by-code]`.
- **Ten support procs = GIN's five + five ordering/config procs.** The added
  procs `RUM_CONFIG_PROC..RUM_ADDINFO_JOIN` (`src/rum.h:850-855`) are the entire
  ordering/ranking surface `[verified-by-code]`.
- **Reciprocal-of-score as distance.** Returning `1.0/score` makes ascending
  `<=>` yield most-relevant-first without inverting the sort
  (`src/rum_ts_utils.c:2065-2068`) `[verified-by-code]`.
- **Refuse pass-by-reference ordering columns, on purpose.** Fixed-length
  posting-tree internal nodes force `elog(ERROR, ...)` for varlena addInfo
  ordering (`src/rumutil.c:257-258`; FIXME `src/rum.h:269-278`)
  `[verified-by-code]`.
- **Alternative on-disk layout for addon ordering.** `ALT_ADD_INFO_NULL_FLAG`
  (`src/rum.h:337`) + raw-TID storage in `useAlternativeOrder` mode
  (`src/rum.h:983-1000`) trade TID delta-compression for sort-by-addInfo
  `[verified-by-code]`.
- **`amgettuple` materializes the whole scan into a RUM tuplesort.** Ordered
  results come from draining `rum_tuplesort_getrum`, not from streaming
  (`src/rumget.c:2594-2657`) `[verified-by-code]`.
- **Pending list removed.** The metapage still carries `head`/`tail`/pending
  fields but they are marked `XXX unused - pending list is removed`
  (`src/rum.h:79-97`) — RUM dropped GIN's fastupdate pending list, so inserts go
  straight into the tree (heavier inserts, no cleanup lag) `[from-comment]`.
- **Vendors core's `tidbitmap.c`.** RUM ships `rumtidbitmap.c` (`src/rum.h:27`,
  `README.md:50`) so it can build a `RumTIDBitmap` for mixed-order multi-column
  scans independent of the core bitmap `[verified-by-code]` / `[from-README]`.

## Links into corpus

- Conceptually **forks core GIN** — RUM is GIN with per-posting attribute data;
  read the core GIN inverted-index model first, then this doc for the delta.
- [[pg_textsearch]] — the tsvector/tsquery/FTS ranking machinery RUM accelerates;
  RUM's `<=>` exists to serve `ts_rank`-style relevance ordering from the index.
- [[zombodb]] — another "FTS via a foreign index engine" extension; contrast
  RUM's in-core GIN fork with ZomboDB's Elasticsearch offload.
- [[pgroonga]] — a rival full-text index AM (Groonga-backed); same problem space,
  entirely different engine.
- [[pgvector]] — the corpus's other `amcanorderbyop` distance-ordering index AM;
  compare RUM's tuplesort-drain `amgettuple` with pgvector's ordered scan.
- [[pgvectorscale]] — pgvector's streaming/DiskANN successor; another data point
  on "index AM that returns rows in distance order."

## Sources

All fetched from `https://raw.githubusercontent.com/postgrespro/rum/master/`
on 2026-07-16:

- `README.md` @ 2026-07-16 → HTTP 200
- `rum.control` @ 2026-07-16 → HTTP 200
- `META.json` @ 2026-07-16 → HTTP 200
- `src/rum.h` @ 2026-07-16 → HTTP 200
- `src/rumget.c` @ 2026-07-16 → HTTP 200
- `src/rumutil.c` @ 2026-07-16 → HTTP 200
- `src/rumbtree.c` @ 2026-07-16 → HTTP 200
- `src/rum_ts_utils.c` @ 2026-07-16 → HTTP 200

Liveness signal: source headers carry `Portions Copyright (c) 2015-2025, Postgres
Professional` (`src/rum.h:6`, `src/rumutil.c:7`), indicating active maintenance
through 2025; `rum.control` declares `default_version = '1.4'`
(`rum.control:3`) while `META.json` still advertises `1.1.0` (`META.json:5`), a
stale-PGXN-manifest tell. The README badges point at a PGXN listing and a
Travis-CI pipeline (`README.md:1-2`). GitHub star/fork counts could not be read
— the cross-repo GitHub API is blocked in this environment (`add_repo`-gated),
so the repository-popularity signal is `[unverified]`.
