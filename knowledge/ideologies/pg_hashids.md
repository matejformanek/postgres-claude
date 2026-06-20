# pg_hashids — ideology / divergence notes

Extension: **iCyberon/pg_hashids** (`master`, default version `1.3`).
A SQL-callable wrapper around the [hashids.c](https://github.com/tzvetkoff/hashids.c)
algorithm: `SELECT id_encode(1001)` → `'jNl'`, and the inverse `id_decode` /
`id_decode_once`.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched repo files (not `source/`), as
> `pg_hashids.c`, `hashids.c`, `hashids.h`, `pg_hashids.control`,
> `pg_hashids--1.3.sql`. Cites verified against files fetched 2026-06-19 (see
> Sources footer). The interesting twist here is that the vendored library is
> NOT pristine upstream hashids.c — it has been patched to allocate through
> PG's memory contexts.

---

## Domain & purpose

pg_hashids turns integers into short, reversible, obfuscated string ids — the
YouTube-video-id style (`347` → `"yr8"`) — so primary keys can be hidden behind
opaque public tokens. "Hashids is a small open-source library that generates
short, unique, non-sequential ids from numbers... You can use hashids to hide
primary keys in your database" (`README.md:4-8`) `[from-README]`. The mapping is
deterministic and exactly invertible given the same `salt` / `min_hash_length` /
`alphabet` parameters (`README.md:104`) `[from-README]`. It is callable from SQL
as `id_encode(bigint[, salt[, min_length[, alphabet]]])` (and a `bigint[]`
overload) plus `id_decode` / `id_decode_once` (`pg_hashids--1.3.sql:14-48`)
`[verified-by-code]`. Despite the name, the algorithm is **not a hash** in the
cryptographic sense — it is a reversible, salt-keyed permutation cipher over a
custom alphabet; the README/upstream both warn it is obfuscation, not security.

---

## How it hooks into PG

A minimal lazy-loaded function extension — no `_PG_init`, no GUCs, no hooks, no
custom types, no catalog rows beyond the `CREATE FUNCTION` set:

- **Control file** `pg_hashids.control`: `default_version = '1.3'`,
  `module_pathname = '$libdir/pg_hashids'`, `relocatable = true`, comment
  `'pg_hashids'` (`pg_hashids.control:1-4`) `[verified-by-code]`. `relocatable =
  true` is honest here — the extension creates only schema-agnostic functions,
  so it can live in any schema. See [[catalog-conventions]].
- **Module magic** only: bare `PG_MODULE_MAGIC` guarded by `#ifdef`
  (`pg_hashids.c:11-13`) `[verified-by-code]`. There is **no `_PG_init`** —
  these are pure functions, nothing to initialize at load time. Contrast the
  GUC-registering `_PG_init` in [[uuidv47]] / [[pgsql-http]].
- **SQL-callable C functions** via `PG_FUNCTION_INFO_V1`: `id_encode`,
  `id_encode_array`, `id_decode`, `id_decode_once` (`pg_hashids.c:15-18`)
  `[verified-by-code]`. Args are pulled with `PG_GETARG_INT64` /
  `PG_GETARG_TEXT_P` / `PG_GETARG_INT32` / `PG_GETARG_ARRAYTYPE_P`, returns via
  `PG_RETURN_TEXT_P` / `PG_RETURN_ARRAYTYPE_P` / `PG_RETURN_INT64`
  (`pg_hashids.c:73-96, 113-144, 189, 226`) `[verified-by-code]`. See [[fmgr-and-spi]].
- **Variadic-by-overload**: rather than a SQL `VARIADIC` signature, the install
  SQL declares four C-language overloads per operation (arity 1-4) all bound to
  the *same* C symbol, and the C function branches on `PG_NARGS()`
  (`pg_hashids--1.3.sql:14-48`; `pg_hashids.c:75-84`) `[verified-by-code]`.
- **Install SQL** uses `CREATE OR REPLACE FUNCTION ... LANGUAGE C IMMUTABLE
  STRICT` for every entry, with `'MODULE_PATHNAME', 'id_encode'` symbol binding
  (`pg_hashids--1.3.sql:4-48`) `[verified-by-code]`. It also keeps the legacy
  v1 `hash_encode` / `hash_decode` names as aliases to the same symbols
  (`pg_hashids--1.3.sql:4-11`) `[verified-by-code]`.
- **Build**: `MODULE_big = pg_hashids`, `OBJS = pg_hashids.o hashids.o`, plain
  PGXS (`Makefile:1-2,12`) `[verified-by-code]` — the vendored library is
  compiled into the same `.so`, not linked as an external shared lib.
- **The algorithm is a vendored standalone C library** (`hashids.c` /
  `hashids.h`) that descends from upstream tzvetkoff/hashids.c
  (`README.md:12`) `[from-README]`. In its pristine form that library knows
  nothing about Postgres — see the divergence section for how pg_hashids bridges
  it.

---

## Where it diverges from core idioms

### 1. The vendored allocator is patched to palloc — the malloc→palloc bridge lives *inside* the library, not at the call boundary

The headline. Upstream hashids.c uses raw `malloc`/`free` through indirection
pointers. In this vendored copy the library `#include "postgres.h"`
(`hashids.c:8`) and its default allocator implementations are **rewritten to
call PG's context allocator** (`hashids.c:45-60`) `[verified-by-code]`:

```c
static inline void *
hashids_alloc_f(size_t size)
{
    return palloc0(size);
}
static inline void
hashids_free_f(void *ptr)
{
    pfree(ptr);
}
void *(*_hashids_alloc)(size_t size) = hashids_alloc_f;
void (*_hashids_free)(void *ptr)     = hashids_free_f;
```

Every internal allocation in the library — the `hashids_t` struct, the alphabet
copies, salt, separators, guards, and the temporary decode buffers — goes
through `_hashids_alloc` / `_hashids_free` (`hashids.c:232,240,269,285,352,
376-378,449,634,828,861` allocate; `:199-217,464,649,836-846,874-880` free)
`[verified-by-code]`. So the standalone library's allocations land in
`CurrentMemoryContext` (the per-call / per-query context) rather than the C heap.
This is the *opposite* of what one might assume of a vendored third-party lib,
and it is a cleaner bridge than [[pgsql-http]]'s (which keeps libcurl's internal
allocations on the C heap and only funnels the response body into a
StringInfo). See [[memory-contexts]].

