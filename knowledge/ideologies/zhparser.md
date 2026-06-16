# zhparser — ideology / divergence-from-core notes

> Extension: `amutu/zhparser` @ `master` (control reports `default_version =
> '2.4'`, `relocatable = true`). The manifest hint named the org
> `zhparser/zhparser`, but that is the Docker-Hub namespace; the source repo
> is `github.com/amutu/zhparser` (858★) — resolved via search.
> One durable "how this diverges from core PG design" doc. Line cites are into
> the upstream zhparser tree (`zhparser.c`, `zhparser.h`, `zhparser--2.4.sql`,
> `zhparser.control`), NOT into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> Caveat: the `zhparser.c` fetched here is a self-described "Hardened revision
> (PG 16/17/18)" (`zhparser.c:6-13`), which diverges substantially from the
> long-circulated upstream original (which used global SCWS state + token-id
> dispatch). Where the README still describes the old behavior, this is flagged.

## Domain & purpose

zhparser is a PostgreSQL **text-search parser** (`CREATE TEXT SEARCH PARSER`),
not an index AM. It plugs into core PG's existing `tsvector`/`tsquery`/GIN FTS
stack at the *tokenizer* seam: where the built-in `default` parser can only
break CJK text into single characters (no whitespace word boundaries in
Chinese), zhparser delegates segmentation to the embedded **SCWS** (Simple
Chinese Word Segmentation) C library, producing dictionary-driven word tokens
with part-of-speech attributes `[from-README: README.md:4-5]`. The user then
builds a `TEXT SEARCH CONFIGURATION` over the `zhparser` parser and maps the
POS token types to dictionaries (e.g. `ADD MAPPING FOR n,v,a,i,e,l WITH
simple`) `[from-README: README.md:139-143]`. So unlike PGroonga/ZomboDB (which
replace the whole index AM with a foreign engine), zhparser swaps out *only*
the parser callback table and lets core PG keep ownership of `tsvector`
storage, GIN indexing, ranking, and MVCC.

## How it hooks into PG

- **The 5-callback FTS parser API.** The SQL bootstrap registers four C
  functions and a core HEADLINE, wired into a parser via `CREATE TEXT SEARCH
  PARSER`:
  ```sql
  CREATE TEXT SEARCH PARSER zhparser (
      START    = zhprs_start,
      GETTOKEN = zhprs_getlexeme,
      END      = zhprs_end,
      HEADLINE = pg_catalog.prsd_headline,
      LEXTYPES = zhprs_lextype );
  ```
  `[verified-by-code: zhparser--2.4.sql:21-27]`. Note the HEADLINE callback is
  **borrowed from core** (`pg_catalog.prsd_headline`) — zhparser writes a
  segmenter, not a headline generator, and reuses PG's generic one
  `[verified-by-code: zhparser--2.4.sql:25]`. This populates a row in
  `pg_ts_parser` (one per `CREATE TEXT SEARCH PARSER`) `[inferred]`.

- **`internal`-typed glue, exactly like core parsers.** The callbacks take/return
  `internal` (`zhprs_start(internal,int4)` returns `internal`;
  `zhprs_getlexeme(internal,internal,internal)`; etc.)
  `[verified-by-code: zhparser--2.4.sql:1-19]`. The contract matches
  `src/backend/tsearch/wparser_def.c`'s default parser: START is handed
  `(char *buf, int len)` and returns an opaque state pointer; GETTOKEN fills
  `char **token, int *len` and returns the int token-type id; END frees
  `[verified-by-code: zhparser.c:576-708]`.

- **`PG_FUNCTION_INFO_V1` + `_PG_init`.** Four V1 fmgr entry points are declared
  `[verified-by-code: zhparser.c:98-101]`, and `_PG_init` registers all GUCs
  (it does NOT stand up a second engine in postmaster — SCWS is lazy-loaded
  per backend) `[verified-by-code: zhparser.c:290-371]`. `PG_MODULE_MAGIC` at
  `zhparser.c:33`.

