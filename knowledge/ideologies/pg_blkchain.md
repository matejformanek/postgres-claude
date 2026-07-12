# pg_blkchain — ideology / divergence notes

Extension: **blkchain/pg_blkchain** (`master`, control `default_version =
'0.0.1'`). A C extension that parses Bitcoin blocks / transactions / scripts
and runs Bitcoin consensus (script interpreter + ECDSA signature verification)
as ordinary SQL functions over `bytea` blobs, backed by the external
**libbitc** C library (a SegWit fork of picocoin) linked into the backend.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched repo files (`pg_blkchain.c`,
> `pg_blkchain--0.0.1.sql`, `pg_blkchain.control`, `Makefile`, `README.md`),
> **not** `source/`. Cites verified against files fetched 2026-07-12 (see
> Sources footer). This is a member of the "wrap an external C library as SQL
> functions" cluster — read alongside `[[pguri]]` (liburiparser), `[[pgsodium]]`
> (libsodium), `[[pg-libphonenumber]]`, `[[postgresql-hll]]`, `[[pg_hashids]]`,
> `[[onesparse]]` (SuiteSparse). Its distinguishing move is *presentation over
> borrowed storage*: no custom on-disk type — it projects libbitc's parsed C
> structs as SQL composites over user-owned `bytea`. Contrast the
> custom-base-type cluster `[[uuidv47]]` / `[[zson]]`. Status per README:
> **work-in-progress, "use at your own risk"** (`README.md:4`) `[from-README]`,
> "developed and tested only on PG 9.6" (`README.md:124`) `[from-README]`.

---

## Domain & purpose

pg_blkchain "provides Bitcoin blockchain functionality" from within Postgres
(`README.md:6-7`) `[from-README]`. Concretely it exposes libbitc's block/tx
deserializer, its Script opcode parser, and its consensus signature verifier as
SQL-callable functions. The unit of work is a **`bytea` blob** the user already
stores — a raw serialized block or transaction, e.g. pulled from bitcoind — not
a bespoke type: every entry point takes `bytea` and the README's examples run
`get_vin(tx)`, `parse_script(...)`, `verify_sig(tx, ptx, n)` against a user
table `rtxs` with a plain `BYTEA` column named `tx` (`README.md:31-52`)
`[from-README]`. So the extension is a **lens**, not a store: it re-parses the
blob on every call and shapes the result into SQL composites, arrays, or jsonb.
There is **no `CREATE TYPE ... (INTERNALLENGTH …)` base type** anywhere in the
install SQL — only composite `CREATE TYPE … AS (…)` row shapes
(`pg_blkchain--0.0.1.sql:10,15,20,25,30,48`) `[verified-by-code]`, confirming
the "borrowed storage" reading.

---

## How it hooks into PG

Pure loadable-C-function extension. **No `_PG_init`, no GUC, no hook, no
background worker, no custom AM, no on-disk type** — bare `PG_MODULE_MAGIC;` at
`pg_blkchain.c:25` `[verified-by-code]` and nothing runs at load time.

- **Control file** `pg_blkchain.control`: `default_version = '0.0.1'`,
  `relocatable = true`, comment `'Tools to Process the Blockchain'`
  (`pg_blkchain.control:1-4`) `[verified-by-code]`. `relocatable = true` is
  honest — the extension creates only schema-agnostic composites + functions.
- **fmgr entry points** via `PG_FUNCTION_INFO_V1`: the parse/consensus surface
  `verify_sig`, `get_vin`, `get_vout`, `get_tx`, `get_block`, `parse_script`
  (`pg_blkchain.c:27,92,212,322,375,439`); the "experimental" projection
  variants `get_vout_arr`, `get_vin_arr`, `get_vin_outpt_arr`,
  `get_vin_outpt_jsonb`, `get_vin_outpt_bytea` (`:542,616,700,771,860`); the
  aggregate support functions `build_vin_transfn`/`_finalfn`,
  `build_vout_transfn`/`_finalfn` (`:922,1008,1048,1114`); and the
  little-endian helper `int4send_le` (`:1149`) `[verified-by-code]`. Args via
  `PG_GETARG_BYTEA_P` / `PG_GETARG_INT32`, returns via `PG_RETURN_BOOL` /
  `PG_RETURN_DATUM` / `PG_RETURN_ARRAYTYPE_P` / `PG_RETURN_POINTER`. See
  `[[fmgr-and-spi]]`.
