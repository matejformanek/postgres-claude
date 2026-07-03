# pg-libphonenumber — a C++ extension defining a `packed_phone_number` base type over Google libphonenumber, with a 64-bit packed on-disk representation and parse-on-input validation

> Headline: where most type-defining PG extensions are C, pg-libphonenumber is
> **C++** — it wraps Google's libphonenumber (itself C++/protobuf) behind an
> `extern "C"` fmgr boundary, parses/validates the number at input time, and
> stores it as a **fixed 8-byte struct bit-packed** with country code, national
> number, and leading-zero count. The ideological interest is threefold: the
> C++↔C linkage dance, converting C++ exceptions (`std::runtime_error`,
> `std::bad_alloc`) into `ereport(ERROR)` **before** longjmp unwinds, and a
> packed fixed-length by-reference type (not varlena) whose btree ordering is a
> deliberate heuristic rather than a true phone ordering.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `blm768/pg-libphonenumber` @ branch `master` (96★, C++), fetched
> 2026-07-03. All `file:line` cites point into that repo, **not** `source/`.
> Caveat: fetched via `raw.githubusercontent.com` only (GitHub API tree,
> codeload tarballs, and github.com HTML all return 403 — the `src/` directory
> could not be listed). The Makefile compiles `src/*.cpp` by wildcard
> (`Makefile:10`), so file names were resolved by probing. Files read:
> `README.md`, `Makefile`, `pg_libphonenumber.control`,
> `sql/pg_libphonenumber--0.1.0.sql`, `src/pg_libphonenumber.cpp`,
> `src/packed_phone_number.h`, `src/packed_phone_number.cpp`,
> `src/error_handling.{h,cpp}`, `src/mask.h`. Probed-and-404: `src/phone_number.*`,
> `src/short_phone_number.*`, `src/mask.cpp`, `sql/pg_libphonenumber--0.0.1.sql`
> (see Sources). The extension self-describes as **alpha / partially
> implemented** (`README.md:3,8-10`) `[from-README]` — several code paths carry
> `TODO`s that this note calls out.

---

## Domain & purpose

pg-libphonenumber adds a first-class `packed_phone_number` SQL type backed by
"[Google's `libphonenumber`]" (`README.md:1-4`) `[from-README]`. The workflow is
parse-then-store: `SELECT parse_packed_phone_number('03 7010 1234', 'AU')`
validates and packs a number for a given region, and a table can declare a
`packed_phone_number` column directly (`README.md:14-20`) `[from-README]`. The
value is not the raw text — it is a normalized, validated phone number reduced
to an 8-byte integer, so equality, ordering (btree), and country-code extraction
work on the parsed structure rather than on string form. The extension depends
on the system `libphonenumber-dev` C++ library at build time
(`README.md:26-33`) `[from-README]`; it is explicitly alpha and "not complete or
tested enough for critical production deployments" (`README.md:8-10`)
`[from-README]`.

---

## How it hooks into PG

A textbook base-type registration, but every C entry point is a C++ function
exported through `extern "C"`:

- **Shell type then flesh it out.** The install SQL first declares the shell
  `CREATE TYPE packed_phone_number;` (`sql/pg_libphonenumber--0.1.0.sql:8`),
  defines the four I/O functions, then the full `CREATE TYPE` with
  `INTERNALLENGTH = 8, INPUT/OUTPUT/RECEIVE/SEND, ALIGNMENT = double, STORAGE =
  plain` (`…--0.1.0.sql:10-34`) `[verified-by-code]`. This is a **fixed-length,
  pass-by-reference** type (not varlena — `INTERNALLENGTH = 8` is a byte count,
  and the C functions traffic in `PG_RETURN_POINTER` / `PG_GETARG_POINTER`,
  `src/pg_libphonenumber.cpp:91,106`), so `STORAGE = plain` and no TOASTing.
  Contrast [[pg_roaringbitmap]] (a true varlena). See [[catalog-conventions]].
- **I/O + binary I/O.** `packed_phone_number_in/out` (cstring↔type) and
  `packed_phone_number_recv/send` (internal↔bytea) are all
  `PG_FUNCTION_INFO_V1` C-language functions bound to the same `.so`
  (`…--0.1.0.sql:10-24`; `src/pg_libphonenumber.cpp:81-165`) `[verified-by-code]`.
  See [[fmgr]].
