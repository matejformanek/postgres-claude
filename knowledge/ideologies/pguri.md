# pguri — ideology / divergence notes

Extension: **petere/pguri** (`master`, control `default_version = 1`).
Adds a first-class `uri` base type to PostgreSQL, backed by the external
`liburiparser` C library linked into the backend.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> All `file:line` cites point into the fetched repo files (`uri.c`,
> `uri--1.sql`, `uri.control`, `README.md`), **not** `source/`. Cites verified
> against files fetched 2026-06-19 (see Sources footer). Read alongside the
> sibling small-custom-type ideology `[[uuidv47]]` and the core `text` type.

---

## Domain & purpose

pguri provides a `uri` data type so URIs get "URI syntax checking, functions
for extracting URI components, [and] human-friendly sorting" instead of being
dumped into a `text` column (`README.md:7-12`) `[from-README]`. The actual
parsing is delegated entirely to **liburiparser** (RFC 3986), a third-party C
library linked into the backend address space (`README.md:13-15`, `uri.c:10`)
`[from-README][verified-by-code]`. The type is interesting to document because
it is a *minimal* custom base type — input validation plus accessor functions —
yet it makes a sharply different storage-and-reparse tradeoff from the other
small custom types in this corpus (`[[uuidv47]]`, `[[zson]]`): pguri stores the
**raw URI text verbatim** and re-runs the external parser on *every* accessor
call rather than parsing once into a packed binary form.

---

## How it hooks into PG

Plain loadable-C-extension model, no `_PG_init`, no GUCs, no hooks:

- **Control file** `uri.control`: `comment = 'uri type'`, `default_version =
  1`, `module_pathname = '$libdir/uri'`, `relocatable = true`
  (`uri.control:1-4`) `[verified-by-code]`. There is **no `_PG_init`** anywhere
  in `uri.c` — bare `PG_MODULE_MAGIC;` at `uri.c:13` `[verified-by-code]`. This
  is the LOAD / CREATE EXTENSION model; nothing runs at load time.
- **The type is a relabeled varlena.** `typedef struct varlena uritype;`
  (`uri.c:16`) with `INTERNALLENGTH = -1` (variable length) in the catalog
  (`uri--1.sql:18-22`) `[verified-by-code]`. The DatumGet/PG_GETARG macros
  (`uri.c:19-25`) are copies of the standard text/varlena macros, including a
  `_PP` packed-detoast variant.
- **Type I/O**: `uri_in` validates then stores the original cstring as text
  (`uri.c:51-64`); `uri_out` is a pure passthrough — `TextDatumGetCString` with
  no reparse (`uri.c:66-73`) `[verified-by-code]`. Registered `IMMUTABLE
  STRICT` (`uri--1.sql:6-16`).
- **Accessors** via `PG_FUNCTION_INFO_V1`: `uri_scheme`, `uri_userinfo`,
  `uri_host`, `uri_host_inet`, `uri_port`, `uri_query`, `uri_fragment`,
  `uri_path`, `uri_path_array`, plus `uri_normalize`, `uri_escape`,
  `uri_unescape` (`uri.c:84-335, 563-597`). See `[[fmgr-and-spi]]`.
- **Comparison + opclasses**: `uri_lt/le/eq/ne/ge/gt/cmp` (`uri.c:477-545`) and
  `uri_hash` (`uri.c:547-561`), wired to a **B-tree** opclass `uri_ops` and a
  **hash** opclass `uri_ops_hash`, both `DEFAULT FOR TYPE uri`
  (`uri--1.sql:201-213`) `[verified-by-code]`. The `=` operator declares
  `HASHES, MERGES` (`uri--1.sql:159-169`).
- **Build**: PGXS `MODULE_big`, links liburiparser via `pkg-config`
  (`SHLIB_LINK += $(shell $(PKG_CONFIG) --libs liburiparser)`, `Makefile:14`)
  `[verified-by-code]`. See `[[extension-development]]`.

Cross-ref `[[catalog-conventions]]` (the `CREATE TYPE`/opclass DDL),
`[[fmgr-and-spi]]`, `.claude/skills/catalog-conventions/SKILL.md`.

---

## Where it diverges from core idioms

### 1. The external parser library is linked into the backend, and its error path leaks its own allocations