- **GUCs (`zhparser.*`).** Eight custom GUCs: `dict_in_memory` (PGC_BACKEND),
  `extra_dicts` (PGC_BACKEND, string, with a `check_extra_dicts` hook),
  `punctuation_ignore`, `seg_with_duality`, `multi_short`, `multi_duality`,
  `multi_zmain`, `multi_zall` (all PGC_USERSET)
  `[verified-by-code: zhparser.c:293-366]`. The two dictionary-affecting GUCs
  are PGC_BACKEND specifically because the dict is loaded once at first-use per
  backend and can't be re-read mid-session
  `[verified-by-code: zhparser.c:299,308; from-README: README.md:128]`.
  `MarkGUCPrefixReserved("zhparser")` is called on PG ≥ 15
  `[verified-by-code: zhparser.c:368-370]`.

## Where it diverges from core idioms

1. **Token "types" are SCWS POS chars, not core token-class ids.** Core
   parsers number tokens by a fixed enumeration (ASCIIWORD, NUMWORD, EMAIL,
   URL, …) defined in `wparser_def.c`. zhparser instead exposes SCWS's
   part-of-speech alphabet `a..z` directly as the lextype table — 26 entries,
   `lexid` = the ASCII code of the POS letter, alias = the letter, descr = a
   bilingual gloss (e.g. `{'n',"n","noun,名词"}`, `{'v',"v","verb,动词"}`)
   `[verified-by-code: zhparser.c:117-149, 720-735]`. `zhprs_getlexeme` reads
   `curr->attr[0]` and clamps it to `['a','z']`, mapping anything out of range
   to `'x'` (unknown) `[verified-by-code: zhparser.c:645-657]`. So the
   README's `tokid 110/118/97 …` are just the ASCII codes of `n/v/a`
   `[inferred from README.md:25-42 vs zhparser.c:127-148]`. A subtle bug-fix:
   the comment notes the original restricted to `['a','x']`, silently dropping
   `'y'` (modal) and `'z'` (status) `[from-comment: zhparser.c:648-653]`.

2. **The token text is a pointer INTO the caller's buffer — zero-copy.**
   `zhprs_getlexeme` sets `*t = pst->buffer + curr->off` and `*tlen =
   curr->len` `[verified-by-code: zhparser.c:659-660]`. It never `palloc`s the
   token; it returns a `(offset,len)` window over the original text the START
   callback was handed (`pst->buffer = PG_GETARG_POINTER(0)`)
   `[verified-by-code: zhparser.c:611]`. This matches the core parser contract
   but means SCWS's UTF-8 byte offsets must line up exactly with PG's — hence
   `scws_set_charset(newscws,"utf-8")` is hard-wired
   `[verified-by-code: zhparser.c:416]`.

3. **External-library state: a per-backend "master" SCWS + per-call fork.**
   This is the headline divergence. SCWS is a C library with mutable
   per-instance state (loaded dict, rules, ignore/duality/multi flags). The
   hardened revision keeps ONE lazy-loaded `master_scws` per backend (process-
   local `static`, dict loaded once via `ensure_master_loaded`)
   `[verified-by-code: zhparser.c:88-89, 391-541]`, then in every
   `zhprs_start` calls `scws_fork(master_scws)` to get a cheap clone and
   applies the session's user flags to the *fork only*, so concurrent parser
   invocations in one backend (nested SRFs, subqueries) can't trample shared
   state `[verified-by-code: zhparser.c:79-86, 593-608; from-comment]`. There
   is **no shared memory and no cross-backend sharing of the SCWS handle** —
   every backend loads its own master. Dictionary *bytes* are shared only via
   the OS page cache when mmap'd (see #4). On a persistent load failure the
   backend caches `master_load_failed` so it doesn't retry every call
   `[verified-by-code: zhparser.c:89, 404-414]`.

4. **Dictionary memory: mmap-by-default, not palloc, not shmem.** The dict
   (`dict.utf8.xdb`, ~14MB) lives outside any MemoryContext. With the default
   (`dict_in_memory=false`) SCWS opens the `.xdb` via its own `fmap`/mmap, so
   the ~14MB is shared read-only across backends through the kernel page cache;
   setting `SCWS_XDICT_MEM` slurps it into private heap and duplicates it per
   backend `[from-comment: zhparser.c:209-223; verified-by-code: 219-223]`.
   This is a deliberate, documented choice — the comment explicitly explains
   that SCWS has no public "mmap flag" and relies on the absence of
   `SCWS_XDICT_MEM` `[from-comment: zhparser.c:209-218]`.

