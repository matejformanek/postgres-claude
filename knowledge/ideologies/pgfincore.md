# pgfincore — an extension that reaches THROUGH PG's storage abstraction to inspect and steer the *operating-system* page cache for relation segment files

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `klando/pgfincore` @ branch `master`. All `file:line` cites below point
> into *that* repo (not `source/`), since this doc characterizes an external
> extension's divergence from core idioms. Cites verified against files fetched
> on 2026-06-29 (see Sources footer): `pgfincore.c` (1117 lines, read in full),
> `pgfincore--1.4.sql`, `pgfincore.control`, `Makefile`, `README.md`. Line
> numbers are for the `master` blobs as fetched (the repo notes it is migrating
> to Codeberg, but `master` on GitHub still carried the source).
>
> Read alongside `[[knowledge/ideologies/system_stats]]` — the OS-reach sibling
> that answers SQL from `/proc`/`sysconf` rather than from PG state. The decisive
> contrast for pgfincore is with **core `contrib/pg_prewarm`**, which warms
> PostgreSQL's *own* shared buffers; pgfincore deliberately operates one layer
> below, on the *kernel's* page cache for the on-disk segment files.

## Domain & purpose

pgfincore "let you see and manipulate objects in the FS page cache"
(`pgfincore.c:3`) `[from-comment]` — i.e. it manages "pages in memory from
PostgreSQL" by leveraging the operating system's page cache for relation files
(`README.md:9-24`) `[from-README]`. It exposes a small SQL surface: `pgsysconf`
(report OS page size + free/total pages via `sysconf`), `pgfadvise` and its
`willneed`/`dontneed`/`normal`/`sequential`/`random` wrappers (apply a
`posix_fadvise` advice to every segment of a relation), `pgfadvise_loader`
(apply WILLNEED/DONTNEED per-page driven by a `varbit` map), `pgfincore`
(report, per segment, how many of the relation's OS pages are resident — and
optionally a `varbit` bitmap of which ones, plus dirty counts), and
`pgfincore_drawer` (render a `varbit` map to ASCII) (`pgfincore--1.4.sql`,
`pgfincore.c`) `[verified-by-code]`. The headline workflow is **snapshot &
restore**: `pgfincore(...)` emits a `databit varbit` describing exactly which
pages are cached; that bitmap is stored in an ordinary table, and after a reboot
(or on a streaming-replication standby) `pgfadvise_loader(rel, seg, true, true,
databit)` replays the bitmap to re-warm the same pages
(`README.md:19-22, 111-128`) `[from-README]`.

The reason to document it: pgfincore is the corpus's clearest case of an
extension that **bypasses PG's storage manager and buffer manager to talk
directly to the kernel VM layer about the segment files PG itself manages**. PG
normally never inspects the kernel page cache — it tracks only its own
`shared_buffers`. pgfincore opens the very same files PG's `md.c` opens, but via
libc `AllocateFile`, and runs `mincore(2)` / `posix_fadvise(2)` / `mmap(2)`
against them.

## How it hooks into PG

Pure fmgr extension — no `_PG_init`, no background worker, no shared memory, no
GUCs, no hooks:

- **No `_PG_init` at all.** The only load-time construct is bare
  `PG_MODULE_MAGIC;` (`pgfincore.c:43-45`) `[verified-by-code]`. There is no
  `RegisterBackgroundWorker`, no `RequestAddinShmemSpace`, no
  `ProcessUtility_hook`. Confirmed by absence across the single 1117-line `.c`.
- **Four C-language SRF/scalar entry points**, each `PG_FUNCTION_INFO_V1`:
  `pgsysconf` (`pgfincore.c:166-194`), `pgfadvise` (`:313-451`),
  `pgfadvise_loader` (`:596-690`), `pgfincore` (`:893-1050`), and
  `pgfincore_drawer` (`:1055-1117`) `[verified-by-code]`. The
  `willneed`/`dontneed`/etc. variants are thin SQL wrappers that call
  `pgfadvise($1,'main',<int>)` with a magic advice code
  (`pgfincore--1.4.sql:52-100`), and the 1-/2-arg `pgfincore`/`pgfadvise_loader`
  overloads are SQL wrappers defaulting the `'main'` fork
  (`pgfincore--1.4.sql:120-183`) `[verified-by-code]`.