- **Composite returns**, three shapes off the *same* parsed struct:
  1. **Single tuple** — `get_tx`, `get_block` call `get_call_result_type` →
     `heap_form_tuple` → `HeapTupleGetDatum` (`pg_blkchain.c:339-372,393-436`)
     `[verified-by-code]`.
  2. **`SETOF` via SRF ValuePerCall** — `get_vin`, `get_vout`, `parse_script`
     use `SRF_IS_FIRSTCALL` / `SRF_FIRSTCALL_INIT` /
     `multi_call_memory_ctx` / `SRF_PERCALL_SETUP` / `SRF_RETURN_NEXT` /
     `SRF_RETURN_DONE`, stashing the parsed `bitc_tx` (or `bscript_parser`) in
     `funcctx->user_fctx` across calls (`pg_blkchain.c:108-209,229-320,455-539`)
     `[verified-by-code]`. **Not** Materialize mode.
  3. **`composite[]` arrays** — `get_vout_arr` etc. loop, `heap_form_tuple` per
     element, then `construct_array` over `tupdesc->tdtypeid`
     (`pg_blkchain.c:578-608`) `[verified-by-code]`.
- **The composite row types live in SQL, not C.** `CBlock`, `CTx`, `CTxIn`,
  `CTxOut`, `CScriptOp`, `COutPt` are `CREATE TYPE … AS (…)`
  (`pg_blkchain--0.0.1.sql:10,15,20,25,30,48`), and the C code discovers their
  `TupleDesc` at runtime via `get_call_result_type` /
  `TypeGetTupleDesc(get_element_type(...))` + `BlessTupleDesc`
  (`pg_blkchain.c:118,239,559-567`) `[verified-by-code]`. The C side never
  registers a type; it only knows field *positions*.
- **Two `CREATE AGGREGATE`s** — `build_vin` / `build_vout` reduce a set of
  input rows back into a serialized-vin / serialized-vout `bytea` (the inverse
  of `get_vin`/`get_vout`), `stype = internal`, C transfn + finalfn
  (`pg_blkchain--0.0.1.sql:61-91`) `[verified-by-code]`.
- **Build**: PGXS `MODULE_big = pg_blkchain`, `SRCS = pg_blkchain.c`, and the
  external library linked as a plain shared lib — `SHLIB_LINK += -lbitc`
  (`Makefile:9-14`) `[verified-by-code]`. Unlike `[[pg_hashids]]` (which
  compiles its vendored `.c` into the same `.so`), libbitc is a *separate*
  installed shared object the reader must build first (`README.md:97-124`)
  `[from-README]`. See `[[extension-development]]`.

---

## Where it diverges from core idioms

### 1. A third-party consensus + crypto library runs inside the backend address space