- **INOUT cast to text.** `CREATE CAST (packed_phone_number AS text) WITH INOUT`
  reuses the output function for text conversion (`…--0.1.0.sql:38-39`)
  `[verified-by-code]`.
- **Full comparison operator family + btree opclass.** `=`, `<>`, `<`, `<=`,
  `>`, `>=` each map to a `PG_FUNCTION_INFO_V1` boolean function, and a
  `packed_phone_number_cmp` support function backs a **default btree opclass**
  `packed_phone_number_ops` (`…--0.1.0.sql:43-140`) `[verified-by-code]`. So the
  type is indexable and sortable. The `=` operator declares `hashes = true,
  merges = true` (`…--0.1.0.sql:55-56`) `[verified-by-code]` — but **no hash
  opclass is defined**, only btree, so hash joins/aggregates can't actually use
  the type despite the `hashes` claim. `[inferred]`
- **Constructor + accessor.** `parse_packed_phone_number(text, text)` (number,
  region) is the public constructor, and `phone_number_country_code(...)`
  extracts the country code as `integer` (`…--0.1.0.sql:144-154`)
  `[verified-by-code]`.
- **Every SQL function is `IMMUTABLE STRICT`** (`…--0.1.0.sql:11,15,…`)
  `[verified-by-code]`. STRICT is honest (NULL args short-circuit). IMMUTABLE is
  *mostly* honest — parsing is deterministic — with one wrinkle: the input
  function hard-codes region `"US"` (below), so `'2819010011'::packed_phone_number`
  depends on nothing but its bytes, but semantics differ from the region-aware
  constructor.
- **Build**: `MODULE_big = pg_libphonenumber`, `OBJS` = every `src/*.cpp`
  (wildcard), `PG_CPPFLAGS = -fPIC -std=c++14`, and crucially
  `SHLIB_LINK = -lphonenumber -lstdc++` — the C++ standard library and
  libphonenumber are linked as **external shared libraries**, not vendored
  (`Makefile:10-27`) `[verified-by-code]`. Plain PGXS otherwise (`Makefile:31-32`).
- **Control file**: `relocatable = true`, `default_version = '0.1.0'`,
  `encoding = 'utf-8'` (`pg_libphonenumber.control:1-3`) `[verified-by-code]`.

---

## Where it diverges from core idioms

### 1. C++ across the fmgr boundary — `extern "C"`, `PGDLLEXPORT`, and where `PG_MODULE_MAGIC` lives

Every backend-visible symbol is defined inside a single `extern "C" { … }` block
so the C++ compiler does **not** name-mangle it — the SQL `CREATE FUNCTION … AS
'pg_libphonenumber', 'packed_phone_number_in'` lookup needs the unmangled symbol
(`src/pg_libphonenumber.cpp:72-328`) `[verified-by-code]`. Each entry point is
also marked `PGDLLEXPORT` and declared with `PG_FUNCTION_INFO_V1` immediately
before its `Datum foo(PG_FUNCTION_ARGS)` body (`src/pg_libphonenumber.cpp:81-84,
101-104,…`) `[verified-by-code]`. `PG_MODULE_MAGIC` itself sits **inside** the
`extern "C"` block (`src/pg_libphonenumber.cpp:72-75`) `[verified-by-code]`,
because the magic block is a C symbol the loader dlsym's by name.

The reverse direction matters too: PG's own headers are C, so they are pulled in
under `extern "C"` — `extern "C" { #include "postgres.h" #include
"libpq/pqformat.h" #include "fmgr.h" }` (`src/pg_libphonenumber.cpp:6-10`;
same pattern in `src/error_handling.cpp:8-10`) `[verified-by-code]`. C++
translation units include the phonenumber/protobuf C++ headers normally
(`src/pg_libphonenumber.cpp:4`) and only wrap the PG headers. See [[fmgr]].

### 2. C++ exception → `ereport` bridge: catch first, longjmp second

This is the headline correctness pattern, and pg-libphonenumber gets the
ordering right. PG errors are reported via `ereport(ERROR, …)`, which
`longjmp`s back to the nearest `PG_TRY`/subtransaction boundary — a longjmp that
would **skip C++ destructors** if it fired while C++ stack objects were live.
Every fmgr wrapper therefore wraps its whole body in a C++ `try { … } catch
(std::exception& e) { reportException(e); }` (`src/pg_libphonenumber.cpp:85-98,
105-128,174-185,…`) `[verified-by-code]`. Because the C++ `throw` unwinds all
C++ frames in the `try` body *before* control reaches the `catch`,
`reportException` runs on an already-unwound C++ stack — so its `ereport(ERROR)`
longjmp jumps over **no** live C++ destructors. This is the correct way to marry
C++ EH with PG's longjmp error model.

