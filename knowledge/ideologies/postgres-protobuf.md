# postgres-protobuf — libprotobuf's C++ runtime living inside a PG backend, exposed as SQL query functions

> Ideology note produced by the pg-extension-anthropologist cloud routine.
> Repo: `mpartel/postgres-protobuf` @ branch `master` (v0.3.3 per `Makefile`),
> fetched 2026-07-02.
> Caveat: characterization based on the files actually fetched —
> `postgres_protobuf.cpp`, `descriptor_db.{hpp,cpp}`, `postgres_utils.{hpp,cpp}`,
> `querying.hpp`, `postgres_protobuf_common.hpp`, the two install-SQL scripts,
> `postgres_protobuf.control`, `Makefile`, `README.md`. The 1341-line
> `querying.cpp` (the field-path interpreter) was fetched but only skimmed for
> its exception types; `build-protobuf-library.sh`, the `test_protos/`, and the
> Ruby `generate_test_cases.rb` harness were not fetched. `postgres_protobuf--0.1.sql`
> is the base install script (the control file's `default_version = '0.2'`).

## Domain & purpose

`postgres-protobuf` is a **data-extraction extension written in C++**: it lets
you keep Protocol Buffers serialized as `bytea` columns and pull fields out of
them from SQL, without ever unpacking them into relational columns. The user
loads a `protoc --descriptor_set_out` `FileDescriptorSet` into a table, then
calls `protobuf_query('MyProto:some.field', proto_col)` and friends to select
scalar fields, repeated elements, map values, or convert whole messages
to/from JSON [from-README] (`README.md:11-25`, `:80-110`). Its reason to exist
is the same as JSON-in-a-database — fewer schema migrations, structure-in-a-cell
— but with protobuf's compact wire format [from-README] (`README.md:27-34`).
It is the mirror image of `decoderbufs`, which *emits* protobuf from logical
decoding; this extension *parses* protobuf on the read path.

## How it hooks into PG

The extension is a **loadable module exposing six SQL-callable C functions** —
there are no planner/executor/utility hooks at all. It wires the C++ world into
PG's C fmgr through a disciplined `extern "C"` boundary.

- **fmgr entry points.** `PG_MODULE_MAGIC` and every
  `PG_FUNCTION_INFO_V1` / `Datum foo(PG_FUNCTION_ARGS)` are wrapped in
  `extern "C"` blocks so the C++ compiler emits C-linkage symbols the fmgr
  loader can find (`postgres_protobuf.cpp:38-42`, `:89-96`) [verified-by-code].
  The functions: `protobuf_query`, `protobuf_query_array`,
  `protobuf_query_multi` (an SRF), `protobuf_to_json_text`,
  `protobuf_from_json_text`, `protobuf_extension_version`
  (`postgres_protobuf.cpp:91-96`) [verified-by-code].
- **Include-order dance.** protobuf's own headers are included *first*, then the
  PG headers inside a second `extern "C"` block, with the comment "Must be
  included before other Postgres headers" (`postgres_protobuf.cpp:6-21`)
  [verified-by-code]. `postgres_utils.hpp` even forward-declares `pfree` by hand
  rather than pull in `postgres.h`, "since it pollutes the namespace, causing
  problems with any protobuf includes that come after it"
  (`postgres_utils.hpp:13-17`) [from-comment].
- **Packaging.** Real `CREATE EXTENSION postgres_protobuf` with a `.control`
  (`relocatable = true`, `default_version = '0.2'`) and versioned SQL scripts
  (`postgres_protobuf.control:1-4`) [verified-by-code]. Build is `MODULE_big`
  PGXS, statically linking `libprotobuf.a` via
  `-Wl,--whole-archive … -lstdc++` — the entire C++ protobuf runtime is baked
  into the `.so` (`Makefile:MODULE_big`, `:PG_LDFLAGS`) [verified-by-code].
- **SRF mechanics.** `protobuf_query_multi` uses the standard
  `SRF_IS_FIRSTCALL` / `SRF_FIRSTCALL_INIT` / `multi_call_memory_ctx` /
  `SRF_RETURN_NEXT` value-per-call idiom, stashing a C++ `MultiQueryState`
  object in `funcctx->user_fctx` (`postgres_protobuf.cpp:207-252`)
  [verified-by-code].

### Core mechanism — descriptors in a user table, cached per-transaction

Protobuf `.proto` schemas are something core PG has no concept of, so the
extension invents its own catalog: an ordinary table
`protobuf_file_descriptor_sets (name TEXT PK, file_descriptor_set BYTEA)`
created by the install script and marked
`pg_extension_config_dump(...)` so `pg_dump` carries the schema blobs
(`postgres_protobuf--0.1.sql:45-50`) [verified-by-code]. On first query in a
transaction, `DescDb::GetOrCreateCached` opens **SPI**, runs
`SELECT name, file_descriptor_set FROM protobuf_file_descriptor_sets`, parses
each blob into a libprotobuf `SimpleDescriptorDatabase` + `DescriptorPool` +
`TypeResolver`, and caches it in a C++ `static shared_ptr`
(`descriptor_db.cpp:24-132`, `:146-150`) [verified-by-code]. The cache is torn
down at transaction end via a `MemoryContextRegisterResetCallback` on
`CurTransactionContext` (`descriptor_db.cpp:118-128`, `:144`) [verified-by-code]
— which is why the README warns the descriptor cache lives only for one
transaction and advises wrapping many SELECTs in one (`README.md:143-144`)
[from-README]. Because query functions read this table they are declared
`STABLE`, not `IMMUTABLE`, and therefore cannot be used in index expressions
(`postgres_protobuf--0.1.sql:9-11`, `README.md:146-149`) [verified-by-code].

## Where it diverges from core idioms

- **C++ exceptions vs PG's longjmp, bridged by hand.** Every fmgr entry point
  wraps its body in a `try { … }` with a cascade of `catch` clauses that
  translate C++ exceptions into `ereport(ERROR, …)`:
  `std::bad_alloc` → `ERRCODE_OUT_OF_MEMORY`, `BadProto` →
  `ERRCODE_INVALID_BINARY_REPRESENTATION`, `BadQuery` →
  `ERRCODE_INVALID_PARAMETER_VALUE`, `RecursionDepthExceeded` →
  `ERRCODE_PROGRAM_LIMIT_EXCEEDED`, and a final `catch (...)` →
  `ERRCODE_INTERNAL_ERROR` "unknown C++ exception"
  (`postgres_protobuf.cpp:107-149`) [verified-by-code]. This is the load-bearing
  divergence: a C++ exception must **never** cross the C fmgr frame (it would
  bypass PG's error stack), and PG's `ereport(ERROR)` `longjmp` must never fire
  while a C++ stack with live destructors is unwound (it would skip them). The
  `ereport` calls are all issued from *inside* the `catch` blocks, i.e. after
  the C++ stack has already unwound, so the two error models never interleave
  [inferred].
- **The "no PG ops while C++ objects are live" bracket.** `GetOrCreateCached`
  is written in two explicit phases with a comment boundary: first read *all*
  SPI rows into `pvector`s "before allocating anything on the C++ heap …
  because there may be a Postgres error while reading rows"; then, in a block
  annotated "No more Postgres operations, which may throw Postgres exceptions,
  are allowed," it constructs the RAII libprotobuf objects
  (`descriptor_db.cpp:46-51`, `:85-110`) [from-comment]. A PG `longjmp` in the
  second phase would leak the half-built C++ object graph.
- **STL allocation vs MemoryContexts — a partial reconciliation.** The extension
  ships a `PostgresAllocator<T>` STL allocator whose `allocate`/`deallocate`
  call `palloc0_or_throw_bad_alloc` / `pfree`, plus `pstring` / `pvector`
  aliases and a `pnew` that placement-constructs a C++ object into a `palloc`
  block (`postgres_utils.hpp:55-111`, `:31-41`) [verified-by-code].
  `palloc0_or_throw_bad_alloc` itself uses `palloc_extended(…, MCXT_ALLOC_NO_OOM)`
  and throws `std::bad_alloc` instead of letting PG `elog` fire — converting PG's
  OOM-longjmp contract into a C++ exception so RAII can clean up
  (`postgres_utils.cpp:21-27`) [verified-by-code].
- **…but libprotobuf itself escapes MemoryContexts entirely.** The parsed
  descriptor pools and message objects are allocated on the **default C++ heap**,
  not via `palloc`, "because the protobuf library does not support custom
  allocators" — the header carries a standing NOTE to that effect
  (`descriptor_db.hpp:19-23`, `README.md:152-160`) [from-comment]. So this
  memory "might not be properly accounted for by Postgres's memory management
  and monitoring systems" (`README.md:154-156`) [from-README]. The
  `PostgresAllocator` only tames the extension's *own* containers; the bulk
  allocation lives outside `MemoryContext` accounting — a direct violation of
  the "all backend memory flows through a context" core idiom [inferred].
- **A user-table catalog for schema core cannot model.** Core has no notion of
  a protobuf `.proto`; the extension stores `FileDescriptorSet` blobs in a
  regular table and reaches them through SPI on every cold query
  (`descriptor_db.cpp:31-44`) — cheaper to build than a real catalog, but it
  means schema lookup is a full-table SPI scan, cached only per-transaction
  [inferred].

## Notable design decisions

- **Static-link the whole protobuf runtime into the `.so`.**
  `-Wl,--whole-archive libprotobuf.a -Wl,--no-whole-archive -lz -lstdc++`
  avoids depending on a system libprotobuf ABI (`Makefile:PG_LDFLAGS`)
  [verified-by-code].
- **`_PG_fini` calls `pb::ShutdownProtobufLibrary()` and clears the cache** —
  an unusually thorough finalizer (most PG modules omit `_PG_fini`)
  (`postgres_protobuf.cpp:356-360`) [verified-by-code].
- **Transaction-scoped descriptor cache via reset callback**, with an inline
  TODO citing Tom Lane's `xmin`/`ctid` change-detection threads as the path to
  a longer-lived cache (`descriptor_db.cpp:112-128`) [from-comment].
- **`pg_extension_config_dump` on the descriptor table** so `pg_dump` preserves
  user-loaded schemas across dump/restore (`postgres_protobuf--0.1.sql:50`)
  [verified-by-code].
- **Query functions `STABLE` by deliberate choice**, trading away index-expression
  use for correctness against schema changes (`postgres_protobuf--0.1.sql:9-11`)
  [verified-by-code].
- **Self-acknowledged safety caveat.** The README flags that C++ + an untrusted
  protobuf/query is risky, and is unsure libprotobuf always cleans up after
  `bad_alloc` (`README.md:130-160`) [from-README].
- **Map values buffered before scanning** → an attacker with a recursive-map
  schema can blow memory; otherwise memory use is linear (`README.md:162-169`)
  [from-README].

## Links into corpus

- [[decoderbufs]] — the protobuf **output plugin** counterpart: it *emits*
  protobuf from logical decoding, where this extension *parses* protobuf on the
  read path. The natural contrast pair.
- [[plv8]] — another C++-runtime-inside-a-backend extension (the V8 engine),
  facing the same C++/C-fmgr and heap-vs-MemoryContext tension.
- [[postgresql-unit]] and [[pguri]] — C++-authored base-type / value extensions
  that also cross the `extern "C"` fmgr boundary, useful as lighter-weight
  comparison points for the exception-translation idiom.

## Sources

- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_protobuf.cpp`
  — HTTP 200. Primary: fmgr entry points, `extern "C"` boundary, exception→ereport
  translation, SRF, `_PG_fini`.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/descriptor_db.cpp`
  — HTTP 200. SPI descriptor load, per-transaction reset callback, C++/PG phase bracket.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/descriptor_db.hpp`
  — HTTP 200. `DescDb`/`DescSet` structs; the "outside PG memory management" NOTE.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_utils.hpp`
  — HTTP 200. `PostgresAllocator`, `pstring`/`pvector`, `pnew`/`pdelete`.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_utils.cpp`
  — HTTP 200. `palloc0_or_throw_bad_alloc` (MCXT_ALLOC_NO_OOM → `std::bad_alloc`).
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/querying.hpp`
  — HTTP 200. `BadQuery` / `RecursionDepthExceeded` exception types, `Query` API.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_protobuf_common.hpp`
  — HTTP 200. `BadProto` exception, `PGPROTO_DEBUG` macro.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_protobuf--0.1.sql`
  — HTTP 200. CREATE FUNCTION signatures, descriptor table, `pg_extension_config_dump`.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_protobuf--0.1--0.2.sql`
  — HTTP 200. Adds `protobuf_query_array`.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/postgres_protobuf.control`
  — HTTP 200. `relocatable`, `default_version = '0.2'`, `module_pathname`.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/Makefile`
  — HTTP 200. `MODULE_big` PGXS, static libprotobuf whole-archive link, C++17.
- `https://raw.githubusercontent.com/mpartel/postgres-protobuf/master/README.md`
  — HTTP 200. Purpose, usage, security/memory/performance caveats.
- `https://api.github.com/repos/mpartel/postgres-protobuf/git/trees/master?recursive=1`
  — HTTP 403 (GitHub API not enabled for this session). File set discovered by
  probing raw paths; `postgres_protobuf--1.0.sql`, `*.hpp`-only names, and
  several guessed `.cpp` names returned 404.
