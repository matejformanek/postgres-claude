# pg_roaringbitmap — ideology / divergence-from-core notes

> Extension: `ChenHuajun/pg_roaringbitmap` @ `master` (control reports
> `default_version = '1.2'`, `relocatable = true`,
> `module_pathname = '$libdir/roaringbitmap'`)
> `[verified-by-code: roaringbitmap.control:3-5]`. 284★, C. One durable "how this
> diverges from core PG design" doc. All `file:line` cites point into the
> pg_roaringbitmap tree (`roaringbitmap.c`, `roaringbitmap.h`,
> `roaringbitmap--1.2.sql`, `roaring_buffer_reader.h/.c`, `roaring.h`,
> `roaringbitmap.control`), **NOT** into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** read this against
> [[knowledge/ideologies/postgresql-hll]] — the other probabilistic/compressed-set
> custom type in the corpus. Both ship a varlena type that wraps a non-trivial
> in-memory set structure and expose composable aggregates; they differ sharply
> in *where the structure lives*. postgresql-hll stores its sketch as the on-disk
> form directly and mutates representation in place; pg_roaringbitmap stores a
> **serialized snapshot** and reconstitutes the live CRoaring object per call.
> Also a structural twin of the vendored-C-lib custom types
> [[knowledge/ideologies/pguri]] (liburiparser) and
> [[knowledge/ideologies/uuidv47]].

## Domain & purpose

pg_roaringbitmap adds a `roaringbitmap` base type (plus a 64-bit
`roaringbitmap64`) implementing **Roaring Bitmaps** — a compressed bitmap that
beats WAH/EWAH/Concise on both speed and size by partitioning the 32-bit value
space into 16-bit-keyed containers, each stored as an array, bitset, or run
depending on density `[from-README: README.md:8]`. The headline use is fast,
composable set algebra over integer id sets (user-segment intersections,
funnel/retention analytics): two bitmaps OR/AND/XOR cheaply, and the aggregates
roll partition-level bitmaps up into one. The actual algorithm is the vendored
**CRoaring** amalgamation (`roaring.c`/`roaring.h`, in-tree, ~thousands of
lines) `[verified-by-code: roaringbitmap.h:25; roaring.h present in repo tree]`.
The extension itself is thin glue: type I/O, operators, and aggregates, all
delegating the math to CRoaring.

The interesting anthropology is the **persistence boundary**. CRoaring's working
object is `roaring_bitmap_t`, a pointer-rich heap structure. PG needs a flat,
relocatable, byte-addressable on-disk value. pg_roaringbitmap resolves this by
making the stored datum CRoaring's *portable serialization* bytes (the
cross-language RoaringFormatSpec layout), and reconstructing the live object on
demand — which drives almost every divergence below.

## How it hooks into PG