Consequence for error safety: because the library allocates in a MemoryContext,
a mid-operation `ereport(ERROR)` longjmp does **not** leak the library's
buffers — the per-query context reset reclaims them. The explicit
`hashids_free(hashids); pfree(hash);` calls in `id_encode` etc.
(`pg_hashids.c:93-94,141-142,180-181,223-224`) `[verified-by-code]` are
belt-and-suspenders for the long-lived-backend case, not a correctness
requirement on the error path. `[inferred]` (from palloc-context semantics +
the visible call sites).

> Caveat: a `pfree` of a `palloc0` chunk is fine, but the upstream library's
> internal `realloc`-style growth (if any) would not have a palloc analogue;
> the fetched `hashids.c` shows only fixed-size `_hashids_alloc` calls, no
> realloc, so the bridge is complete for this code path. `[verified-by-code]`
> (grep of `hid_hashids.c`: no `realloc`).

### 2. IMMUTABLE is *honest* here — output depends only on arguments, not on session state

Every function is declared `IMMUTABLE STRICT` (`pg_hashids--1.3.sql:4-48`)
`[verified-by-code]`, and unlike many extensions this is **correct**. The
salt, minimum length, and alphabet are passed as ordinary function arguments
(`pg_hashids.c:75-84`) `[verified-by-code]`, so the output is a pure function of
the inputs — there is no GUC, no `_PG_init` state, no clock, no randomness in
the encode path. This is the clean contrast case to [[uuidv47]] (whose output
function reads `uuid47.key` from a GUC and can even `ERROR` when unset, making
its declared immutability a lie) and to [[zson]] (whose dictionary-keyed
encoding depends on catalog/session state). pg_hashids is the corpus's example
of an extension where the IMMUTABLE label is *load-bearing and truthful*: the
planner is free to constant-fold `id_encode(1001)` and that is exactly right.
`[inferred]` from PG volatility semantics + the all-args-no-state design.

### 3. Error handling — library errno translated into SQLSTATE-bearing ereport

The library keeps a thread-local `hashids_errno` (via the
`__hashids_errno_addr()` indirection, `hashids.c:37-43`) `[verified-by-code]`
set at each failure site (`hashids.c:234,258,263,272,...,875`)
`[verified-by-code]`. pg_hashids checks the NULL return from `hashids_init*`
and dispatches `hashids_error()`, a switch that maps each errno to an
`ereport(ERROR, ...)` with a chosen SQLSTATE (`pg_hashids.c:20-41`)
`[verified-by-code]`:

- `HASHIDS_ERROR_ALLOC` → `ERRCODE_OUT_OF_MEMORY`
- `HASHIDS_ERROR_ALPHABET_LENGTH` → `ERRCODE_INVALID_PARAMETER_VALUE`
  ("alphabet is too short")