The headline. `verify_sig` deserializes two transactions and calls libbitc's
`bitc_verify_sig(&coin, &txto, n, SCRIPT_VERIFY_P2SH|SCRIPT_VERIFY_WITNESS,
txout->nValue)` (`pg_blkchain.c:83`) `[verified-by-code]` — i.e. it executes
the **Bitcoin Script interpreter and ECDSA signature verification** in-process,
in a forked backend, as an `IMMUTABLE STRICT` SQL function
(`pg_blkchain--0.0.1.sql:35-37`) `[verified-by-code]`. This is a far larger and
more security-sensitive blob of foreign C than the string/number libraries in
the sibling cluster (`[[pguri]]`, `[[pg_hashids]]`): a bug in libbitc's script
VM or crypto is a bug in the backend, and consensus-critical verification now
shares a memory space with the query executor. The extension trusts libbitc's
parser on adversarial input — every `deser_bitc_*` failure is caught and turned
into `ereport(ERROR, ERRCODE_DATA_EXCEPTION)` (`pg_blkchain.c:47-50,55-58`
etc.) `[verified-by-code]`, but a *non-graceful* failure (overread, abort)
inside the library is uncontained. `verify_sig` also **short-circuits one
consensus check**: `txfrom.sha256_valid = true; /* shortcut - why wouldn't it
be? */` (`pg_blkchain.c:52`) `[verified-by-code]` skips recomputing the funding
tx's hash, trusting the caller's blob. Contrast the crypto sibling
`[[pgsodium]]`, which wraps libsodium primitives but does not run a consensus
state machine. Tag: `[verified-by-code]` for the call; the blast-radius
argument is `[inferred]` from the in-process FFI model.

### 2. It projects the library's C structs as SQL rows rather than storing them

Core custom types parse once at `*_in` and *store* a packed binary form
(`[[uuidv47]]`, `[[zson]]`). pg_blkchain does neither halves of that: it stores
nothing and parses *every* call. Each entry point re-runs
`deser_bitc_tx(tx, &cbuf)` over the input `bytea` (`pg_blkchain.c:129,250,347`
etc.) `[verified-by-code]`, walks the resulting `struct bitc_tx` /
`bitc_txin` / `bitc_txout`, and copies individual fields into a freshly built
tuple — `values[1] = UInt32GetDatum(tx->nVersion)`, `memcpy(VARDATA(hash),
&tx->sha256, 32)`, etc. (`pg_blkchain.c:355-364`) `[verified-by-code]`. The SQL
composite is a **presentation projection** of a transient in-memory C struct,
never a stored representation. The SQL comments make the mapping explicit:
`uint32` is surfaced as signed `INT` "because both are 4 bytes" (so values
> 2^31 read back negative) and field names drop the Hungarian prefix
(`nVersion` → `version`) (`pg_blkchain--0.0.1.sql:4-8`) `[verified-by-code]`.
This is the same "reparse-per-call over borrowed storage" tradeoff as
`[[pguri]]`'s reparse-per-accessor, but taken further: pguri at least owns its
column; pg_blkchain owns nothing.

### 3. The palloc ↔ libbitc-allocator boundary is walked by hand, per call

Every function allocates the top-level `bitc_tx` with `palloc`, then hands it to
libbitc's own `bitc_tx_init` / `deser_bitc_tx`, which fill in internal
structures (the `vin`/`vout` `parr` arrays, `scriptSig`/`scriptPubKey`
`cstring`s) using **libbitc's own allocator**, and releases them with
`bitc_tx_free(tx); pfree(tx);` (`pg_blkchain.c:126-127,369-370,433-434`)
`[verified-by-code]`. So the ownership split is: the *container* is palloc'd
(reclaimed on context reset even under a longjmp), but the *library's inner
allocations* are freed only by the explicit `bitc_*_free` calls on the happy
path. An `ereport(ERROR)` *after* a successful `deser_bitc_tx` but *before* the
matching `bitc_tx_free` — e.g. the `get_call_result_type` failure branch, or an
OOM inside the projection loop — abandons libbitc's inner allocations, and PG's
MemoryContext teardown will **not** reclaim them (they are not palloc chunks).
`[inferred]` from the free-on-happy-path-only structure vs the library-owned
inner memory (contrast `[[pg_hashids]]`, which patches its vendored library's
allocator to `palloc0`/`pfree` so a longjmp cannot leak; pg_blkchain does
**not** — it links libbitc unmodified). This is the same address-space-boundary
hazard `[[pguri]]` documents for `uriFreeUriMembersA`. See `[[memory-contexts]]`,
`[[error-handling]]`.