`parse_uri` calls `uriParseUriA` (liburiparser) and, on syntax error,
`ereport(ERROR, …)` with `ERRCODE_INVALID_TEXT_REPRESENTATION`
(`uri.c:40-45`) `[verified-by-code]`. The divergence is the
**allocation-ownership boundary**: liburiparser fills a `UriUriA` struct with
memory it `malloc`'d *itself* (outside any PG MemoryContext), which the caller
must release with `uriFreeUriMembersA`. The happy-path callers do call it (e.g.
`uri_scheme`, `uri.c:95`), but `parse_uri` itself **`ereport(ERROR)`s before
the `UriUriA` is freed** (`uri.c:41-44`): on a parse *failure* the partially
populated `UriUriA` is abandoned via longjmp, and because that memory is
liburiparser's own `malloc`, **PG's MemoryContext teardown will not reclaim
it** — a per-failed-parse leak in the calling backend. `[inferred]` (from the
ereport-before-free control flow at `uri.c:36-48` and the fact that
`UriUriA` members are library-`malloc`'d, not palloc'd). Contrast core's
contract that aborting via `ereport(ERROR)` is safe precisely because the
current MemoryContext is reset — a guarantee that does not extend across the
liburiparser allocator boundary. See `[[memory-contexts]]`, `[[error-handling]]`.

The unknown-error fallback uses `elog(ERROR, "liburiparser error code %d", …)`
(`uri.c:47`) — an internal-error elog, not a user-facing ereport — which is the
right call for a "should not happen" library return code.

### 2. Storage is the verbatim text; the parser runs on every accessor, not once at input

Core composite/packed types parse once at `*_in` and store a binary form so
accessors are cheap field reads. pguri does the opposite: `uri_in` parses
**only to validate**, immediately `uriFreeUriMembersA`'s the result, and stores
the *original cstring unchanged* as a text varlena (`uri.c:59-63`)
`[verified-by-code]`. Consequently `uri_out` is a no-op passthrough
(`uri.c:72`), and **every** accessor — `uri_scheme`, `uri_host`, `uri_cmp`,
etc. — calls `TextDatumGetCString` then re-runs the full liburiparser parse
(e.g. `uri.c:89-93`, `:450-457`) `[verified-by-code]`. So a `SELECT
uri_host(u)` over N rows performs N independent library parses. The design buys
exact round-trip fidelity (the stored bytes are exactly what the user typed —
the README even relies on this for equality semantics, `README.md:124-128`) at
the cost of repeated parse work. This is a legitimate and conscious tradeoff,
but it is the inverse of the "parse once, store packed" idiom that
`[[uuidv47]]` and most binary custom types follow. `[inferred]` from the
store-text + reparse-per-accessor structure.

### 3. The B-tree comparator is a *semantic, multi-field* sort, not byte order on storage

`uuidv47`'s comparator is a `memcmp` over stored bytes; pguri's `_uri_cmp` is a
hand-rolled multi-key comparison that parses both operands and compares
**scheme, then host, then port, then userinfo, then case-insensitively, then
exact** (`uri.c:447-475`) `[verified-by-code]`. Scheme/userinfo/host text
compares are **ASCII-case-insensitive** via the extension's own
`strncasecmp_ascii`/`strcasecmp_ascii` (reimplemented to avoid locale
dependence, `uri.c:337-385`) `[verified-by-code]`. Host comparison is
IP-aware: IPv4 and IPv6 hosts are compared by raw address bytes via `memcmp`
over `hostData.ip4/ip6` (`cmp_hosts`, `uri.c:409-445`) `[verified-by-code]`.
This delivers the README's "human-friendly sorting" (`README.md:11`) — order by
host/scheme rather than by leading `https://` text — but it means **the B-tree
key order is not derivable from the stored bytes**; the index is sorted by a
parse-derived projection. Two costs follow: (a) every comparison reparses both
sides (point 2 again, now on the index hot path), and (b) the comparator is
*not* consistent with `uri_out`'s text, so a B-tree scan does not return rows in
lexical-text order. The tie-break chain ending in `strcmp` (`uri.c:470`) keeps
the order a total order. See `.claude/skills/access-method-apis/SKILL.md`,
`[[catalog-conventions]]`.

### 4. The hash opclass hashes the raw stored bytes — inconsistent with the equality semantics