5. **Per-call cleanup via MemoryContext reset callbacks, not pfree.** Because
   the forked SCWS handle and its result cursor are foreign allocations, they
   can't be reclaimed by a context reset alone. `zhprs_start` registers a
   `MemoryContextCallback` (`parser_state_cleanup`) on `CurrentMemoryContext`
   so that on ANY unwind (ERROR, txn abort) the fork + result are freed
   `[verified-by-code: zhparser.c:543-569, 615-619]`. `zhprs_end` additionally
   frees eagerly to keep RSS flat across long `to_tsvector` loops
   `[verified-by-code: zhparser.c:680-708; from-comment:685-692]`. This is the
   classic foreign-allocator-meets-longjmp divergence (cf. PGroonga's manual
   `grn_obj` close discipline).

6. **Catalog convention: a user schema + a COPY-to-file custom dict, not a
   catalog table read at runtime.** Custom words live in a user table
   `zhparser.zhprs_custom_word(word PK, tf, idf, attr CHECK(@|!))`
   `[verified-by-code: zhparser--2.4.sql:30-37]`, but the C side never reads
   that table — instead `sync_zhprs_custom_word()` COPYs it out to a
   **filesystem dict** `DataDir/base/zhprs_dict_<dbname>.txt`, which SCWS then
   loads `[verified-by-code: zhparser--2.4.sql:52-88; zhparser.c:440-446]`.
   So the dict is **per-database** (named by `current_database()`), edits
   require a `sync` + a **fresh connection** to take effect (the master is
   loaded once per backend) `[from-README: README.md:179, 201; inferred]`.
   This is a serialize-catalog-to-a-file pattern alien to core FTS dictionaries
   (which read `pg_ts_dict`/template init at parse time).

7. **Path-traversal hardening the core parser never needs.** Because dict
   filenames flow from a GUC and from `current_database()` into `snprintf`
   paths under `share/tsearch_data` and `DataDir/base`, the hardened revision
   adds `is_safe_dict_filename` (whitelist `[A-Za-z0-9_.-]`, reject `..`,
   leading `.`/`-`, require `.txt`/`.xdb`) and `is_safe_database_name`
   (`[A-Za-z0-9_]` only, else skip the custom dict with a LOG)
   `[verified-by-code: zhparser.c:162-207, 229-273, 431-447]`. The plpgsql
   `sync_zhprs_custom_word` mirrors this with a `^[A-Za-z0-9_]+$` guard and
   `format(... %L ...)` quoting `[verified-by-code: zhparser--2.4.sql:67-85]`.
   Core FTS parsers take no filesystem input, so none of this exists upstream.

8. **`pstrdup` symbol collision with SCWS, fenced in a header.** SCWS < 1.2.3
   declares a function `pstrdup`, colliding with PG's `pstrdup` macro.
   `zhparser.h` `#undef`s PG's macro, aliases SCWS's to `scws_pstrdup` around
   the `#include "scws.h"`, then restores PG's macro — an ABI-collision dance
   that is pure foreign-library-integration friction
   `[verified-by-code: zhparser.h:4-30; from-comment]`.

## Notable design decisions (with cites)

- **Lazy per-backend master + `scws_fork` per call** is the concurrency-safety
  spine: `ensure_master_loaded()` builds the master once
  (`zhparser.c:391-541`), `scws_fork` clones it per `zhprs_start`
  (`zhparser.c:593`), session GUCs apply to the fork only (`zhparser.c:606-608`)
  `[verified-by-code]`.
- **Inheritance of flags onto the master so forks start correct:**
  `scws_set_ignore/duality/multi` are set on the master at load time AND
  re-applied to the fork, so the first call after load and every later call see
  consistent flags `[verified-by-code: zhparser.c:535-538, 606-608]`.
- **Dict load order = priority order (low→high):** built-in main dict, then
  per-DB custom dict, then `extra_dicts` in listed order; later adds override
  earlier `[verified-by-code: zhparser.c:422-521; from-README: README.md:124]`.
- **`.txt` vs `.xdb` dispatch by extension** (`SCWS_XDICT_TXT` /
  `SCWS_XDICT_XDB`), validated twice (GUC check hook + load-time re-validation,
  "defence in depth") `[verified-by-code: zhparser.c:260-267, 470-509]`.