### 4. The SRF result-type discovery relies on the SQL-declared composite

Because the row shapes live in SQL, the C code must *learn* them at runtime:
`get_call_result_type(fcinfo, NULL, &tupdesc) != TYPEFUNC_COMPOSITE` guards
every composite return, and the array variants call
`get_element_type(arroid)` + `TypeGetTupleDesc` to reach through the declared
`composite[]` to its element tupdesc (`pg_blkchain.c:118-121,559-567`)
`[verified-by-code]`. The C is thus **positionally coupled** to the `.sql` — it
writes `values[0..N]` in the order the `CREATE TYPE` lists columns
(`get_vin`'s `values[0..4]` ↔ `CTxIn (n, prevout_hash, prevout_n, scriptSig,
sequence)`, `pg_blkchain.c:174-193` ↔ `pg_blkchain--0.0.1.sql:20`)
`[verified-by-code]`. Reorder a column in the SQL without touching the C and
the projection silently mis-maps. This is a deliberate consequence of choosing
SQL-defined composites over C-registered types.

### 5. Multiple output encodings of the *same* datum — composite, array, jsonb, packed bytea

The `get_vin_outpt_*` family returns the same outpoint list four ways:
`COutPt[]` composite array via `construct_array` (`pg_blkchain.c:700-769`), a
hand-built **jsonb** via `pushJsonbValue(WJB_BEGIN_ARRAY …)` /
`JsonbValueToJsonb` (`:771-858`), and a `BYTEA[]` of raw
32-byte-hash-plus-big-endian-index concatenations (`:860-913`)
`[verified-by-code]`. The jsonb path even round-trips through fmgr composition —
`DirectFunctionCall1(byteaout, …)` to stringify a hash and
`DirectFunctionCall3(numeric_in, …)` to build a numeric (`:827,845`)
`[verified-by-code]`, the same fmgr-reuse idiom `[[pguri]]` uses for `inet_in`.
This is an experimentation surface (the `.sql` tags these and the `*_arr`
functions `-- experimental`, `pg_blkchain--0.0.1.sql:39`) `[from-comment]`
exploring which shape SQL callers find ergonomic, rather than one committed API.

### 6. Aggregates rebuild library structs in the aggregate context and are deliberately non-STRICT

`build_vin`/`build_vout` invert the readers: `build_vin_transfn` accumulates a
libbitc `parr` of `bitc_txin`s into the aggregate memory context
(`AggCheckCallContext(fcinfo, &aggContext)` → `MemoryContextSwitchTo`,
`pg_blkchain.c:946-951`), and `build_vin_finalfn` serializes it with libbitc's
`ser_bitc_txin` into a `bytea` (`:1020-1038`) `[verified-by-code]`. The transfn
is declared `IMMUTABLE PARALLEL SAFE` but **not** `STRICT`
(`pg_blkchain--0.0.1.sql:63-65`), and the C explicitly checks each arg with
`PG_ARGISNULL` — treating a NULL `prevout_hash` as a coinbase all-zero hash
(`pg_blkchain.c:930-975`) `[verified-by-code]`: a case a STRICT marking would
have silently dropped. Note the `stype = internal` state pointer is passed
across calls raw, the classic transition-state idiom (see `[[fmgr-and-spi]]`).

> **Quality drift worth flagging (WIP status).** Two hand-rolled allocations in
> this file look wrong against core's varlena/palloc discipline: (a) the
> `build_vin` growth path calls `repalloc(&state->vin->data, …)` — passing the
> *address of* the struct field rather than the heap chunk `state->vin->data`
> (`pg_blkchain.c:998`, mirrored for vout at `:1104`) `[verified-by-code]`;
> `repalloc` on a non-chunk pointer is undefined, so aggregates that grow past
> the initial 8-slot array are at risk. (b) The jsonb path sizes the
> per-number buffer as `palloc(jb.val.string.len + 1)` where
> `jb.val.string.len` is still the *key* length (`"n"` ⇒ 1) at that point, then
> `snprintf`s the full `prevout.n` decimal (`n_len` digits) into it
> (`pg_blkchain.c:840-842`) `[verified-by-code]` — a heap overflow for any index
> ≥ 10. Consequences are `[inferred]`; the code is `[verified-by-code]`. These
> are consistent with the README's "work-in-progress, use at your own risk"
> self-warning (`README.md:4`) `[from-README]`. The file also uses C++ `//`
> comments (`pg_blkchain.c:866,915,1041`), off core house style.