`reportException` is the dispatcher (`src/error_handling.cpp:55-80`)
`[verified-by-code]`: it `dynamic_cast`s the caught exception to pick a SQLSTATE —

- `std::bad_alloc` → `reportOutOfMemory()` → `ERRCODE_OUT_OF_MEMORY`
  (`error_handling.cpp:43-47,56-60`);
- `PhoneNumberTooLongException` → `ERRCODE_INVALID_TEXT_REPRESENTATION`, with the
  formatted number in `errmsg` and `exception.what()` in `errdetail`
  (`error_handling.cpp:62-72`);
- anything else → `ERRCODE_EXTERNAL_ROUTINE_INVOCATION_EXCEPTION` with
  `typeid(exception).name()` in the message (`error_handling.cpp:76-80`).

Parse failures don't come through exceptions at all: `Parse()` returns a
`PhoneNumberUtil::ErrorType` enum, dispatched by `reportParseError` into
`ERRCODE_INVALID_TEXT_REPRESENTATION` with a human message per error code
(`error_handling.cpp:82-87`; message table at `:16-37`) `[verified-by-code]`.
This is idiomatic [[error-handling]] — a foreign library's error taxonomy
funneled into the backend's SQLSTATE contract.

> Latent leak `[inferred]`: in the `PhoneNumberTooLongException` branch,
> `std::string phone_number = too_long->number_string();` is a live C++ object
> when `ereport(ERROR)` longjmps out of `reportException`
> (`error_handling.cpp:65-71`). That longjmp skips the `std::string`
> destructor, leaking its heap buffer (a `std::string`, not palloc'd). Small and
> per-error, but it is the one place the catch-first discipline is violated —
> because here the C++ object is created *after* the catch, inside the reporter.

### 3. Memory: palloc for the type instance, transient C++ objects on the C++ heap

The type instance that PG stores is always palloc'd: `do_parse_packed_phone_number`
does `palloc0(sizeof(PackedPhoneNumber))` then **placement-new**s the C++ object
into that PG-owned buffer — `new(short_number) PackedPhoneNumber(number)`
(`src/pg_libphonenumber.cpp:48-58`) `[verified-by-code]`. Because
`PackedPhoneNumber` is a trivial 8-byte value (just a `uint64_t _data`,
`packed_phone_number.h:113-114`) there is no destructor to run, so placement-new
into palloc memory is safe and never leaks. The output function likewise palloc's
the result cstring and `memcpy`s out of the C++ `std::string`, with an explicit
comment: "We must use the PostgreSQL allocator, not new/malloc"
(`src/pg_libphonenumber.cpp:112-122`) `[verified-by-code]`. The transient C++
objects (`std::string formatted`, the libphonenumber `PhoneNumber` message) live
on the C++ heap and are destroyed by normal C++ scope exit — they never become
PG-visible storage. See [[memory-contexts]].

Note the two `TODO: prevent leaks` markers: `parse_packed_phone_number` pfrees
its scratch cstrings but only on the success path — a thrown parse error longjmps
before the `pfree`s (`src/pg_libphonenumber.cpp:300-303`) `[verified-by-code]`.
Harmless in practice because the per-call memory context reclaims them, but the
author flagged it.

### 4. The packed on-disk format: 64-bit bit-field, not the parsed text

The stored representation is an 8-byte struct that bit-packs three fields into a
single `uint64_t`: **country code** (10 bits, offset 0), **leading-zero count**
(4 bits, offset 10), and **national number** (50 bits, offset 14)
(`src/packed_phone_number.h:43-53,113-114`) `[verified-by-code]`. Pack/unpack go
through `constexpr` bit-mask templates in `mask.h` (`get_masked` / `set_masked`,
`src/mask.h:7-26`) `[verified-by-code]`. A `static_assert(sizeof(PackedPhoneNumber)
== 8, …)` guards the layout so any accidental size change trips a compile error
and reminds the author to update the SQL `INTERNALLENGTH`
(`src/packed_phone_number.h:117-121`) `[verified-by-code]` — the C++ struct size
and the catalog `INTERNALLENGTH = 8` are two halves of one invariant. Validation
happens at pack time: the constructor throws `PhoneNumberTooLongException` if the
country code > 999, national number > 10¹⁵−1, or leading zeros > 15
(`src/packed_phone_number.cpp:19-42`) `[verified-by-code]` — so an out-of-range
number can never be stored, only rejected at input. Round-tripping back to a
libphonenumber `PhoneNumber` (for formatting) is an `operator PhoneNumber()`
conversion (`src/packed_phone_number.cpp:44-52`) `[verified-by-code]`.

### 5. btree ordering is a documented heuristic, and binary I/O is non-portable

`compare_fast` computes `other._data - this->_data` — a raw subtraction of the
packed 64-bit words, with the class comment warning it "may not produce intuitive
results for numbers with the same country code but different lengths"
(`src/packed_phone_number.h:68-81`) `[verified-by-code]`. `packed_phone_number_cmp`
clamps this to {−1,0,1} for the btree support function
(`src/pg_libphonenumber.cpp:275-277`) `[verified-by-code]`. So the index orders
by packed-integer layout, not by any semantic phone-number order — an explicit
speed-over-intuition tradeoff. Separately, `recv`/`send` do a **raw byte copy**
of the 8-byte struct (`pq_copymsgbytes` / `pq_sendbytes`), with a `TODO: make
portable (fix endianness issues, etc.)` (`src/pg_libphonenumber.cpp:139-140,
157-158`) `[verified-by-code]` — binary dumps are therefore not
architecture-portable. Contrast the byte-order care in [[portable-identifiers]].

---

## Notable design decisions

- **Base type registered by shell-then-full `CREATE TYPE`**, fixed-length 8-byte
  pass-by-reference, `ALIGNMENT = double`, `STORAGE = plain` — no varlena, no
  TOAST (`sql/pg_libphonenumber--0.1.0.sql:8,26-34`) `[verified-by-code]`.
- **Bit-packed 64-bit layout** (country 10b / leading-zeros 4b / national 50b)
  guarded by a `static_assert` tying the C++ struct size to the SQL
  `INTERNALLENGTH` (`src/packed_phone_number.h:43-53,117-121`) `[verified-by-code]`.
- **C++ exceptions caught at every fmgr boundary and converted to `ereport`
  after C++ unwinding**, via a `dynamic_cast` dispatcher choosing SQLSTATE
  (`src/pg_libphonenumber.cpp:85-98`; `src/error_handling.cpp:55-87`)
  `[verified-by-code]`.
- **`extern "C"` wraps both the exported entry points and the included PG
  headers**; `PG_MODULE_MAGIC` and `PG_FUNCTION_INFO_V1` sit inside the
  `extern "C"` block (`src/pg_libphonenumber.cpp:6-10,72-84`) `[verified-by-code]`.
- **libphonenumber + libstdc++ linked as external shared libs**, not vendored
  (`Makefile:27`) `[verified-by-code]` — the opposite of [[pg_hashids]]'s
  vendored-and-patched library.
- **PhoneNumberUtil singleton grabbed as a file-scope C++ global**
  (`static const PhoneNumberUtil* const phoneUtil = PhoneNumberUtil::GetInstance();`,
  `src/pg_libphonenumber.cpp:17`; also `src/packed_phone_number.cpp:6-8`,
  `src/error_handling.cpp` region) — a heavy C++ static constructor runs at `.so`
  load (`dlopen`) time. `[inferred]`
- **Full btree opclass but heuristic ordering**; `=` claims `hashes`/`merges`
  yet ships no hash opclass (`sql/pg_libphonenumber--0.1.0.sql:47-140`)
  `[verified-by-code]` / `[inferred]`.
- **Input function hard-codes region `"US"`** with a `TODO: use international
  format instead` (`src/pg_libphonenumber.cpp:88-89`) `[verified-by-code]` — the
  `::packed_phone_number` cast is US-biased; use `parse_packed_phone_number(text,
  text)` for region control.
- **Alpha / partial**: multiple `TODO`s (null-arg handling, number-validity
  checks, leak prevention, portability) mark unfinished edges
  (`src/pg_libphonenumber.cpp:63,66,139,301`) `[verified-by-code]`;
  `README.md:3,8-10` `[from-README]`. Vestigial naming: the header's
  `static_assert` comment and a probed-404 `src/short_phone_number.*` suggest the
  type was renamed `short_phone_number` → `packed_phone_number`
  (`src/packed_phone_number.h:117-119`) `[inferred]`.

---

## Links into corpus

- [[fmgr]] — `PG_FUNCTION_INFO_V1` / `PGDLLEXPORT` / `PG_GETARG_POINTER` /
  `PG_RETURN_POINTER` entry points, here all inside an `extern "C"` block so C++
  doesn't mangle them.
- [[error-handling]] — the C++-exception→`ereport(ERROR)` bridge with
  `dynamic_cast`-selected SQLSTATE, and the libphonenumber `ErrorType`→SQLSTATE
  table.
- [[memory-contexts]] — palloc0 + placement-new for the stored instance;
  transient `std::string` / protobuf objects kept on the C++ heap; the
  ereport-longjmp-skips-`std::string`-dtor leak.
- [[catalog-conventions]] — shell-type-then-full `CREATE TYPE`, fixed-length
  by-reference type, INOUT cast, operator family + btree opclass registration.
- [[portable-identifiers]] — the counter-example: `recv`/`send` do a raw,
  endianness-unsafe byte copy of the 8-byte struct.
- Sibling type-defining ideologies: [[pg_roaringbitmap]] (varlena type with
  operators + opclass — the by-value/varlena contrast to this fixed-length
  by-reference type), [[postgresql-unit]] (another compact scientific base type),
  [[pguri]] (a text-domain type wrapping a C parsing library),
  [[postgresql-hll]] (small-struct algorithm type), [[postgres-protobuf]] (the
  other protobuf-touching extension), [[pg_hashids]] (the vendored-library
  contrast — this extension links libphonenumber externally instead), [[uuidv47]]
  (identifier-transform type).

> Corpus gap: there is no dedicated `idioms/cpp-extension-boundary.md` covering
> the `extern "C"` linkage rules, name-mangling, the exception→ereport ordering
> discipline, and the `-lstdc++` link requirement. pg-libphonenumber is the
> cleanest exemplar of the "catch C++ exceptions first, then ereport" pattern and
> would anchor such a doc, paired with [[postgres-protobuf]]. `[inferred]`

---

## Sources

Fetched 2026-07-03, branch `master`, via `raw.githubusercontent.com` only (all
other GitHub endpoints 403; `src/` not listable — file names probed):

- `https://raw.githubusercontent.com/blm768/pg-libphonenumber/master/README.md` — HTTP 200.
- `.../master/Makefile` — HTTP 200 (PGXS; `src/*.cpp` wildcard; `-lphonenumber -lstdc++`).
- `.../master/pg_libphonenumber.control` — HTTP 200.
- `.../master/sql/pg_libphonenumber--0.1.0.sql` — HTTP 200 (full type + operator + opclass DDL).
- `.../master/src/pg_libphonenumber.cpp` — HTTP 200 (all fmgr wrappers; deep-read).
- `.../master/src/packed_phone_number.h` — HTTP 200 (class, bit layout, static_assert).
- `.../master/src/packed_phone_number.cpp` — HTTP 200 (constructor validation, PhoneNumber conversion).
- `.../master/src/error_handling.h` — HTTP 200.
- `.../master/src/error_handling.cpp` — HTTP 200 (exception dispatcher, parse-error table).
- `.../master/src/mask.h` — HTTP 200 (bit-mask templates).
- Probed-and-404 (do not exist at these paths): `.../src/short_phone_number.cpp`,
  `.../src/short_phone_number.h`, `.../src/phone_number.cpp`, `.../src/phone_number.h`,
  `.../src/mask.cpp`, `.../src/packed_phone_number_type.cpp`, `.../src/pg_functions.cpp`,
  `.../src/functions.cpp`, `.../src/main.cpp`, `.../sql/pg_libphonenumber--0.0.1.sql`,
  `.../meson.build`, `.../regression.sql`.

All cites `[verified-by-code]` against the fetched files except: the alpha-status
and libphonenumber-dependency framing (`[from-README]`); and the hash-opclass
absence, C++-static-constructor-at-load, `std::string`-dtor leak, US-region bias
consequence, and short→packed rename (`[inferred]` from the code + probe
results). libphonenumber's own parsing/formatting internals were treated as a
black box, not audited.