- **It locates a relation's segment files via `relpathbackend` + manual `.N`
  suffixing — not through smgr.** Both `pgfadvise` and `pgfincore` do
  `relation_open(relOid, AccessShareLock)`, then `relpathpg(rel, forkName)`
  (a macro over `relpathbackend(rel->rd_locator, rel->rd_backend,
  forkname_to_number(...))`, `pgfincore.c:146-156`), then iterate segments by
  `snprintf(filename, "%s.%u", relationpath, segcount)` for `segcount > 0` and
  the bare path for segment 0 (`pgfincore.c:362-400, 945-980`)
  `[verified-by-code]`. This is the divergence in one line: it reconstructs the
  *filename* PG's `md.c` would use, then opens that file itself.
- **Standard SRF scaffolding.** `pgfadvise`/`pgfincore` use the ValuePerCall SRF
  protocol (`SRF_IS_FIRSTCALL`/`SRF_FIRSTCALL_INIT`/`SRF_PERCALL_SETUP`/
  `SRF_RETURN_NEXT`/`SRF_RETURN_DONE`), keep cross-call state (`Relation`,
  `relationpath`, `segcount`) in a `palloc`'d fctx in
  `multi_call_memory_ctx`, and build the tupdesc via `get_call_result_type`
  (`pgfincore.c:331-380, 911-960`) `[verified-by-code]`. The relation lock is
  held across the whole walk and released at `SRF_RETURN_DONE`
  (`pgfincore.c:416-421, 994-999`). `pgfadvise_loader` is a non-SRF single-tuple
  function that opens the relation only to *derive the filename* and closes it
  immediately, before doing the I/O (`pgfincore.c:638-664`) `[verified-by-code]`.