---

## Notable design decisions (with cites)

- **No on-disk type; operate over `bytea`.** All entry points take
  `PG_GETARG_BYTEA_P` and wrap `{ VARDATA, VARSIZE-VARHDRSZ }` into libbitc's
  `struct const_buffer` (`pg_blkchain.c:31-36,112,328`) `[verified-by-code]`.
  Presentation over borrowed storage — the deliberate contrast with the
  custom-base-type cluster `[[uuidv47]]` / `[[zson]]` / `[[pguri]]`.
- **Consensus in the backend.** `verify_sig` runs the Script VM + ECDSA via
  `bitc_verify_sig`, with a hash-validity shortcut (`pg_blkchain.c:52,83`)
  `[verified-by-code]`.
- **SQL-defined composites, C discovers the tupdesc.** `CREATE TYPE … AS`
  (`pg_blkchain--0.0.1.sql:10-48`) + `get_call_result_type` / `BlessTupleDesc`
  (`pg_blkchain.c:118-124`) `[verified-by-code]`.
- **libbitc linked as an external `.so`** (`SHLIB_LINK += -lbitc`,
  `Makefile:14`) `[verified-by-code]`, unmodified — no palloc bridge (contrast
  `[[pg_hashids]]`). The commented `#SHLIB_LINK += -lccoin` (`Makefile:13`)
  hints at an earlier picocoin/ccoin backend.
- **Everything `IMMUTABLE`.** Readers `IMMUTABLE STRICT`
  (`pg_blkchain--0.0.1.sql:13,18,23,…`); aggregate support functions
  `IMMUTABLE PARALLEL SAFE`, transfns intentionally non-STRICT
  (`:63-85`) `[verified-by-code]`. Immutability is honest — output is a pure
  function of the input blob (no GUC, no session state), so the planner may
  constant-fold, matching the `[[pg_hashids]]` "truthful IMMUTABLE" case.
- **`int4send_le`** — a little-endian twin of core `int4send`, for building
  Bitcoin's LE wire integers (`pg_blkchain.c:1149-1160`) `[verified-by-code]`.
- **README leans on `pgcrypto`** for the `digest(digest(tx,'sha256'),'sha256')`
  join key in the `verify_sig` example (`README.md:35-52`) `[from-README]` —
  the extension composes with core crypto rather than exposing its own hashing.

---

## Links into corpus

- `[[fmgr-and-spi]]` — the whole surface: `PG_FUNCTION_INFO_V1`,
  `PG_GETARG_BYTEA_P` / `PG_RETURN_*`, SRF ValuePerCall
  (`SRF_IS_FIRSTCALL`/`SRF_RETURN_NEXT`), `get_call_result_type` +
  `heap_form_tuple` composite build, `construct_array`, and the
  `internal`-state aggregate transfn/finalfn pattern. Also
  `.claude/skills/fmgr-and-spi/SKILL.md`.
- `[[catalog-conventions]]` — `CREATE TYPE … AS (…)` composites,
  `CREATE FUNCTION … LANGUAGE C`, `CREATE AGGREGATE`, `relocatable = true`
  control file (`pg_blkchain--0.0.1.sql`).
- `[[memory-contexts]]` — the palloc ↔ libbitc-allocator boundary (§3): palloc'd
  container, library-owned inner allocations freed only on the happy path; SRF
  `multi_call_memory_ctx` and aggregate-context switches.