- **Result-cursor refill loop:** when a SCWS result batch is exhausted
  (`pst->curr == NULL`) GETTOKEN frees it and pulls the next `scws_get_result`
  batch, so multi-batch segmentation streams transparently
  `[verified-by-code: zhparser.c:662-668]`.
- **`_PG_fini` frees the master** (`scws_free`) — symmetric teardown, though
  PG rarely calls `_PG_fini` `[verified-by-code: zhparser.c:373-381]`.

## Links into corpus

- FTS parser seam: [[knowledge/subsystems/parser-and-rewrite]] for the broader
  parse pipeline; the relevant core analog is `src/backend/tsearch/`'s
  `pg_ts_parser` + `prsd_*` callbacks (default parser in `wparser_def.c`,
  HEADLINE `prsd_headline`) — zhparser substitutes only START/GETTOKEN/END.
- fmgr / `internal`-typed C functions: [[knowledge/idioms/fmgr]] —
  `PG_FUNCTION_INFO_V1`, `PG_GETARG_POINTER`, opaque-state passing.
- Memory discipline: [[knowledge/idioms/memory-contexts]],
  [[knowledge/idioms/memory-context-api-and-dispatch]] — the
  `MemoryContextRegisterResetCallback` foreign-resource-cleanup idiom.
- GUC wiring: [[knowledge/idioms/guc-variables]] —
  `DefineCustomBool/StringVariable`, check hooks, `MarkGUCPrefixReserved`,
  PGC_BACKEND vs PGC_USERSET.
- Catalog: [[knowledge/idioms/catalog-conventions]] — `CREATE TEXT SEARCH
  PARSER` / `pg_ts_parser` registration.
- Sibling FTS-dictionary contrib (read the catalog table at runtime, contrast
  zhparser's serialize-to-file): [[knowledge/subsystems/contrib-dict_int]],
  [[knowledge/subsystems/contrib-dict_xsyn]],
  [[knowledge/subsystems/contrib-pg_trgm]].
- **Sibling "FTS / search" ideologies:**
  - [[knowledge/ideologies/pgroonga]] — also embeds a foreign C search engine,
    but as an **index AM** that owns storage + MVCC + WAL. **Contrast:**
    zhparser is far lighter — it only replaces the *tokenizer* and leaves
    `tsvector`/GIN/MVCC/ranking entirely to core PG. No custom storage, no
    WAL bridge, no ctid recheck.
  - [[knowledge/ideologies/zombodb]] — remote Elasticsearch index AM; opposite
    extreme of integration weight from zhparser.
  - [[knowledge/ideologies/pg_textsearch]] — BM25 ranking as a native AM;
    contrast with zhparser which adds no ranking, only segmentation.

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/zhparser/zhparser | 404 (wrong namespace; Docker-Hub org, not source repo) |
| https://api.github.com/search/repositories?q=zhparser+scws | 200 (resolved real repo: `amutu/zhparser`, master, 858★) |
| https://api.github.com/repos/amutu/zhparser/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/zhparser.c | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/zhparser.h | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/zhparser.control | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/zhparser--2.4.sql | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/README.md | 200 |
| https://raw.githubusercontent.com/amutu/zhparser/master/META.json | 200 |

**Fetch notes / substitutions:**
- Manifest hint `zhparser/zhparser` was the Docker-Hub namespace; real source
  is `amutu/zhparser` (resolved via the GitHub search API). No content gap.
- Manifest hint `zhprs_test.c` does **not exist** in the tree. Tests instead
  live as SQL/golden-output pairs: `sql/zhparser.sql` +
  `expected/zhparser*.out`, plus `tests/test_invariant_zhparser--2.1.sql` and
  `regress/` driver scripts. Not fetched (not load-bearing for the divergence
  doc); noted as the test surface.
- `zhparser.control` resolved at the repo root (NOT a `*.control.in`).
- The fetched `zhparser.c` self-identifies as a "Hardened revision (PG
  16/17/18)" (`zhparser.c:6-13`); divergences #3/#5/#7 and the `['a','z']` fix
  are specific to this revision and differ from the historically-circulated
  upstream (global SCWS state, token-id dispatch). Flagged inline.