- **Build is plain PGXS, single module.** `MODULES = pgfincore`, no
  `MODULE_big`, no external library link (`Makefile:1-16`) `[verified-by-code]`.
  Control: `default_version = '1.4'`, `relocatable = true`,
  `directory = pgfincore` (`pgfincore.control:1-6`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. The decisive reach-through: smgr/md.c is bypassed; the kernel page cache is queried directly

Core PG's storage stack is layered `bufmgr → smgr → md.c → fd.c`, and PG's only
notion of "is this page cached" is "is it in `shared_buffers`" (the
`pg_buffercache` view reads PG's own buffer descriptors). pgfincore answers a
*different* question — "is this page in the **OS** page cache" — that PG itself
never asks. It does so by opening the segment file via libc and calling
`mincore(pa, st.st_size, vec)` over an `mmap(NULL, st.st_size, PROT_NONE,
MAP_SHARED, fd, 0)` projection of the file, then walking the returned residency
vector (`pgfincore.c:763-807, 826-865`) `[verified-by-code]`. The `PROT_NONE`
mapping is the textbook mincore idiom: map the file purely to obtain an address
range to interrogate, never to read through it. So the data source is the
kernel's VM residency bits for PG's data files — a layer PG's own code treats as
opaque. `[verified-by-code]` from the `mmap`+`mincore` call pair.

### 2. The contrast with core pg_prewarm: same goal name, opposite cache

`contrib/pg_prewarm` warms PostgreSQL's *own* shared buffers (its `buffer` mode
reads each block through `ReadBufferExtended`, pinning it into
`shared_buffers`); its `prefetch` mode issues `posix_fadvise(WILLNEED)` but only
as an optimization layered under PG's own read path. pgfincore's
`pgfadvise_willneed` issues `posix_fadvise(fd, 0, 0, POSIX_FADV_WILLNEED)` on the
whole segment file (`pgfincore.c:244-248, 286`) and never touches
`shared_buffers` at all — the warmed pages live in the OS cache, available to a
*subsequent* PG read but not pinned by PG. The snapshot/restore feature
(`README.md:111-128`) is the sharpest divergence: pg_prewarm's
`autoprewarm` persists a list of PG buffer-tags; pgfincore persists a per-page
**OS-residency bitmap** as a SQL `varbit`, restorable on a *different* host via
streaming replication (`README.md:19-22`) `[from-README]` — because OS-cache
state is a property of the file on disk, which the standby also has.

### 3. `mincore`/`fincore`/`fadvise`/`mmap` are non-portable, gated by build-time defines

The whole capability is `#if defined(USE_POSIX_FADVISE)` (the advise/loader
functions, `pgfincore.c:196, 453`); the `#else` branch is a stub that
`elog(ERROR, "POSIX_FADVISE UNSUPPORTED on your platform")`
(`pgfincore.c:298-305, 579-588`) `[verified-by-code]`. The residency probe has a
two-way fork on `HAVE_FINCORE`: when the newer `fincore()` syscall is available
it is called directly on the fd (`fincore(fd, 0, st.st_size, vec)`,
`pgfincore.c:796-803`); otherwise it falls back to `mmap`+`mincore`
(`pgfincore.c:763-795`) `[verified-by-code]`. This also changes the *information
density*: `FINCORE_BITS` is `1` without `fincore` (present/absent only) but `2`
with it (present + dirty), and the dirty accounting at
`pgfincore.c:833-846` only runs when `FINCORE_BITS > 1`
(`pgfincore.c:58-64, 812`) `[verified-by-code]`. The README states plainly this
is unavailable on Windows (`README.md`, requirements) `[from-README]`. Core PG
abstracts platform differences behind `pg_flush_data` / its own fd layer;
pgfincore exposes the raw syscall portability matrix as a feature-detection
cliff.

### 4. The per-page resident bitmap: a libc `calloc`'d vector plus a `palloc0`'d varbit, mixed allocators

For each segment, pgfincore allocates the kernel residency vector with **libc
`calloc(1, npages)`** (`pgfincore.c:776`) and frees it with libc `free`
(`pgfincore.c:804, 873`) `[verified-by-code]` — outside any MemoryContext. The
*output* bitmap, by contrast, is a proper PG `VarBit` built with `palloc0(len)` +
`SET_VARSIZE` + manual `VARBITLEN` poke (`pgfincore.c:812-822`)
`[verified-by-code]`, returned as a Datum. So one buffer (the scratch vector)
lives in malloc-land and one (the result varbit) lives in palloc-land, and the
code even self-flags the uncertainty — comment `"XXX: do we need to free that ?"`
above the `palloc0` (`pgfincore.c:817`) `[from-comment]`. For a large relation
this varbit is `FINCORE_BITS * npages` bits *per segment*, materialized in the
per-query context. See `[[knowledge/idioms/memory-contexts]]` for the contrast
with PG's "let the context reclaim it" discipline — here the scratch vector must
be hand-`free`d on every error path (`pgfincore.c:782, 804`), and the `munmap`
likewise (`pgfincore.c:780, 793, 875`) `[verified-by-code]`.

### 5. File I/O on the SQL hot path, with no interrupt checking inside the page loop

The segment open uses PG's `AllocateFile(filename, "rb")` / `FreeFile`
(`pgfincore.c:223, 289, 494, 740, 877`) — so it correctly participates in PG's
transient-file bookkeeping (files are closed at xact end even if leaked)
`[verified-by-code]` — but the residency walk (`pgfincore.c:826-865`) and the
loader's per-page `posix_fadvise` loop over every set bit
(`pgfincore.c:510-569`) run to completion with **no `CHECK_FOR_INTERRUPTS`**
inside them. `[inferred]` from the loop bodies (no interrupt macro present). On a
multi-gigabyte relation the loader issues one `posix_fadvise` syscall per cached
page (`pgfincore.c:520-524, 552-556`), an uninterruptible burst of syscalls in
the executing backend.

### 6. Theoretical, not observed, load/unload accounting

The loader increments `pagesLoaded`/`pagesUnloaded` per bit acted on, but the
code itself notes "both are theorical: we don't know if the page was or not in
memory when we call posix_fadvise" (`pgfincore.c:482-487`) `[from-comment]`. So
the returned counts describe *advice issued*, not cache transitions that
actually happened — the kernel may ignore `WILLNEED`/`DONTNEED`. This is an
honest divergence from PG's usual "report what we did" stat semantics: the
numbers are an upper bound on intent.

## Notable design decisions with cites

- **Magic advice integers cross the SQL/C boundary.** `pgfadvise(regclass, text,
  int)` takes an `int` advice code; the SQL wrappers pass literals `10/20/30/40/
  50` (`pgfincore--1.4.sql:59,69,79,89,99`) which the C side maps to
  `PGF_WILLNEED..PGF_RANDOM` `#define`s (`pgfincore.c:52-56`) and thence to
  `POSIX_FADV_*` flags (`pgfincore.c:244-281`) `[verified-by-code]`. An unknown
  code `elog(ERROR, "pgfadvise: invalid advice")` (`pgfincore.c:277-281`).
- **Segment iteration mirrors `md.c`'s `RELSEG_SIZE` filename scheme by hand.**
  Segment 0 is the bare relpath; segment N is `relpath.N`
  (`pgfincore.c:390-400, 970-980`) `[verified-by-code]`. The SRF advances
  `segcount` and re-derives the filename each call; when `AllocateFile` returns
  NULL (no such segment) `pgfadvise_file`/`pgfincore_file` return 1 and the SRF
  ends (`pgfincore.c:223-225, 416-421, 740-742, 994-999`) `[verified-by-code]` —
  i.e. "file not found" is the loop terminator, not an error.
- **`relpathpg` carries the cross-version porting burden of PG's relfilenode
  rename.** The macro forks three ways: `rd_node` for PG < 16, `rd_locator` for
  16–17, and `pstrdup(...).str` for PG 18+ where `relpathbackend` returns a
  `RelPathStr` struct (`pgfincore.c:146-156`) `[verified-by-code]`. This is the
  single spot most coupled to PG internals — it tracks the
  `RelFileNode→RelFileLocator` rename and the later return-type change.
- **`pgfincore_drawer` is an in-tree ASCII visualizer** marked "(for testing)":
  it walks the varbit two bits at a time, emitting `'.'` for present, `'*'` for
  dirty, `' '` for absent (`pgfincore.c:1055-1117`) `[verified-by-code]`. A
  cstring-returning scalar, not an SRF.
- **The relation lock is `AccessShareLock`, held for the whole walk in
  `pgfincore`/`pgfadvise`** (`pgfincore.c:364, 419, 947, 997`) but
  **released immediately** in `pgfadvise_loader` after deriving the filename
  (`pgfincore.c:638-664`) `[verified-by-code]` — the loader deliberately does its
  fadvise I/O without holding any relation lock, with a comment that the only
  purpose of the open was a consistent filename (`pgfincore.c:659-663`)
  `[from-comment]`.
- **`mincore` ENOMEM gets a bespoke error pointing at the author's email.** The
  `mmap` failure path emits a long hint ending "Please mail cedric@villemain.org
  with '[pgfincore] ENOMEM' as subject" (`pgfincore.c:769`) `[verified-by-code]`
  — a non-PG-idiomatic errmsg (core uses `errhint`, no personal contact).

## Links into corpus

- `[[knowledge/ideologies/system_stats]]` — the OS-reach sibling: it answers SQL
  from `/proc`/`sysconf`/`uname` (host telemetry) where pgfincore answers from
  `mincore`/`posix_fadvise` over PG's *own* data files (per-relation OS-cache
  state). Both share the "backend does libc syscalls on the SQL path" shape and
  both use `sysconf(_SC_PAGESIZE)`/`sysconf(_SC_AVPHYS_PAGES)` (system_stats via
  `/proc/meminfo`; pgfincore directly, `pgfincore.c:183-189, 216, 294`).