`uri_hash` is `hash_any` over the varlena payload (`VARDATA_ANY` /
`VARSIZE_ANY_EXHDR`, `uri.c:554-555`) `[verified-by-code]`, with a proper
`PG_FREE_IF_COPY` to avoid leaking a detoasted copy (`uri.c:558`). But `uri_eq`
is `_uri_cmp(...) == 0`, which is **case-insensitive on scheme/host**
(point 3). So two URIs that compare equal under `=` (e.g. differing only in
scheme case) hash to **different** values. PG requires a hash opclass's hash to
be consistent with its equality operator (equal values must hash equally) —
this is the hash-opclass invariant `eq(a,b) ⇒ hash(a)=hash(b)`. pguri appears
to **violate** it: the `=` operator carries `HASHES` (`uri--1.sql:166`) and
`uri_ops_hash` binds `=` to `uri_hash` (`uri--1.sql:210-213`), yet hash is over
literal bytes while `=` is case-folded. The practical effect is that
hash-based equality (hash joins, hash aggregation, hash indexes) can miss
matches that the `=` operator considers equal. `[inferred]` from the
byte-hash (`uri.c:554`) vs case-insensitive `_uri_cmp` (`uri.c:460-468`)
mismatch; this is the sharpest correctness divergence in the extension.

### 5. Accessor outputs are built with PG idioms, not library memory handed back raw

Where the library returns pointers into the parsed struct, the accessors copy
into palloc'd PG memory before freeing the `UriUriA`: `uri_text_range_to_text`
uses `cstring_to_text_with_len` (`uri.c:75-82`); `uri_path` builds a
`StringInfo` (`uri.c:259-277`); `uri_path_array` uses
`accumArrayResult`/`makeArrayResult` to build a `text[]` (`uri.c:287-305`)
`[verified-by-code]`. `uri_host_inet` even composes onto a core type — formats
the IP into a buffer and calls `DirectFunctionCall1(inet_in, …)`
(`uri.c:153, 165`) `[verified-by-code]`, the same fmgr-composition idiom
`[[uuidv47]]` uses to reuse `uuid_in`. So the *result* memory is handled
correctly; the leak in point 1 is specifically the library's *own* `UriUriA`
members on the error path, not the result Datums.

### 6. `uri_escape` reads raw varlena internals with hand-computed sizing

`uri_escape` reaches directly into the input text's bytes via `VARDATA(arg)` /
`VARSIZE(arg) - 4` (the `- 4` strips the varlena header) and sizes the output
as `(len) * (normalize_breaks ? 6 : 3) + 1` to bound liburiparser's
`uriEscapeExA` worst-case expansion (`uri.c:571-581`) `[verified-by-code]`.
This is correct but fragile: it assumes a **4-byte (un-toasted, un-packed)
varlena header** and uses `PG_GETARG_TEXT_PP` (packed) on the same arg
(`uri.c:567`), mixing the packed getarg with raw `VARSIZE`/`VARDATA` that
assume the unpacked layout. `[inferred]` from the `VARSIZE(arg) - 4` arithmetic
at `uri.c:574-577` against a `_PP`-fetched datum.

---

## Notable design decisions (with cites)

- **No `_PG_init`, no GUC, no hook** — pure type extension; bare
  `PG_MODULE_MAGIC` (`uri.c:13`) `[verified-by-code]`. Contrast `[[uuidv47]]`
  (one GUC for its key) and `[[pgsql-http]]` (GUC-heavy + curl init).
- **Store-verbatim, reparse-on-demand** — `uri_in` validates and discards the
  parse, stores the original text (`uri.c:59-63`); accessors reparse
  (`uri.c:89-93`) `[verified-by-code]`. Round-trip fidelity over parse cost.
- **`relocatable = true`** (`uri.control:4`) `[verified-by-code]` — the
  extension's objects can be moved between schemas; viable because it defines no
  schema-qualified cross-references at install time.
- **Two casts to/from `text`, both `WITH INOUT AS ASSIGNMENT`**
  (`uri--1.sql:25-26`) `[verified-by-code]` — assignment-only (not implicit) so
  `text` and `uri` don't silently interconvert in expressions, but a `text`
  value assigns into a `uri` column (re-validating through `uri_in`).