- `HASHIDS_ERROR_ALPHABET_SPACE` → `ERRCODE_INVALID_PARAMETER_VALUE`
  ("alphabet contains whitespace characters")
- `HASHIDS_ERROR_INVALID_HASH` → `ERRCODE_INVALID_PARAMETER_VALUE`
- default → `ERRCODE_EXTERNAL_ROUTINE_EXCEPTION` ("unknown error")

This is idiomatic [[error-handling]] — a third-party errno funneled into the
backend's `ereport`/SQLSTATE contract. The alphabet rules come from the library:
min length 16 (`HASHIDS_MIN_ALPHABET_LENGTH 16u`, `hashids.h:13`), and the
length/whitespace checks at `hashids.c:256-265` `[verified-by-code]`.
Decode failure is signalled by `hashids_numbers_count(...) == 0`, which the C
wrapper turns into the same `hashids_error()` path (`pg_hashids.c:172-175,
216-219`) `[verified-by-code]`.

### 4. Hand-rolled ArrayType construction borrowed from contrib/intarray

`id_decode` returns a `bigint[]`. Instead of `construct_array`, it builds the
`ArrayType` by hand — `new_intArrayType` palloc0's the header+data, sets
`ARR_NDIM`, `ARR_ELEMTYPE = INT8OID`, dims and lbound directly
(`pg_hashids.c:44-59`) `[verified-by-code]`, with a comment crediting
`contrib/intarray/_int_tool.c` (`pg_hashids.c:43`) `[verified-by-code]`. The
decoded values are `memcpy`'d into the array's data region
(`pg_hashids.c:183-185`) `[verified-by-code]`. This is a lower-level idiom than
most extensions reach for, copied from in-tree contrib.

### 5. Signedness reinterpretation: int64 ↔ unsigned long long, no range check

The library speaks `unsigned long long`; SQL speaks signed `int64`. The wrapper
reinterprets via raw casts at every boundary — `(unsigned long long) number` on
encode (`pg_hashids.c:90`), `(unsigned long long *) &number` /
`(unsigned long long *) numbers` on decode (`pg_hashids.c:178,221`), and even
`(unsigned long long *) ARR_DATA_PTR(numbers)` to feed the int64 array elements
straight into the library (`pg_hashids.c:137-138`) `[verified-by-code]`. There
is no check that a value is non-negative or in range; a negative `bigint`
reinterprets as a large unsigned value. `[inferred]` from the cast sites +
absence of any range guard. The `bigint[]` encode path also pre-rejects NULL
elements with `array_contains_nulls` → `ERRCODE_NULL_VALUE_NOT_ALLOWED`
(`pg_hashids.c:116-121`) `[verified-by-code]`, but does not validate the array
is 1-dimensional before indexing `ARR_DIMS(numbers)[0]` (`pg_hashids.c:114`)
`[verified-by-code]`.

### 6. Re-initializes the cipher on every call — no caching of hashids_t

Each `id_encode` / `id_decode` call runs `hashids_init*` from scratch (which
allocates and consistent-shuffles the alphabet, separators, and guards) and
frees it before returning (`pg_hashids.c:75-93`) `[verified-by-code]`. There is
no per-backend cache of the configured `hashids_t` keyed on salt/alphabet — so a
query encoding a million rows pays the setup cost a million times. This is a
deliberate simplicity choice consistent with IMMUTABLE purity (no static
mutable state to cache), but contrasts with extensions that memoize expensive
per-config setup. `[inferred]` from the per-call init/free pairing.

---

## Notable design decisions (with cites)

- **Vendored library patched to allocate via palloc0/pfree** through the
  `_hashids_alloc` / `_hashids_free` function pointers, so all library memory
  lives in PG MemoryContexts (`hashids.c:8,45-60`) `[verified-by-code]`. The
  single most interesting deviation from "vendor it pristine."
- **No `_PG_init`, no GUC, no hooks** — bare `PG_MODULE_MAGIC` and four
  `PG_FUNCTION_INFO_V1` functions (`pg_hashids.c:11-18`) `[verified-by-code]`.
- **All functions IMMUTABLE STRICT and genuinely so** — config passed as args,
  no hidden state (`pg_hashids--1.3.sql:4-48`; `pg_hashids.c:75-84`)
  `[verified-by-code]`.
- **Four C-overloads per op, dispatched on `PG_NARGS()`** instead of SQL
  VARIADIC (`pg_hashids--1.3.sql:14-48`; `pg_hashids.c:75-84`)
  `[verified-by-code]`.
