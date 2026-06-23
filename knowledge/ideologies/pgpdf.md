# pgpdf — ideology / divergence-from-core notes

> Extension: `Florents-Tselai/pgpdf` @ `main` (control reports
> `default_version = '0.1.0'`, `module_pathname = '$libdir/pgpdf'`,
> `comment = 'pdf type'`, `relocatable = true`)
> `[verified-by-code: pgpdf.control:1-4]`. 224★, C (GPL-2, requires
> PostgreSQL ≥ 14.0 per META.json `[verified-by-code: META.json:13-18]`).
> One durable "how this diverges from core PG design" doc. All `file:line`
> cites point into the **pgpdf** tree (`pgpdf.c`, `pgpdf.control`,
> `sql/pgpdf--0.1.0.sql`, `Makefile`, `README.md`, `META.json`), **NOT**
> into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** read this against the other vendored-/system-C-library
> custom-type docs in the corpus — [[knowledge/ideologies/pguri]]
> (liburiparser: library `malloc`s outside any context, hand-`free` boundary
> that leaks on error), [[knowledge/ideologies/pg_roaringbitmap]] (CRoaring,
> which goes the *opposite* way — redirects the library's whole allocator
> into MemoryContext via `roaring_init_memory_hook`),
> [[knowledge/ideologies/uuidv47]] (a small parse-once-store-binary base
> type), and pgJQ (jq/oniguruma; the other "wrap a foreign parser as a
> custom type" sibling written this run). pgpdf sits at the *most extreme*
> end of the foreign-library-boundary spectrum: it links a **C++ document
> engine** (poppler) through a **GLib/GObject** C binding whose entire heap
> is invisible to PostgreSQL's MemoryContext, and its input function does
> **server-side filesystem I/O**. Those two facts drive every divergence
> below.

## Domain & purpose

pgpdf adds a single base type `pdf` plus a family of accessor functions that
extract text and metadata from PDF documents, so PDFs can be stored,
searched, and queried inside PostgreSQL "in an ACID-compliant way" rather
than via an external ingestion script `[from-README: README.md:1-37]`. The
headline ergonomic is a cast chain: `'/tmp/x.pdf'::pdf` reads the file and
validates it; `…::pdf::text` yields the full extracted plain text, which then
flows straight into stock PostgreSQL string functions, `LIKE`, full-text
search (`@@ to_tsquery(...)`), and `pg_trgm` similarity — the type is
deliberately a thin shim that *becomes text* so the rest of PG's text
machinery applies unchanged `[from-README: README.md:83-137]`.

The actual parsing is delegated wholesale to **poppler** (the freedesktop PDF
library), reached through its GObject/GLib binding `poppler-glib`
`[from-README: README.md:37; verified-by-code: pgpdf.c:9, Makefile:12-14]`.
Poppler is **not vendored** — it is a system shared library resolved at build
time by `pkg-config` and linked with `-lpoppler -lpoppler-glib`
`[verified-by-code: Makefile:12-14]`; installation instructions tell the user
to `apt install libpoppler-glib-dev` or `brew install poppler`
`[from-README: README.md:276-289]`. This is the structural inverse of
[[knowledge/ideologies/pg_roaringbitmap]], whose CRoaring amalgamation is
committed in-tree. The extension's own C is ~360 lines of fmgr glue
`[verified-by-code: pgpdf.c:1-367]`; all the document logic lives in a
versionless external `.so`.

The anthropologically interesting decision is the **storage/identity split**:
the stored datum is the *raw, unparsed PDF byte stream* wrapped in a varlena,
but the type's text representation is the *parsed, extracted plaintext*. Input
and output are therefore **not inverses** (see divergence #2), and every
single accessor re-parses the entire document from scratch on each call (see
divergence #3).

## How it hooks into PG

- **`CREATE TYPE pdf`** as a variable-length base type: `INTERNALLENGTH = -1`,
  `INPUT = pdf_in`, `OUTPUT = pdf_out`, `STORAGE = extended`
  `[verified-by-code: sql/pgpdf--0.1.0.sql:17-23]`. The two-step
  shell-type-then-full-type idiom is used: `CREATE TYPE pdf;` (shell) →
  define `pdf_in`/`pdf_out` → `CREATE TYPE pdf (...)`
  `[verified-by-code: sql/pgpdf--0.1.0.sql:1, 3-15, 17-23]`. There are **no**
  `recv`/`send` binary I/O functions declared `[verified-by-code: absent from
  sql/pgpdf--0.1.0.sql]`.
- **The varlena itself is just bytes.** `typedef struct varlena pdftype;`
  — the type has no header beyond the standard varlena length word; the
  payload is the verbatim PDF file content
  `[verified-by-code: pgpdf.c:27]`. Detoast macros mirror the core pattern:
  `DatumGetPdfP`/`DatumGetPdfPP` over `PG_DETOAST_DATUM`(`_PACKED`)
  `[verified-by-code: pgpdf.c:29-35]`.
- **`pdf_in`** takes a `cstring` *filename*, reads the file off the server
  filesystem via `DirectFunctionCall1(pg_read_binary_file_all, …)`, copies
  the bytes into a fresh varlena, then parses once with poppler purely to
  **validate** (the parsed document is immediately `g_object_unref`'d and
  thrown away) `[verified-by-code: pgpdf.c:52-88]`. See divergence #1.
- **`pdf_out`** does *not* emit the stored bytes. It re-parses the document
  and concatenates `poppler_page_get_text()` across every page into a
  `StringInfo`, returning that plaintext as the cstring
  `[verified-by-code: pgpdf.c:90-123]`. See divergence #2.
- **Document-handle macro.** Every accessor begins
  `PopplerDocument* doc = PG_GETARG_POPPLER_DOCUMENT(0)`, a GCC
  statement-expression macro that detoasts the arg, wraps it in a `GBytes`,
  and calls `poppler_document_new_from_bytes(...)`, `elog(ERROR)`-ing on
  failure `[verified-by-code: pgpdf.c:37-48]`. So the parse happens *inside
  the argument macro*, once per call, in every function.
- **Metadata / text accessors.** `pdf_title`, `pdf_author`, `pdf_creator`,
  `pdf_keywords`, `pdf_metadata`, `pdf_version`, `pdf_subject` each call the
  matching `poppler_document_get_*()` and wrap the result with
  `cstring_to_text`, returning NULL when poppler returns NULL
  `[verified-by-code: pgpdf.c:126-215]`. `pdf_num_pages` returns
  `poppler_document_get_n_pages` `[verified-by-code: pgpdf.c:217-224]`;
  `pdf_page(pdf, int)` returns one page's text
  `[verified-by-code: pgpdf.c:227-236]`.
- **Date accessors.** `pdf_creation`/`pdf_modification` pull a `GDateTime`
  from poppler, decompose it into y/m/d/h/m/s GLib getters, and rebuild a PG
  timestamp via `DirectFunctionCall6(make_timestamp, …)`
  `[verified-by-code: pgpdf.c:238-302]`. (SQL declares the return as
  `TIMESTAMP` `[verified-by-code: sql/pgpdf--0.1.0.sql:94, 101]` while the C
  uses `PG_RETURN_TIMESTAMPTZ` `[verified-by-code: pgpdf.c:268, 301]` — a
  mismatch noted in #7.)
- **Casts.** Two text casts are declared `WITH INOUT AS ASSIGNMENT`
  (`pdf AS text`, `text AS pdf`) — routing through `pdf_out`/`pdf_in`
  `[verified-by-code: sql/pgpdf--0.1.0.sql:25-26]`. Two bytea casts are
  function-backed: `bytea AS pdf` via `bytea_to_pdf` (validates, copies),
  `pdf AS bytea` via `pdf_to_bytea` (raw copy of the stored bytes)
  `[verified-by-code: sql/pgpdf--0.1.0.sql:124-125; pgpdf.c:340-367,
  322-338]`. See #2 on why the `pdf→bytea→pdf` round-trip is lossless but
  `pdf→text→pdf` is not.
- **SQL convenience wrappers.** `pdf_read_file(text)` = `$1::pdf::text` and
  `pdf_read_bytes(bytea)` = `$1::bytea::pdf::text`, both `LANGUAGE SQL
  IMMUTABLE STRICT` `[verified-by-code: sql/pgpdf--0.1.0.sql:129-140]`.
- **No `_PG_init`, no GUC, no hooks.** The module defines only
  `PG_MODULE_MAGIC` `[verified-by-code: pgpdf.c:25]`; there is no
  `_PG_init`, no `DefineCustom*Variable`, no `shared_preload_libraries`
  requirement — plain `CREATE EXTENSION pgpdf;`
  `[verified-by-code: absent from pgpdf.c; from-README: README.md:299-303]`.
  Built with `MODULE_big` + PGXS `[verified-by-code: Makefile:6, 32-33]`.
- **All SQL functions are `IMMUTABLE STRICT`**
  `[verified-by-code: sql/pgpdf--0.1.0.sql:4-5, 31-122]` — including `pdf_in`,
  which is the load-bearing anomaly (#1): an input function marked IMMUTABLE
  whose result depends on the *current contents of a file on the server*.

## Where it diverges from core idioms

### 1. The input function reads the server filesystem — `pdf_in('/path')` does disk I/O, yet is marked IMMUTABLE

Core type input functions are pure: `text_in`, `int4in`, `numeric_in` map a
literal's bytes to a datum and touch nothing else. `pdf_in` instead treats its
cstring argument as a **filename** and slurps the file off the server's disk
via `DirectFunctionCall1(pg_read_binary_file_all, filename_t)`
`[verified-by-code: pgpdf.c:55, 64]`. So `'/tmp/x.pdf'::pdf` is not a literal
cast — it is a server-side file read executed with the privileges of the
`postgres` OS user, a fact the README explicitly warns about ("The filepath
should be accessible by the `postgres` process… That's different than the user
running psql") `[from-README: README.md:64-67]`. Two sharp consequences:

- **IMMUTABLE is a lie about a side-effecting read.** `pdf_in` is declared
  `IMMUTABLE STRICT` `[verified-by-code: sql/pgpdf--0.1.0.sql:3-5]`, which
  tells the planner the result depends only on the input value. But the input
  value is a *path*, and the bytes it resolves to can change (or the file can
  vanish) between calls. A correctly-`STABLE`-or-`VOLATILE` marking would
  defeat the constant-folding the cast relies on, so the extension takes the
  IMMUTABLE shortcut and inherits the classic file-read-as-pure footgun.
  `[verified-by-code]` for the marking; `[inferred]` for the planner
  consequence.
- **No `pg_read_server_files` role gate of its own.** It piggybacks on
  `pg_read_binary_file_all`'s permission model (superuser /
  `pg_read_server_files`) but surfaces it through a cast that *looks* like a
  pure string conversion `[inferred from pgpdf.c:64]`. The README's security
  warning (README.md:327-329) is the only guardrail.

This is the single most distinctive divergence: a base type whose **identity
is "a file on disk", established by an input function that performs
authenticated I/O.** No core type, and none of the vendored-lib sibling types
([[knowledge/ideologies/pguri]], [[knowledge/ideologies/pg_roaringbitmap]],
[[knowledge/ideologies/uuidv47]]), reads the filesystem in its `*_in`.

### 2. Input and output are not inverses — `pdf_out` returns extracted *text*, not the stored PDF

A core type's `out`∘`in` is the identity on representable values, and dump /
restore depends on it. pgpdf breaks this on purpose. The stored varlena holds
the **raw PDF bytes** `[verified-by-code: pgpdf.c:67-70, 27]`, but `pdf_out`
runs poppler over those bytes and returns the **concatenated page text**
`[verified-by-code: pgpdf.c:90-123]`. So:

- `'/tmp/x.pdf'::pdf::text` is plaintext extraction, by design
  `[from-README: README.md:83-137]`.
- `pdf_out` output can **never** be fed back through `pdf_in` (which expects a
  filename), so the type is **not dump/restore-safe via its text form.** A
  `COPY … TO`/`FROM` text round-trip would lose the document entirely.
  `[inferred]` from the in/out asymmetry — the README does not call this out.
- The lossless round-trip path is the **bytea** cast pair, not the text pair:
  `pdf_to_bytea` copies the stored bytes verbatim
  `[verified-by-code: pgpdf.c:322-338]` and `bytea_to_pdf` copies them back
  (after a validate-parse) `[verified-by-code: pgpdf.c:340-367]`. So binary
  dump (`pg_dump` default) survives; a text dump does not.

Treating `out` as "the useful projection of the value" rather than "the
reversible serialization" is the core idiom this extension most cleanly
inverts. It is what makes the `::pdf::text` ergonomic so clean and what makes
the type quietly text-dump-unsafe.

### 3. Every accessor re-parses the whole document from raw bytes — no cached parse

Because the stored form is the unparsed PDF, *every* function must reconstruct
a `PopplerDocument` before it can answer anything. The
`PG_GETARG_POPPLER_DOCUMENT` macro does exactly this on each call —
`g_bytes_new(VARDATA, …)` → `poppler_document_new_from_bytes(...)`
`[verified-by-code: pgpdf.c:37-48]` — and it is invoked at the top of
`pdf_out`, `pdf_title`, `pdf_author`, `pdf_num_pages`, `pdf_page`, and every
other accessor `[verified-by-code: pgpdf.c:95, 130, 143, 222, 232, 243, …]`.
Contrast [[knowledge/ideologies/pg_roaringbitmap]], which at least ships a
zero-deserialize buffer reader for the cheap paths; pgpdf has no such shortcut
— `SELECT pdf_num_pages(doc)` fully parses the PDF just to read a page count.
A query like `SELECT pdf_title(doc), pdf_author(doc), pdf_num_pages(doc) FROM
pdfs` parses each document **three times per row**. This is the cost of the
"store raw, parse on demand" choice (#1/#2): maximal storage fidelity and zero
parse state, paid for with repeated full re-parse on every access.
`[verified-by-code]` for the per-call parse; `[inferred]` for the
three-parses-per-row arithmetic.

### 4. Poppler's GLib/GObject heap lives entirely outside MemoryContext

This is the allocator-boundary divergence, and pgpdf sits at the **opposite
pole** from [[knowledge/ideologies/pg_roaringbitmap]]. CRoaring exposes a
`roaring_init_memory_hook` so its whole allocator can be redirected into
`palloc`; poppler/GLib exposes no such hook usable here, so **all** poppler and
GObject allocations (`PopplerDocument`, `PopplerPage`, the `GBytes` wrapper,
the `gchar*` page-text buffers, the `GDateTime`) come from GLib's own
`g_malloc`/GSlice heap, invisible to the current MemoryContext
`[verified-by-code: pgpdf.c:37-48, 72-85, 98-120, 244-256]`. The code
therefore must **manually pair every GLib allocation with its `g_*_unref` /
`g_free`**:

- `g_bytes_unref(g_bytes)` after the document is built
  `[verified-by-code: pgpdf.c:75, 364]`.
- `g_object_unref(doc)` / `g_object_unref(page)`
  `[verified-by-code: pgpdf.c:85, 119, 363]`.
- `g_free(page_text)` per page in `pdf_out`
  `[verified-by-code: pgpdf.c:108-113]`.
- `g_date_time_unref(dt)` in the date accessors
  `[verified-by-code: pgpdf.c:256, 289]`.

The boundary back into PG is `cstring_to_text` / `appendStringInfo` /
`makeStringInfo`, which copy the GLib-owned strings into palloc'd memory
`[verified-by-code: pgpdf.c:96, 111, 136]` — the standard "copy across the
allocator fence" move, same family as [[knowledge/ideologies/pguri]]'s
`pstrdup` of liburiparser output. The critical fragility: because GLib memory
is **not** context-reclaimed, any `ereport`/`elog(ERROR)` that fires while a
GLib object is live **leaks that object** for the lifetime of the backend (PG
unwinds the MemoryContext, but GLib's heap is untouched). See #5 for where
this actually bites. `[verified-by-code]` for the manual unref discipline;
`[inferred]` for the leak-on-longjmp consequence.

### 5. `elog(ERROR)` fires while GLib resources are held — longjmp leaks them, and one path is plain dead code

PG's `ereport(ERROR)` `longjmp`s out of the function; it does not return. The
parse macro embeds the error inside a GCC statement-expression:

```
PopplerDocument* doc = poppler_document_new_from_bytes(...);
if (!doc) { elog(ERROR, "...: %s", error->message); g_clear_error(&error); }
doc;
```
`[verified-by-code: pgpdf.c:41-47]`. The `g_clear_error(&error)` **after** the
`elog(ERROR)` is unreachable — control never returns from `elog(ERROR)` — so
the `GError` leaks on the parse-failure path. The same shape recurs in
`pdf_in`, where `pfree(result); g_clear_error(&error);` sit *after*
`elog(ERROR)` and never execute `[verified-by-code: pgpdf.c:77-83]`.
`bytea_to_pdf` does it more carefully — it `g_bytes_unref`s the `GBytes`
*before* calling `elog(ERROR)` `[verified-by-code: pgpdf.c:352-356]` — showing
the author knows the hazard, but the cleanup-after-error anti-pattern survives
in the two hottest paths. This is the canonical foreign-library × PG error
model mismatch: the library expects ordinary C return-and-cleanup, PG uses
`setjmp`/`longjmp`, and the two don't compose without putting **all** cleanup
*before* the `ereport`. Core code solves this with `PG_TRY/PG_CATCH`; pgpdf
uses neither, so a malformed PDF leaks the in-flight `GError` (and on some
paths the document) `[verified-by-code]` for the ordering; `[inferred]` for
the leak. See [[knowledge/idioms/error-handling]].

### 6. C++ document engine reached through a C/GObject shim — the language boundary is real but hidden

Poppler's core is **C++**; pgpdf never sees it. It includes only `poppler.h`
(the `poppler-glib` C binding) `[verified-by-code: pgpdf.c:9]` and links
`-lpoppler-glib` alongside `-lpoppler` `[verified-by-code: Makefile:14]`. The
GObject layer is what makes a C++ engine callable from PG's C without a C++
compiler or `extern "C"` wrappers in the extension itself — every object is an
opaque `Poppler*` handle manipulated through C functions and reference-counted
with `g_object_unref`. This is a cleaner story than a raw C++ link (no name
mangling, no exception-across-FFI concern at the extension boundary), but it
imports GLib's *entire* runtime — its allocator (#4), its `GError`
convention (#5), and its `GDateTime` type that must be hand-marshalled into a
PG timestamp field-by-field (#7) `[verified-by-code: pgpdf.c:244-268]`. The
C++-ness is invisible in the source but present in the link line and in the
fact that a C++ exception escaping poppler would cross an FFI boundary with no
PG-side handler. `[verified-by-code]` for the include/link; `[inferred]` for
the C++-exception exposure.

### 7. `STORAGE = extended` (double-compresses), plus a `TIMESTAMP`/`TIMESTAMPTZ` and a missing-NULL-check footgun

Three smaller divergences from core hygiene:

- **`STORAGE = extended`** `[verified-by-code: sql/pgpdf--0.1.0.sql:22]` is
  the varlena default: large values both TOAST out-of-line **and** get PGLZ
  compression. For PDFs this is a debatable choice — most PDFs already embed
  Flate-compressed streams, so PGLZ over them often spends CPU for little
  gain. This is the *opposite* of [[knowledge/ideologies/pg_roaringbitmap]]'s
  deliberate `STORAGE = external` ("don't double-compress an already-compressed
  payload"). pgpdf takes no such position. `[verified-by-code]` for the
  setting; `[inferred]` for the double-compression critique.
- **`TIMESTAMP` declared, `TIMESTAMPTZ` returned.** The SQL declares
  `pdf_creation`/`pdf_modification` as `RETURNS TIMESTAMP`
  `[verified-by-code: sql/pgpdf--0.1.0.sql:94, 101]` but the C returns via
  `PG_RETURN_TIMESTAMPTZ` after building the value with `make_timestamp`
  (which yields a *timestamp without time zone*)
  `[verified-by-code: pgpdf.c:258-268, 291-301]`. The Datum representations
  of `timestamp` and `timestamptz` are bit-identical (both int64 µs), so this
  does not crash, but the timezone semantics are muddled. `[verified-by-code]`
  for the mismatch; `[inferred]` for the harmless-but-wrong consequence.
- **`pdf_page` has no NULL/bounds guard.** It calls
  `poppler_document_get_page(doc, i)` and feeds the result straight into
  `poppler_page_get_text(page)` with no check — an out-of-range page index
  returns NULL and dereferences it `[verified-by-code: pgpdf.c:227-236]`,
  unlike `pdf_out` which checks `if (!page)` `[verified-by-code: pgpdf.c:102-106]`.
  A crash-on-bad-index footgun. `[verified-by-code]`.

## Notable design decisions (with cites)

- **"Read the file once."** The README's pitch is that ingestion reads the
  disk exactly once at insert time, after which the bytes live in the table
  `[from-README: README.md:61-62]`; `pdf_in` does precisely one
  `pg_read_binary_file_all` then stores `[verified-by-code: pgpdf.c:64-70]`.
- **Validate-on-ingest, discard the parse.** Both `pdf_in` and `bytea_to_pdf`
  parse the document purely to reject malformed input
  (`elog(ERROR, "Error parsing PDF document")`), then `g_object_unref` the
  parsed doc and store only the raw bytes
  `[verified-by-code: pgpdf.c:74-87, 352-363]` — so corrupt PDFs are caught at
  write time, but the parse work is thrown away (#3 re-does it on read).
- **Lean on text, ship almost no operators.** There is no `=`, no operator
  class, no aggregate, no index support of any kind in the install SQL
  `[verified-by-code: sql/pgpdf--0.1.0.sql, none present]`. The entire query
  surface is "cast to text, then use PG's text machinery" — FTS, `LIKE`,
  `pg_trgm` `[from-README: README.md:83-137]`. The type is a *loader*, not a
  queryable structure.
- **System library, not vendored.** poppler is a build-time `pkg-config`
  dependency `[verified-by-code: Makefile:12-14; from-README: README.md:276-289]`,
  so the extension inherits whatever poppler version the OS ships — no pinned
  on-disk-format concern (the stored bytes are just the PDF), but a real
  version-skew surface for extraction behavior. Contrast the in-tree CRoaring
  of [[knowledge/ideologies/pg_roaringbitmap]].
- **Packed-detoast awareness is partial.** Macros for both
  `PG_DETOAST_DATUM` and `PG_DETOAST_DATUM_PACKED` exist
  `[verified-by-code: pgpdf.c:29-35]`, and `bytea_to_pdf` uses
  `PG_GETARG_BYTEA_PP` + `VARDATA_ANY` `[verified-by-code: pgpdf.c:346, 350]`,
  but `pdf_to_bytea` uses the non-packed `PG_GETARG_PDF_P` + `VARDATA`
  `[verified-by-code: pgpdf.c:327, 335]`. Mixed discipline around the packed
  varlena footgun that bites the sibling types too.
- **Ships a versionless ABI.** No `recv`/`send`, no upgrade scripts
  (`sql/` has only `pgpdf--0.1.0.sql`) `[verified-by-code: tree listing]` —
  a young 0.1.0 extension `[verified-by-code: pgpdf.control:1]`.

## Links into corpus

- [[knowledge/ideologies/pg_roaringbitmap]] — the polar-opposite
  vendored-library allocator story: CRoaring's whole heap is redirected into
  MemoryContext via `roaring_init_memory_hook`, so an `ereport` mid-op leaks
  nothing; pgpdf's GLib heap is entirely outside MemoryContext and *does* leak
  on the error path (#4, #5). Also contrast `STORAGE = external` (no
  double-compress) vs pgpdf's `STORAGE = extended` (#7), and in-tree vendoring
  vs system-`pkg-config` linking.
- [[knowledge/ideologies/pguri]] — the closest temperament match:
  another foreign-C-library type that `malloc`s outside any context and copies
  results across the allocator fence with `pstrdup`, leaking on the error
  boundary. pgpdf does the same dance through GLib's `g_*_unref` instead of
  `free` (#4, #5).
- [[knowledge/ideologies/uuidv47]] — small parse-once-store-binary base type;
  structural contrast on the store-form decision (uuidv47 stores the parsed
  binary; pgpdf stores the *unparsed* bytes and re-parses on every read, #3).
- pgJQ — sibling "wrap a foreign parser (jq/oniguruma) as a custom type"
  written this run; compare its error/allocator boundary against pgpdf's
  GLib one.
- [[knowledge/idioms/memory-contexts]] — why GLib allocations escape context
  teardown and must be hand-`unref`'d (#4), and the copy-across-the-fence
  pattern via `cstring_to_text`/`StringInfo`.
- [[knowledge/idioms/error-handling]] — the `elog(ERROR)`-longjmp vs
  return-and-cleanup mismatch that makes the post-`elog` `g_clear_error`/`pfree`
  dead code and leaks GLib objects (#5); `PG_TRY/PG_CATCH` is the unused fix.
- [[knowledge/idioms/fmgr]] — `PG_FUNCTION_INFO_V1`, the `pdftype`/varlena
  detoast macros, `DirectFunctionCall1(pg_read_binary_file_all)` and
  `DirectFunctionCall6(make_timestamp)` as the fmgr re-entry points (#1, the
  date marshalling in #6/#7), and the `PG_GETARG_BYTEA_P` vs `_PP` packed
  distinction.
- [[knowledge/idioms/catalog-conventions]] — the shell-type-then-full-type
  `CREATE TYPE` idiom, `STORAGE = extended`, the INOUT vs function-backed
  casts, and the deliberate *absence* of `recv`/`send`/opclass/aggregate.
- [[knowledge/idioms/guc-variables]] — noted only by its absence: pgpdf
  defines no GUC and no `_PG_init`, unlike most vendored-lib siblings.
- Core analogs in prose: type I/O contract and the in/out-are-inverses
  expectation in `src/backend/utils/adt/`; varlena/TOAST storage strategies
  in `src/backend/access/common/`; `pg_read_binary_file_all` /
  server-file-read permissioning in `src/backend/utils/adt/genfile.c`.

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/Florents-Tselai/pgpdf/git/trees/main?recursive=1 | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/pgpdf.control | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/sql/pgpdf--0.1.0.sql | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/README.md | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/Makefile | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/META.json | 200 |
| https://raw.githubusercontent.com/Florents-Tselai/pgpdf/main/pgpdf.c | 200 |

**Fetch notes / substitutions:**
- The prompt's manifest hint (`*.control`, `*.sql`, `src/*.c`) was resolved
  against the tree listing: the repo is **flat**, not `src/`-rooted. The main
  (and only) C file is `pgpdf.c` (367 lines) at repo root; the control is a
  plain `pgpdf.control` (no `.control.in`); the single install script is
  `sql/pgpdf--0.1.0.sql` matching `default_version = '0.1.0'`. No upgrade
  scripts exist. No 404s encountered; all seven fetched files returned HTTP
  200.
- **poppler is a system library, not vendored and not a submodule.** The
  `Makefile` resolves it via `pkg-config --cflags/--libs poppler poppler-glib`
  and links `-lpoppler -lpoppler-glib` `[verified-by-code: Makefile:12-14]`;
  the README's install steps `apt install libpoppler-glib-dev` /
  `brew install poppler` confirm it is expected on the host
  `[from-README: README.md:276-289]`. The PDF library is therefore **poppler**
  (its GObject/GLib binding `poppler-glib`), *not* pdfium — pdfium is not
  referenced anywhere in the tree.
- The internals of poppler/GLib (the actual PDF parser, the GSlice allocator,
  `GBytes`/`GDateTime` implementations) were **not** read — they are an
  external shared library, not in this repo. All claims about poppler/GLib
  behavior are `[from-comment]`/`[inferred]` from the binding calls in
  `pgpdf.c` and the GLib API contract, never from a code read of poppler.
- `test/sql/pgpdf.sql`, `test/expected/pgpdf.out`, `Dockerfile`, and the
  `.github/workflows/*` were listed in the tree but not fetched; they are
  test/CI scaffolding and do not bear on the divergence analysis.