- `[[knowledge/idioms/fmgr]]` — the `PG_FUNCTION_INFO_V1` + ValuePerCall SRF
  (`SRF_FIRSTCALL_INIT`/`SRF_RETURN_NEXT`) pattern instantiated by `pgfadvise`
  and `pgfincore`; no SPI is used (the SQL wrappers in `pgfincore--1.4.sql` do
  the only SQL-level composition).
- `[[knowledge/idioms/memory-contexts]]` — the contrast in §4: cross-call fctx in
  `multi_call_memory_ctx`, result varbit in the per-query context via `palloc0`,
  but the kernel residency vector in libc `calloc`/`free` outside any context.
- **In-core foil: `contrib/pg_prewarm`** (no corpus subsystem doc exists yet —
  `knowledge/subsystems/` is empty as of this fetch, so this is an external
  pointer, not a `[[wikilink]]`). pg_prewarm warms `shared_buffers` (or issues
  fadvise under PG's read path); pgfincore inspects/steers the OS page cache and
  never touches `shared_buffers`. The two are complementary layers, not
  alternatives. `[inferred]` from pgfincore's call paths vs pg_prewarm's
  documented behavior.

> Corpus gap: there is no `knowledge/subsystems/storage-smgr.md` or
> `storage-buffer.md` to link to (the `subsystems/` dir is empty at fetch time),
> so the "reach past smgr/md.c" claim in §1 is anchored on pgfincore's own code
> (`relpathbackend` + manual `.N` suffixing, `mmap`/`mincore`) rather than a
> cross-link into a core-storage doc. That doc would be the natural home for the
> bufmgr→smgr→md.c→fd.c layering this extension circumvents. `[inferred]`

## Sources

Fetched 2026-06-29 from `raw.githubusercontent.com/klando/pgfincore/master`
(the GitHub API tree endpoint `git/trees/master?recursive=1` returned **HTTP
403** through the agent proxy, and the GitHub MCP tool is scoped to the user's
own repo only — so the file manifest was reconstructed from the `Makefile`'s
`DATA`/`MODULES` lists rather than from a tree listing):

- `pgfincore.c` → HTTP 200 (1117 lines; read in full — all five functions, both
  `#ifdef HAVE_FINCORE` branches, the `relpathpg` version fork).
- `pgfincore.control` → HTTP 200 (6 lines; `default_version = '1.4'`,
  `relocatable = true`).
- `pgfincore--1.4.sql` → HTTP 200 (193 lines; full install script — the C
  function decls + SQL wrappers).
- `Makefile` → HTTP 200 (16 lines; PGXS, `MODULES = pgfincore`, `DATA` lists the
  1.2→1.3.1, 1.3.1→1.4, and 1.4 SQL scripts).
- `README.md` → HTTP 200 (355 lines; fetched via WebFetch which returns a
  summary rather than verbatim text, so all `[from-README]` cites are to summary
  line ranges, not exact blob lines — the behavioral specifics (mincore,
  fadvise, snapshot/restore over replication, Windows-unsupported) are
  corroborated by the C code where it matters).
- `META.json` → HTTP 404 (not present in this repo).

Manifest gaps: the upgrade scripts `pgfincore--1.2--1.3.1.sql` and
`pgfincore--1.3.1--1.4.sql` (named in `Makefile:6-7`) were enumerated but not
fetched — they are version-delta scripts and do not change the divergence
characterization, which rests on the `1.4` install script + the C source. The
`expected/`/`sql/` regression files (implied by `REGRESS = pgfincore`,
`Makefile:10`) were not fetched. All §1–§6 code claims are `[verified-by-code]`
against `pgfincore.c` except the no-interrupt-checking observation, the
mixed-allocator framing's "for a large relation" sizing, and the pg_prewarm
contrast, which are `[inferred]` from the visible control flow and core
pg_prewarm's documented behavior rather than a runtime test.