- **Locale-independent ASCII case folding** reimplemented in-extension
  (`strcasecmp_ascii`, `uri.c:337-360`) `[verified-by-code]` rather than libc
  `strcasecmp`, so sort order doesn't shift with `LC_COLLATE`.
- **Version chain `0 → 1`** shipped (`Makefile:7` lists
  `uri--0.sql uri--1.sql uri--0--1.sql`) `[verified-by-code]` — an upgrade
  script exists; `default_version = 1`.
- **README self-warns** against storing untrusted URI data ("might contain
  arbitrary junk", `README.md:17-19`) `[from-README]`.

---

## Links into corpus

- `[[catalog-conventions]]` — `CREATE TYPE uri` with `INTERNALLENGTH = -1`,
  in/out funcs, two `CREATE OPERATOR CLASS` (btree + hash), `CREATE CAST`
  (`uri--1.sql`).
- `[[fmgr-and-spi]]` — `PG_FUNCTION_INFO_V1` surface, `accumArrayResult`/
  `makeArrayResult` SRF-style array build, `DirectFunctionCall1(inet_in,…)`
  fmgr composition (`uri.c:153`).
- `[[memory-contexts]]` — the liburiparser↔palloc boundary: result memory is
  copied into palloc'd PG memory, but the library's own `UriUriA` members are
  `malloc`'d and must be `uriFreeUriMembersA`'d by hand (point 1).
- `[[error-handling]]` — parse failures → `ereport(ERROR,
  ERRCODE_INVALID_TEXT_REPRESENTATION)` (`uri.c:40-45`); internal library codes
  → `elog(ERROR, …)` (`uri.c:47`); the ereport-before-free leak is the
  cautionary case.
- Sibling ideologies: `[[uuidv47]]` (parse-once-store-binary + memcmp
  comparator — the structural contrast), `[[zson]]` (another store-form
  decision for a custom type), `[[pgsql-http]]` (third-party C lib —
  libcurl — linked into the backend, the same address-space-sharing theme).

> Corpus gap: there is no `idioms/custom-type-io.md` capturing the type-I/O
> purity / opclass-consistency invariants (output immutability, `hash`
> consistent with `=`). The point-4 hash/equality mismatch and the point-2
> store-vs-reparse tradeoff would be the natural anchors for such a doc; today
> they hang off `[[catalog-conventions]]` + `[[fmgr-and-spi]]`. `[inferred]`

---

## Sources

Fetched 2026-06-19 (branch `master`):

- `https://api.github.com/repos/petere/pguri/git/trees/master?recursive=1`
  → HTTP 200 (tree enumerated; manifest paths confirmed at repo root — no
  `src/` subdir, no `.in` control template).
- `https://raw.githubusercontent.com/petere/pguri/master/uri.c`
  → HTTP 200 (598 lines; deep-read — I/O, accessors, comparator, hash,
  escape/unescape).
- `https://raw.githubusercontent.com/petere/pguri/master/uri.control`
  → HTTP 200 (4 lines; `default_version = 1`, no `.in` template, not
  `.control.in`).
- `https://raw.githubusercontent.com/petere/pguri/master/uri--1.sql`
  → HTTP 200 (226 lines; type/opclass/cast/operator DDL — the install script
  for `default_version = 1`).
- `https://raw.githubusercontent.com/petere/pguri/master/README.md`
  → HTTP 200 (148 lines; purpose, function reference, caveats).
- `https://raw.githubusercontent.com/petere/pguri/master/Makefile`
  → HTTP 200 (21 lines; PGXS, liburiparser `pkg-config` link, version chain).
- `https://raw.githubusercontent.com/petere/pguri/master/uri--0.sql`
  → HTTP 200 (fetched, skimmed — earlier version, not cited; `uri--0--1.sql`
  upgrade script and the `test/` regression files were listed in the tree but
  not fetched).

Manifest-path corrections: the prompt's `uri--*.sql` glob resolved to
`uri--1.sql` (matching `default_version = 1`); `uri.control` exists as a plain
`.control` (no `.control.in` template). All cites are `[verified-by-code]`
against the fetched files except the human-friendly-sort and equality-semantics
motivation (`[from-README]`) and the four `[inferred]` analysis points (the
error-path leak, the per-accessor reparse cost, the hash/equality
inconsistency, and the `uri_escape` varlena-header assumption), which are
reasoned from the visible control flow rather than a runtime test.