- **`CREATE TYPE roaringbitmap`** as a variable-length base type:
  `INTERNALLENGTH = VARIABLE`, `STORAGE = external`, with in/out/recv/send
  `[verified-by-code: roaringbitmap--1.2.sql:9, 31-38]`. The on-disk value is a
  varlena whose payload is exactly the CRoaring portable-serialize bytes (see
  divergence #1).
- **I/O functions.** `roaringbitmap_in` accepts either a `\x…` bytea literal
  (deserialize → re-serialize round trip) or an `{1,2,3}` integer-set literal it
  parses with `strtol` into a fresh `roaring_bitmap_create()`
  `[verified-by-code: roaringbitmap.c:170-294]`. `roaringbitmap_out` is
  GUC-switched: by default it emits the bytea (`byteaout`), or with
  `roaringbitmap.output_format=array` it deserializes and prints `{…}` via a
  CRoaring iterator `[verified-by-code: roaringbitmap.c:300-336, 16-23]`.
  `roaringbitmap_recv` wraps `bytearecv` + validate + re-serialize;
  `roaringbitmap_send` just wraps the stored bytes in `pq_sendbytes`
  `[verified-by-code: roaringbitmap.c:342-385]`.
- **GUC.** `_PG_init` registers one `PGC_USERSET` enum GUC
  `roaringbitmap.output_format` (`array`|`bytea`, default `bytea`)
  `[verified-by-code: roaringbitmap.c:77-93, 16-23]`. See [[knowledge/idioms/guc-variables]].
- **Casts.** `roaringbitmap AS bytea` is `WITHOUT FUNCTION` (a free relabel,
  since the storage *is* the bytea), and `bytea AS roaringbitmap` validates via
  `rb_from_bytea` `[verified-by-code: roaringbitmap--1.2.sql:48-49]`. Conversion
  to/from `integer[]` is via functions `rb_build(integer[])` and
  `rb_to_array(roaringbitmap) RETURNS integer[]`, not casts
  `[verified-by-code: roaringbitmap--1.2.sql:138-141, 228-230]`.
- **Operators.** `&` (and), `|` (or / add-element), `#` (xor), `-` (andnot /
  remove-element), `<<`/`>>` (shift), `@>`/`<@` (contains/contained), `&&`
  (intersect), `=`/`<>` `[verified-by-code: roaringbitmap--1.2.sql:247-364]`.
  The set-comparison operators carry selectivity estimators (`contsel`,
  `contjoinsel`, `eqsel`/`eqjoinsel`) `[verified-by-code:
  roaringbitmap--1.2.sql:301-364]`.
- **Aggregates.** `rb_or_agg`, `rb_and_agg`, `rb_xor_agg`, `rb_build_agg`, and
  the cardinality variant `rb_or_cardinality_agg`, all `STYPE = internal` with
  the full parallel-agg quartet `SFUNC`/`COMBINEFUNC`/`SERIALFUNC`/`DESERIALFUNC`
  and `FINALFUNC`, `PARALLEL = SAFE`
  `[verified-by-code: roaringbitmap--1.2.sql:401-419, 432-439]`.
  See [[knowledge/idioms/fmgr]].
- **No GIN/GiST opclass, no B-tree opclass.** Despite the rich operator set,
  the install SQL defines **no `CREATE OPERATOR CLASS`** — there is no index
  access method support beyond the selectivity hints on the operators
  `[verified-by-code: grep of roaringbitmap--1.2.sql found no OPERATOR CLASS /
  GIN / GIST]`. A `roaringbitmap` column is not indexable as a set; the type is
  meant to *be* the index-like structure, not to sit under one.
- **Load model.** Conditional `PG_MODULE_MAGIC` under `#ifdef`, plain
  `CREATE EXTENSION` (no `shared_preload_libraries` requirement)
  `[verified-by-code: roaringbitmap.c:3-5]`. See [[knowledge/idioms/catalog-conventions]].

## Where it diverges from core idioms

### 1. The stored datum is CRoaring's portable-serialize blob, not the in-memory structure — every operation deserializes

This is the central divergence and the lens for the rest. Core packed types
(and the sibling [[knowledge/ideologies/postgresql-hll]]) define their *own*
on-disk layout and operate on it directly. pg_roaringbitmap instead stores the
CRoaring **portable serialization** bytes verbatim inside the varlena, and the
canonical write path everywhere is:
`roaring_bitmap_portable_size_in_bytes` → `palloc(VARHDRSZ + size)` →
`roaring_bitmap_portable_serialize(r, VARDATA(...))` → `SET_VARSIZE`
`[verified-by-code: roaringbitmap.c:156-162 (rb_from_bytea), 287-293
(roaringbitmap_in), 363-369 (recv), 416-422 (rb_or)]`. The matching read path is
`roaring_bitmap_portable_deserialize_safe(VARDATA(b), VARSIZE(b) - VARHDRSZ)`
`[verified-by-code: roaringbitmap.c:143, 186, 312, 350, 401]`. So a binary
operator like `rb_or` deserializes **both** operands into live
`roaring_bitmap_t`s, `roaring_bitmap_or_inplace`s them, re-serializes, and frees
both `[verified-by-code: roaringbitmap.c:392-423]`. The portable format is the
language-neutral RoaringFormatSpec (`SERIAL_COOKIE` header, a 16-bit
key/cardinality directory, optional run-container bitmap, per-container offsets)
— a *different* layout from CRoaring's native in-memory `roaring_array_t`
`[from-README: README.md:534 references RoaringFormatSpec for the 64-bit type;
inferred for the 32-bit type by symmetry]`. Choosing the portable (not "frozen"
/ native) format buys cross-version and cross-platform stability of stored data
at the cost of a deserialize on every access. Cross-ref the core varlena/TOAST
machinery in `src/backend/access/common/` and the type-I/O contract in
`src/backend/utils/adt/`.

### 2. A bespoke zero-deserialize reader (`roaring_buffer_*`) shadows CRoaring for the read-only operators

Because divergence #1 makes "deserialize both sides" the default and that is
wasteful for queries that only need a count or a boolean, the extension ships
its **own** parser, `roaring_buffer_reader.c/.h`, that walks the serialized
buffer *in place* without materializing a `roaring_bitmap_t`. `roaring_buffer_t`
holds borrowed pointers into the serialized bytes — `keyscards`, `offsets`,
`bitmapOfRunContainers` — plus `*_need_free` flags
`[verified-by-code: roaring_buffer_reader.h:6-16]`. It re-implements a slice of
CRoaring's API directly over the spec layout: `roaring_buffer_and`,
`roaring_buffer_or_cardinality`, `roaring_buffer_and_cardinality`,
`roaring_buffer_intersect`, `roaring_buffer_contains`, `roaring_buffer_rank`,
etc., each returning a status bool (false on a malformed buffer)
`[verified-by-code: roaring_buffer_reader.h:25-154]`. The C-side picks the
reader for the cheap paths: `rb_or_cardinality` and `rb_and` build
`roaring_buffer_t`s and never call `portable_deserialize`
`[verified-by-code: roaringbitmap.c:434-457 (rb_or_cardinality), 474-499
(rb_and)]`, while `rb_or` (which must produce a full new bitmap) still goes
through the full deserialize path `[verified-by-code: roaringbitmap.c:401-419]`.
Maintaining a *second, hand-rolled* deserializer that must track the upstream
on-disk format is an unusual maintenance burden core types never carry — it is
the price of having picked a serialize-on-disk representation (#1) and then
needing to claw back the per-query cost. `[verified-by-code]` for the call-site
split; the in-place binary-search container lookup is `[from-comment:
roaring_buffer_reader.c:11-15]`.

### 3. CRoaring's allocator is redirected into the PostgreSQL MemoryContext system via a global hook

CRoaring normally calls `malloc`/`free`/`realloc`/`calloc` plus an
`aligned_malloc`/`aligned_free` pair `[verified-by-code: roaring.h:2361-2379
declares roaring_memory_t + roaring_init_memory_hook]`. pg_roaringbitmap
installs a `roaring_memory_t` whose function pointers are PG allocators —
`.malloc = palloc`, `.realloc = pg_realloc` (palloc/repalloc),
`.calloc = pg_calloc` (palloc0), `.free = pg_free`, plus custom
`aligned_malloc`/`aligned_free` — and calls `roaring_init_memory_hook(...)` once
in `_PG_init` `[verified-by-code: roaringbitmap.c:64-93]`. This is the *opposite*
discipline from the sibling vendored-lib types [[knowledge/ideologies/pguri]]
(liburiparser `malloc`s outside any context, with a hand-`free` boundary that
leaks on the error path) and pg_jieba (C++ `new` invisible to MemoryContext):
here the vendored library's *entire* heap is pulled inside the current
MemoryContext, so CRoaring allocations are reclaimed by normal context teardown
and an `ereport(ERROR)` mid-operation does not leak the in-flight bitmap. The
catch: the hook is **process-global** and set once; whatever
`CurrentMemoryContext` is live when CRoaring calls `palloc` is where the bitmap
lands. The aggregate code therefore has to `MemoryContextSwitchTo(aggctx)`
*around* every CRoaring call so the transition state survives between rows (see
#4) `[verified-by-code: roaringbitmap.c:1782-1794, 1868-1884]`. See
[[knowledge/idioms/memory-contexts]].

### 4. A hand-rolled aligned-malloc that smuggles a palloc'd block past an alignment requirement

CRoaring wants aligned allocations; `palloc` only guarantees MAXALIGN.
`pg_aligned_malloc` over-allocates `size + alignment`, rounds the returned
pointer up to the alignment boundary, and stores the byte-offset back to the
real `palloc` header in `p[-1]` so `pg_aligned_free` can recover the original
pointer to `pfree` it `[verified-by-code: roaringbitmap.c:25-46]`. The
`pg_aligned_free` path even has a fallback (`if (porg == memblock) porg -= 256`)
for the zero-offset case `[verified-by-code: roaringbitmap.c:42-44; inferred:
this handles the edge case where the aligned pointer coincided with the palloc
pointer so the stored offset byte is 0]`. This is a real (if small) re-implement
of an aligned allocator on top of PG's, with a one-byte sidecar header — exactly
the kind of pointer arithmetic core avoids by giving aligned needs their own
`palloc`-with-alignment paths. `[verified-by-code]` for the mechanism;
`assert(alignment <= 256)` bounds the sidecar to one byte
`[verified-by-code: roaringbitmap.c:31]`.

### 5. The aggregate transition state is a raw `roaring_bitmap_t *` carried as `internal`, with full parallel-agg plumbing

The aggregates use `STYPE = internal` and pass the live CRoaring pointer between
calls via `PG_GETARG_POINTER`/`PG_RETURN_POINTER`
`[verified-by-code: roaringbitmap--1.2.sql:403; roaringbitmap.c:1778, 1789,
1797]`. Each transfn guards with `AggCheckCallContext(fcinfo, &aggctx)` and
`MemoryContextSwitchTo(aggctx)` so the bitmap lives in the aggregate context,
not the per-tuple context `[verified-by-code: roaringbitmap.c:1769-1794]`. The
first non-null row deserializes into the state; subsequent rows
`roaring_bitmap_or_inplace` into it `[verified-by-code: roaringbitmap.c:1774-1797]`.
For **parallel** aggregation, the `internal` state can't cross the worker→leader
DSM boundary, so the extension supplies `SERIALFUNC = rb_serialize` (state →
bytea via portable serialize) and `DESERIALFUNC = rb_deserialize` (bytea →
`internal`), plus `COMBINEFUNC = rb_or_combine` to merge per-worker states
`[verified-by-code: roaringbitmap.c:2059-2118; roaringbitmap--1.2.sql:405-408]`.
Two subtleties worth flagging: (a) `rb_deserialize` explicitly sets
`fcinfo->isnull = false`, with a comment pinning it to a real bug — PG's
`combine_aggregates()` only inits `isnull` once
`[verified-by-code: roaringbitmap.c:2113-2116; from-comment cites issue #6]`;
and (b) `rb_and_trans` notes "postgres will crash when use PG_GETARG_BYTEA_PP
here" and deliberately uses the fully-detoasted `PG_GETARG_BYTEA_P`
`[verified-by-code: roaringbitmap.c:1864-1866; from-comment]` — a packed-varlena
footgun the same family as the one [[knowledge/ideologies/pguri]] hits. This is
a textbook-correct parallel-agg implementation, but the `internal`-state +
serialize/deserialize-for-DSM contract is far more machinery than a core
fixed-width aggregate needs, and it leans entirely on the portable-serialize
format (#1) doubling as the DSM transport. See [[knowledge/idioms/parallel-state-propagation]],
and the `CREATE AGGREGATE` parallel contract documented around
`src/backend/executor/nodeAgg.c`.

### 6. `STORAGE = external` — TOAST without compression, because the payload is already compressed

The type declares `STORAGE = external`
`[verified-by-code: roaringbitmap--1.2.sql:37]`, which lets large bitmaps move
out-of-line to the TOAST relation but **disables LZ compression** of the datum.
This is a deliberate inversion of the default `extended` storage core hands a
varlena: a Roaring bitmap is already a compressed structure, so running PGLZ
over it wastes CPU for ~no gain. `[inferred]` from the `external` choice against
an already-compressed payload — the README does not state the rationale, but the
combination (variable-length + external + a compressed serialization) is the
standard "don't double-compress" idiom. Contrast core `text`/`bytea` which
default to `extended`.

### 7. No B-tree/hash opclass, yet a full `=`/`<>` operator pair with selectivity hints

The `=` operator is backed by `rb_equals` (a CRoaring `roaring_buffer_equals`
content comparison) and wired with `eqsel`/`eqjoinsel`
`[verified-by-code: roaringbitmap--1.2.sql:346-354]`, but there is **no hash or
btree opclass**, so `roaringbitmap` cannot back a `GROUP BY`, `DISTINCT`, hash
join, or unique index on the type itself — only explicit `WHERE a = b`
filtering. Core base types that ship `=` almost always ship a matching opclass;
the omission here signals the type is a payload, not a key. `[verified-by-code]`
(absence of opclass DDL) + `[inferred]` for the intent.

## Notable design decisions (with cites)

- **Validate-on-input, always re-serialize.** Every entry point that ingests
  external bytes (`rb_from_bytea`, `roaringbitmap_in` bytea branch, `recv`)
  runs `roaring_bitmap_internal_validate` and rejects malformed input with
  `ERRCODE_INVALID_TEXT_REPRESENTATION`, then re-serializes to a canonical form
  rather than trusting the input bytes `[verified-by-code: roaringbitmap.c:149-162,
  192-205, 356-369]`. The cheap read-only operators that use the buffer reader
  instead get a `false` return → `ereport(ERROR, "bitmap format is error")`
  `[verified-by-code: roaringbitmap.c:441-444]`. See [[knowledge/idioms/error-handling]].
- **Dual text input syntax.** One `*_in` accepts both the `\x` bytea hex form
  and the human `{1,2,3}` set form, dispatching on the first two chars
  `[verified-by-code: roaringbitmap.c:181-206]` — a convenience core types
  rarely offer (usually one canonical input grammar).
- **GUC-switched output.** `roaringbitmap_out` returns bytea by default for
  round-trip fidelity and dump/restore safety, switching to the readable `{…}`
  only when the session GUC asks `[verified-by-code: roaringbitmap.c:307-309]`.
- **`run_optimize` is opt-in.** `rb_runoptimize` deserializes, calls
  `roaring_bitmap_run_optimize` (which converts dense runs to run-containers),
  and re-serializes `[verified-by-code: roaringbitmap.c:2152-2173]` — the
  space optimization is a user-invoked function, not automatic on write.
- **A parallel 64-bit type.** `roaringbitmap64` mirrors the whole surface for
  `bigint` domains via `roaring64_buffer_reader.*` and `roaringbitmap64.c`,
  with casts both directions to the 32-bit type
  `[verified-by-code: roaringbitmap--1.2.sql:543-560; from-README:
  README.md:534]`.
- **CRoaring is vendored in-tree (not a submodule).** `roaring.c`/`roaring.h`
  (the upstream amalgamation) are committed in the repo, so the `roaring_memory_t`
  hook struct and API are pinned to a known version
  `[verified-by-code: roaring.h:2361-2379 present in repo tree]` — contrast
  pg_jieba's submodule cppjieba.

## Links into corpus

- [[knowledge/ideologies/postgresql-hll]] — the closest sibling: another
  probabilistic/compressed-set custom type with composable aggregates. **Contrast:**
  hll stores its sketch *as* the on-disk form and promotes representation in
  place; pg_roaringbitmap stores a serialized snapshot and rebuilds the live
  CRoaring object per call, then shadows it with a zero-deserialize reader (#2).
- [[knowledge/ideologies/pguri]] — vendored-C-lib custom type (liburiparser).
  **Contrast on the allocator boundary:** pguri leaks the library's own `malloc`'d
  struct on the error path; pg_roaringbitmap redirects CRoaring's *entire*
  allocator into MemoryContext via `roaring_init_memory_hook` (#3), so library
  allocations are context-reclaimed.
- [[knowledge/ideologies/uuidv47]] — small custom base type sibling
  (parse-once-store-binary); structural contrast on the store-form decision.
- [[knowledge/idioms/fmgr]] — `PG_FUNCTION_INFO_V1`, `PG_GETARG_BYTEA_P`
  vs the `_PP` packed footgun (#5), `internal`-typed state passing, the SRF
  `rb_iterate`.
- [[knowledge/idioms/memory-contexts]] — the global allocator hook + per-call
  `MemoryContextSwitchTo(aggctx)` discipline (#3, #4); the hand-rolled
  aligned-malloc sidecar.
- [[knowledge/idioms/catalog-conventions]] — `CREATE TYPE` (variable-length,
  `STORAGE = external`), in/out/recv/send, casts, and the **absent** opclass
  (#6, #7).
- [[knowledge/idioms/parallel-state-propagation]] — the parallel-agg
  serialize/deserialize/combine contract (#5); also the `CREATE AGGREGATE`
  parallel-safety machinery around `src/backend/executor/nodeAgg.c`. *(If this
  doc does not yet exist, the parallel-agg discussion lives in #5 above.)*
- [[knowledge/idioms/guc-variables]] — the single `PGC_USERSET` enum output GUC.
- Core analogs in prose: varlena/TOAST in `src/backend/access/common/` (the
  `STORAGE = external` no-double-compress choice), type I/O in
  `src/backend/utils/adt/`, and the parallel `CREATE AGGREGATE`
  combine/serialize contract.

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/ChenHuajun/pg_roaringbitmap/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaringbitmap.control | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/README.md | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaringbitmap--1.2.sql | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaringbitmap.h | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaringbitmap.c | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaring_buffer_reader.h | 200 |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaring_buffer_reader.c | 200 (skimmed top) |
| https://raw.githubusercontent.com/ChenHuajun/pg_roaringbitmap/master/roaring.h | 200 (grepped for memory-hook decls) |

**Fetch notes / substitutions:**
- The prompt's manifest was a guess; the real tree confirmed the canonical files
  at repo root: main C is `roaringbitmap.c` (2173 lines), install SQL is
  `roaringbitmap--1.2.sql` matching `default_version = '1.2'` (the prompt's
  generic "SQL install script" name), control is a plain `.control` (no
  `.control.in`). No 404s encountered.
- **CRoaring is vendored in-tree**, not a git submodule: `roaring.c` and
  `roaring.h` are committed amalgamation files. So the `roaring_memory_t` struct
  and `roaring_init_memory_hook` are `[verified-by-code: roaring.h:2361-2379]`,
  not `[inferred]`. The *internals* of CRoaring's containers and the byte-level
  RoaringFormatSpec layout were not read line-by-line — claims about the portable
  format's structure are `[from-README]`/`[inferred]` and pinned to the spec URL
  the README cites (RoaringFormatSpec), not to a code read of `roaring.c`.
- `roaring_buffer_reader.c` was only skimmed at the top (binary-search /
  advance-until container lookup) to confirm it parses the serialized buffer in
  place; the divergence-#2 claims rest on its header (`roaring_buffer_reader.h`)
  and the call sites in `roaringbitmap.c`, both `[verified-by-code]`.
- `roaringbitmap64.c` and `roaring64_buffer_reader.*` were not fetched; the
  64-bit type is characterized from the SQL DDL and README only
  (`[verified-by-code]` for the DDL, `[from-README]` for the format).