- `[[error-handling]]` — parse failures → `ereport(ERROR,
  ERRCODE_DATA_EXCEPTION)`; wrong-context returns →
  `ERRCODE_FEATURE_NOT_SUPPORTED`; `elog(ERROR)` for non-aggregate context
  (`pg_blkchain.c:948`).
- Sibling ideologies (the "wrap an external C library" cluster):
  `[[pguri]]` (liburiparser — same address-space-boundary + reparse-per-call
  theme), `[[pgsodium]]` (libsodium — the crypto-in-backend sibling, but no
  consensus VM), `[[pg-libphonenumber]]`, `[[postgresql-hll]]`, `[[onesparse]]`
  (SuiteSparse — the largest foreign lib in the cluster), `[[pg_hashids]]` (the
  *contrast* on the allocator bridge — it patches its lib to palloc; pg_blkchain
  does not). Custom-base-type contrast: `[[uuidv47]]`, `[[zson]]` (parse-once,
  store-packed — pg_blkchain stores nothing).

> Corpus gap: no `idioms/composite-srf-projection.md` capturing the
> "SQL-declares-the-row-shape, C-discovers-the-tupdesc-and-writes-by-position"
> pattern (`get_call_result_type` + `heap_form_tuple` + positional coupling).
> pg_blkchain, `[[onesparse]]`, and any SRF-returning extension would anchor it;
> today it hangs off `[[fmgr-and-spi]]`. `[inferred]`

---

## Sources

Fetched 2026-07-12 (branch `master`), all via `raw.githubusercontent.com`
(HTTP 200); `git/trees` + `api.github.com` are 403-blocked in this environment
so no tree enumeration was possible — the manifest paths were fetched directly
and all resolved at repo root (no `src/` subdir, no `.control.in` template):

- `https://raw.githubusercontent.com/blkchain/pg_blkchain/master/README.md`
  → HTTP 200 (124 lines; purpose, usage examples, libbitc build instructions,
  WIP + PG-9.6 warnings).
- `https://raw.githubusercontent.com/blkchain/pg_blkchain/master/Makefile`
  → HTTP 200 (19 lines; PGXS `MODULE_big`, `SRCS = pg_blkchain.c`,
  `SHLIB_LINK += -lbitc`, commented `-lccoin`, regression harness).
- `https://raw.githubusercontent.com/blkchain/pg_blkchain/master/pg_blkchain.c`
  → HTTP 200 (1160 lines; deep-read — all 16 entry points, SRF/array/jsonb
  projections, both aggregates, the palloc/libbitc boundary, and the two
  hand-alloc bugs).
- `https://raw.githubusercontent.com/blkchain/pg_blkchain/master/pg_blkchain--0.0.1.sql`
  → HTTP 200 (97 lines; composite `CREATE TYPE`s, `CREATE FUNCTION … LANGUAGE
  C`, two `CREATE AGGREGATE`s, volatility/strictness markings).
- `https://raw.githubusercontent.com/blkchain/pg_blkchain/master/pg_blkchain.control`
  → HTTP 200 (4 lines; `default_version = '0.0.1'`, `relocatable = true`).

No 404s; no path corrections needed. All cites are `[verified-by-code]` against
the fetched files except: motivation / status / usage semantics (`[from-README]`
/ `[from-comment]`); and the reasoned analysis points tagged `[inferred]` — the
in-process FFI blast radius (§1), the library-inner-memory leak on the error
path (§3), and the runtime consequences of the two hand-alloc bugs (§ quality
note). **libbitc internals are not in this repo**; every claim about what
`deser_bitc_tx` / `bitc_verify_sig` / `bitc_tx_free` do internally is
`[inferred]` from the call sites and libbitc's stated role as a picocoin/SegWit
fork (`README.md:100-101`), not from reading libbitc source.