- **Hand-built ArrayType** cribbed from `contrib/intarray`
  (`pg_hashids.c:43-59`) `[verified-by-code]`.
- **Library errno → SQLSTATE switch** in `hashids_error()`
  (`pg_hashids.c:20-41`) `[verified-by-code]`.
- **Legacy `hash_encode`/`hash_decode` names retained** as aliases for the same
  C symbols across the upgrade chain (`pg_hashids--1.3.sql:4-11`)
  `[verified-by-code]`.
- **Thread-local `hashids_errno`** via `__hashids_errno_addr()` indirection in
  the library (`hashids.c:37-43`; `hashids.h:43-45`) `[verified-by-code]` —
  harmless under PG's one-backend-per-process model, vestigial from the
  library's multi-threaded heritage.

---

## Links into corpus

- [[fmgr-and-spi]] — `PG_FUNCTION_INFO_V1`, `PG_GETARG_*` / `PG_RETURN_*`,
  `PG_NARGS()` overload dispatch, hand-built `ArrayType` return.
- [[memory-contexts]] — the malloc↔palloc bridge: the vendored library's
  allocator function pointers rewritten to `palloc0`/`pfree`, so a longjmp on
  `ereport(ERROR)` cannot leak library state.
- [[error-handling]] — `hashids_errno` translated into `ereport(ERROR)` with
  per-case SQLSTATE selection.
- [[catalog-conventions]] — `relocatable = true` control file, `CREATE OR
  REPLACE FUNCTION ... LANGUAGE C IMMUTABLE STRICT` install SQL, legacy-name
  aliasing across upgrade scripts.
- Sibling ideologies: [[uuidv47]] (the *dishonest*-IMMUTABLE contrast — output
  depends on a session GUC and can throw), [[zson]] (encoding keyed on
  catalog/session state, contra pg_hashids' pure-args design),
  [[postgresql-hll]] (another small algorithm-in-C-vendored-into-an-`.so`
  extension), [[pgsql-http]] (a *different* memory bridge — body into StringInfo
  while keeping the lib's own allocations on the C heap).

> Corpus gap: there is still no dedicated `idioms/sql-function-volatility.md`
> (flagged by [[pgsql-http]] too). pg_hashids is the canonical *correct*
> IMMUTABLE case and would be the positive exemplar in such a doc, paired with
> uuidv47/zson as the cautionary ones. `[inferred]`

---

## Sources

Fetched 2026-06-19 (branch `master`, tree SHA `8c404dd`):

- `https://api.github.com/repos/iCyberon/pg_hashids/git/trees/master?recursive=1`
  — HTTP 200 (tree enumerated; manifest hint `pg_hashids--*.sql` resolved to
  `pg_hashids--1.3.sql`, the control file's `default_version`; `.control.in`
  does not exist — the repo ships a plain `pg_hashids.control`).
- `https://raw.githubusercontent.com/iCyberon/pg_hashids/master/README.md`
  — HTTP 200 (3509 bytes; purpose, usage, upstream-lib attribution).
- `.../master/pg_hashids.c` — HTTP 200 (5844 bytes; deep-read — all four entry
  points, error switch, ArrayType builder).
- `.../master/pg_hashids.control` — HTTP 200 (105 bytes).
- `.../master/hashids.c` — HTTP 200 (26589 bytes; read the allocator bridge,
  init, errno set-sites, free paths; algorithm internals skimmed not audited).
- `.../master/hashids.h` — HTTP 200 (3110 bytes; struct, error codes, alloc/
  errno indirection, API surface).
- `.../master/pg_hashids--1.3.sql` — HTTP 200 (2798 bytes; full function DDL +
  legacy aliases).
- `.../master/Makefile` — HTTP 200 (PGXS; `OBJS = pg_hashids.o hashids.o`).
- `.../master/sql/pg_hashids.sql` — HTTP 200 (974 bytes; regression input,
  skimmed for expected values).

All cites are `[verified-by-code]` against the fetched files except: the
algorithm-is-reversible-not-cryptographic and primary-key-hiding motivation
(`[from-README]`); the error-path-no-leak reasoning, the int64/ull
signedness-reinterpretation hazard, the no-per-call-cache cost note, and the
IMMUTABLE-is-correct judgement (`[inferred]` from palloc-context + volatility
semantics + the visible call sites). The library's algorithm internals
(shuffle, encode/decode loops) were skimmed for the allocator/errno surface,
not audited line-by-line.
