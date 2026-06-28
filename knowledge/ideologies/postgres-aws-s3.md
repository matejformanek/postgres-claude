# postgres-aws-s3 — a non-RDS clone of Amazon RDS's proprietary `aws_s3` extension, reimplemented entirely in `plpython3u` + boto3 so application SQL written for RDS runs unchanged off-RDS

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `chimpler/postgres-aws-s3` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> files fetched on 2026-06-28 (see Sources footer). Read alongside
> `[[knowledge/ideologies/orafce]]` (the other "reproduce a proprietary vendor's
> SQL surface for compatibility" extension — Oracle there, RDS here) and
> `[[knowledge/ideologies/index_advisor]]` (the other "the whole extension is a
> handful of dynamic-language function bodies, no C, no `.so`" case).

## Domain & purpose

postgres-aws-s3 exists to make Amazon RDS's S3 import/export surface available on
a plain PostgreSQL server. RDS (since PG 11.1) ships a closed `aws_s3` extension
exposing `aws_s3.table_import_from_s3(...)` and `aws_s3.query_export_to_s3(...)`
plus the `aws_commons` helper constructors; this repo is a from-scratch
reimplementation "that is similar to the one provided in RDS … implemented in
Python using the boto3 library" (`README.md:3-6`) `[from-README]`. The goal is
**API compatibility, not novelty**: the schemas (`aws_s3`, `aws_commons`), the
composite types (`aws_commons._s3_uri_1`, `aws_commons._aws_credentials_1`), and
the function signatures all match RDS so that application SQL and migration
tooling written against RDS run unmodified on a local/self-hosted cluster
(`aws_s3--0.0.1.sql:5-11,46-58`) `[verified-by-code]`.

The reason to document it: it is the corpus's clearest example of an extension
whose *entire* divergence is that it has **no backend C at all** — its
`module_pathname = '$libdir/aws_s3'` (`aws_s3.control:4`) is a vestigial lie (no
`.so` is built; the `Makefile` only installs the `.control` + SQL), and every
"function" is a `LANGUAGE plpython3u` body that shells data through boto3 and a
server-side `COPY` (`aws_s3--0.0.1.sql:60-126`) `[verified-by-code]`. It is a
compatibility shim, and its design decisions are all consequences of pretending
to be a C extension while actually being trusted-but-not-really Python.

## How it hooks into PG

There are no hooks. The extension is four `CREATE FUNCTION`s and two `CREATE
TYPE`s in a single install script:

- **Two composite "object" constructors in `aws_commons`**, mirroring RDS's
  opaque handles: `create_s3_uri(bucket, key, region) RETURNS
  aws_commons._s3_uri_1` and `create_aws_credentials(access_key, secret_key,
  session_token) RETURNS aws_commons._aws_credentials_1`, each a one-line
  `plpython3u` body that just returns the tuple (`aws_s3--0.0.1.sql:21-43`)
  `[verified-by-code]`. The composite types are declared with `DROP TYPE IF
  EXISTS … CASCADE` then `CREATE TYPE … AS (...)` (`aws_s3--0.0.1.sql:13-19`) —
  see divergence #4 on why the `CASCADE` drop in an install script is unusual.
- **`aws_s3.table_import_from_s3`** in two overloads: a 10-argument "flat" form
  (`aws_s3--0.0.1.sql:46-126`) and a 6-argument form taking the two composite
  objects that simply `plpy.prepare`/`execute`s a call to the flat form
  (`aws_s3--0.0.1.sql:131-160`) `[verified-by-code]`. The flat form does the
  real work: boto3 `s3.Object(bucket, file_path).get()`, optional gzip
  de-streaming, write to a `tempfile.NamedTemporaryFile`, then `COPY <table>
  FROM '<tmpfile>' <options>` via `plpy.execute` (`aws_s3--0.0.1.sql:103-124`).
- **`aws_s3.query_export_to_s3`**, also two overloads, the inverse: `COPY (<query>)
  TO '<tmpfile>' <options>` then boto3 `s3.upload_fileobj(fd, bucket, file_path)`,
  returning `(rows_uploaded, files_uploaded, bytes_uploaded)` counted by reading
  the temp file back and counting `b'\n'` (`aws_s3--0.0.1.sql:162-227`)
  `[verified-by-code]`.

`plpython3u` is the untrusted variant (the `u` suffix), so all of this runs with
the OS privileges of the backend process — which is exactly what lets it touch
the filesystem and the network (see divergence #1).

## Where it diverges from core idioms

### 1. The extension's whole runtime is an untrusted-PL escape hatch into the OS — network sockets and temp files from inside a backend

Core PG has no in-database HTTP/S3 client and deliberately so; reaching the
network is left to `[[knowledge/ideologies/pgsql-http]]` (synchronous libcurl in
C) or `[[knowledge/ideologies/pg_net]]` (async bgworker). postgres-aws-s3 instead
borrows `plpython3u`'s ambient authority: `boto3.resource('s3', …)` /
`boto3.client('s3', …)` open outbound TLS connections to AWS (or any
`endpoint_url`) directly from the executing backend (`aws_s3--0.0.1.sql:96-101,
192-197`) `[verified-by-code]`, and a `tempfile.NamedTemporaryFile` materializes
the entire object on the backend's local disk before `COPY` ingests it
(`aws_s3--0.0.1.sql:103-124`). The data path is **S3 → backend RAM/socket →
backend-local temp file → COPY → heap**; the file is the deliberate bridge,
because server-side `COPY … FROM '<file>'` is the only way to drive core's
bulk-load path from SQL without a C `.so`. This is the inverse of a clean
extension: rather than teach the backend a new capability in C, it abuses an
untrusted PL to smuggle a Python runtime's capabilities into SQL.

### 2. It impersonates a C extension it isn't — `module_pathname` points at a `$libdir/aws_s3.so` that is never built

`aws_s3.control` declares `module_pathname = '$libdir/aws_s3'`
(`aws_s3.control:4`) `[verified-by-code]`, the boilerplate a C extension uses so
`CREATE FUNCTION … AS 'MODULE_PATHNAME'` resolves to its shared library. But no C
source exists and the `Makefile` builds no library — the directive is inert
because every function is `LANGUAGE plpython3u` with an inline body, not
`LANGUAGE c`. The artifact is cargo-culted from the C-extension template; it
documents intent (look like RDS's `aws_s3`) rather than mechanism. `relocatable =
true` (`aws_s3.control:5`) is similarly aspirational — the function bodies don't
hard-code their own schema, but they *do* hard-code `aws_s3.`-prefixed recursive
calls (divergence #4), so true relocation is partial. `[verified-by-code]`

### 3. `IMMUTABLE` on functions that perform network I/O and write files

`aws_commons.create_s3_uri` and `create_aws_credentials` are marked `IMMUTABLE`
(`aws_s3--0.0.1.sql:25,42`) `[verified-by-code]` — defensible, they're pure
tuple constructors. But the volatility story is loose: the import/export
functions are left at the default `VOLATILE` (correct), yet the whole design
leans on side-effecting PL where core would never label such work pure. This is
the same family of "volatility label vs. actual effects" looseness catalogued in
`[[knowledge/ideologies/zson]]` (IMMUTABLE I/O that reads a catalog) and
`[[knowledge/ideologies/uuidv47]]` (IMMUTABLE output depending on a GUC) — here
the constructors are the benign end, but the pattern of "compatibility first,
volatility-purity second" is the same.

### 4. Credentials and config are read from GUCs via `current_setting('aws_s3.<name>', true)`, defaulting silently to the string `'unknown'`

Both import and export build an `aws_settings` dict by `plpy.prepare`-ing a query
that calls `current_setting('aws_s3.' || name, true)` over the four names
`access_key_id, secret_access_key, session_token, endpoint_url`
(`aws_s3--0.0.1.sql:78-94, 176-190`) `[verified-by-code]`. So credentials can be
supplied three ways — explicit function args, the `aws_commons._aws_credentials_1`
object, or **placeholder GUCs in the session/`postgresql.conf`** — and when an
access key is missing it falls back to the literal string `'unknown'`
(`aws_s3--0.0.1.sql:82`), pushing the failure down into boto3 rather than raising
a PG error. Using `current_setting(..., true)` (the missing-ok form) means a
typo'd GUC name yields `NULL` → `'unknown'` silently. These `aws_s3.*` settings
are **placeholder GUCs** — not registered via `DefineCustomStringVariable`
(there's no C `_PG_init`), they exist only because PG accepts dotted unknown GUC
names as free-form placeholders (cf. `[[knowledge/idioms/guc-variables]]`).

### 5. SQL injection surface by `str.format` into `COPY`, not parameterization

The `COPY` statements are assembled with Python `str.format`:
`"COPY {table_name} {formatted_column_list} FROM {filename} {options};"`
(`aws_s3--0.0.1.sql:114-120`) and `"COPY ({query}) TO '{filename}' {options}"`
(`aws_s3--0.0.1.sql:201-205`) `[verified-by-code]`. Only `filename` is passed
through `plpy.quote_literal` (`aws_s3--0.0.1.sql:116`); `table_name`,
`column_list`, `options`, and the entire `query` are interpolated raw. This is
unavoidable for `COPY` (its table/option slots aren't parameterizable), but it
means the functions trust their callers completely — appropriate for the RDS
contract (the caller is the DBA) but a sharp edge that core's parameterized
protocol would never expose. The recursive 6-arg → 10-arg overloads, by
contrast, *do* use proper `plpy.prepare` with a typed `['TEXT', …]` plan and
positional `$1..$9` params (`aws_s3--0.0.1.sql:133-159`), showing the author
knows the safe idiom and reaches for `format` only where `COPY` forces it.

### 6. A hand-rolled per-session module cache built on plpython's `SD` dict

To avoid re-`import`ing boto3 on every call, each function defines a local
`cache_import(module_name)` that memoizes imported modules into plpython's
session dictionary `SD['__modules__']` (`aws_s3--0.0.1.sql:61-76, 165-180`)
`[verified-by-code]`. `SD` is plpython's per-function session-local store, so
this is a deliberate backend-lifetime cache living entirely in the Python
interpreter's heap — outside any PG `MemoryContext`
(`[[knowledge/idioms/memory-contexts]]`). It's the Python analogue of the
malloc'd, MemoryContext-free caches that C extensions like
`[[knowledge/ideologies/zson]]` hand-roll; here the "allocator" is CPython's GC
and the cache survives for the life of the forked backend.

### 7. Gzip handling sniffs both the real `ContentEncoding` and a `x-amz-meta-content-encoding` user-metadata header

The importer decompresses if either S3's `ContentEncoding == 'gzip'` *or* a
user-metadata key `response.get('x-amz-meta-content-encoding') == 'gzip'`
(`aws_s3--0.0.1.sql:104-112`) `[verified-by-code]` — a small fidelity touch that
matches RDS's documented behavior for objects whose gzip-ness is recorded in
custom metadata rather than the standard header. It streams via
`gzip.GzipFile(fileobj=body)` in 200 KB chunks (`aws_s3--0.0.1.sql:106-110`),
never holding the whole decompressed object in memory at once — the one place the
design is memory-careful, ironically in Python rather than in PG.

## Notable design decisions with cites

- **Export counts rows by re-reading the temp file and counting newlines**, not
  by trusting `COPY`'s own row count: after `COPY (query) TO tmpfile`, it loops
  `fd.read(8192*1024)` accumulating `buffer.count(b'\n')` and `len(buffer)` for
  `(rows_uploaded, bytes_uploaded)`, then `s3.upload_fileobj`
  (`aws_s3--0.0.1.sql:207-223`) `[verified-by-code]`. `files_uploaded` is
  hard-coded `1` — it never splits across multiple S3 objects, unlike RDS which
  can chunk large exports. `[verified-by-code]`
- **The export function is a set-returning `RETURNS SETOF RECORD` with `OUT`
  params**, `yield`-ing a single tuple (`aws_s3--0.0.1.sql:171-225`) — the
  plpython idiom for a one-row SRF, chosen so the signature matches RDS's
  multi-row-capable return shape even though this implementation always returns
  one row. `[verified-by-code]`
- **`endpoint_url` is threaded through every overload** specifically to support
  LocalStack / MinIO testing (`README.md` "optional endpoint", the repo ships a
  `docker-compose.yml` + LocalStack mock-server) `[from-README]` — a
  compatibility *superset* over RDS, which has no such parameter.
- **`DROP TYPE IF EXISTS … CASCADE` at the top of the install script**
  (`aws_s3--0.0.1.sql:13,16`) `[verified-by-code]` is unusual for a
  `CREATE EXTENSION` script (which normally runs in a fresh extension schema);
  it's there to make `DROP EXTENSION; CREATE EXTENSION` re-runs idempotent across
  the type-shape changes the README documents (`README.md:42-47` "drop and
  recreate") `[from-README]` — but `CASCADE` would silently drop dependent
  columns, a footgun core's own extension scripts avoid.

## Links into corpus

- `[[knowledge/ideologies/orafce]]` — the sibling "reproduce a proprietary
  vendor's SQL surface for drop-in compatibility" extension (Oracle compat as
  policy); postgres-aws-s3 is RDS-`aws_s3` compat as policy.
- `[[knowledge/ideologies/pgsql-http]]` and `[[knowledge/ideologies/pg_net]]` —
  the two principled ways PG reaches the network (sync C libcurl / async bgworker
  + curl_multi); postgres-aws-s3 is the unprincipled third way (untrusted PL +
  boto3 from the executing backend).
- `[[knowledge/ideologies/index_advisor]]` — the other "no C, the whole extension
  is a few dynamic-language function bodies" case; both invert "no compiled code
  therefore harmless."
- `[[knowledge/ideologies/zson]]` and `[[knowledge/ideologies/uuidv47]]` — the
  volatility-label-vs-actual-effects family (divergence #3).
- `[[knowledge/idioms/guc-variables]]` — placeholder `aws_s3.*` GUCs read via
  `current_setting(name, true)` with no `DefineCustom*Variable` registration.
- `[[knowledge/idioms/memory-contexts]]` — the `SD['__modules__']` per-session
  module cache as the Python analogue of a MemoryContext-free backend-lifetime
  cache.

## Sources

Fetched 2026-06-28 via `raw.githubusercontent.com/chimpler/postgres-aws-s3/master`:

- `README.md` @ 2026-06-28 → 200
- `aws_s3.control` @ 2026-06-28 → 200
- `aws_s3--0.0.1.sql` @ 2026-06-28 → 200

Tree listing via `api.github.com/repos/chimpler/postgres-aws-s3/git/trees/master`
@ 2026-06-28 → 200. No manifest gaps for the type/function story above. The
`Makefile`, `docker-compose.yml`, `mock-servers/` (LocalStack fixtures),
`CHANGELOG.md`, and `Dockerfile` were listed but not fetched; they confirm the
no-`.so` build + LocalStack test harness but add nothing to the divergence
analysis. Star count (~178★) per the GitHub search at fetch time.
