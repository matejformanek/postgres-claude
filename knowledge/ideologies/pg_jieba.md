# pg_jieba — ideology / divergence-from-core notes

> Extension: `jaiminpan/pg_jieba` @ `master` (control reports `default_version =
> '1.1.1'`, `relocatable = true`, `module_pathname = '$libdir/pg_jieba'`)
> `[verified-by-code: pg_jieba.control:1-4]`. 412★, C/C++. One durable "how this
> diverges from core PG design" doc. Line cites are into the upstream pg_jieba
> tree (`pg_jieba.c`, `jieba.h`, `jieba.cpp`, `jieba_token.h`, `pg_jieba.sql`),
> NOT into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** pg_jieba is the direct twin of [[knowledge/ideologies/zhparser]] —
> both are Chinese-segmentation **text-search parsers** plugged into core's
> `CREATE TEXT SEARCH PARSER` seam. They differ in engine (cppjieba C++ vs SCWS
> C), in concurrency model, and crucially in how they cross the foreign-library
> boundary. Read this doc against the zhparser one; the contrasts are the payload.

## Domain & purpose

pg_jieba is a PostgreSQL **text-search parser** (`CREATE TEXT SEARCH PARSER`),
not an index AM. Chinese has no whitespace word boundaries, so core's built-in
`default` parser degrades CJK text to single characters. pg_jieba delegates
segmentation to the embedded **cppjieba** (a C++ port of the Python `jieba`
segmenter, vendored as a git submodule under `libjieba/`), producing
dictionary-driven word tokens annotated with part-of-speech tags
`[from-README: README.md:7; from-comment: jieba.cpp:20]`. The user picks one of
four pre-built configurations exposed by the install SQL — `jiebacfg` (Mix:
MP+HMM, recommended), `jiebamp` (max-probability only), `jiebahmm` (HMM only),
`jiebaqry` (query/search-engine mode) — each a `TEXT SEARCH CONFIGURATION` over
a distinct parser that selects a cppjieba segmenter
`[verified-by-code: pg_jieba.sql:42-90; from-README: README.md (config table)]`.
Like zhparser (and unlike PGroonga / ZomboDB which replace the whole index AM),
pg_jieba swaps out **only the tokenizer callback table** and lets core PG keep
ownership of `tsvector` storage, GIN indexing, ranking, MVCC, and headline
generation (`HEADLINE = pg_catalog.prsd_headline`)
`[verified-by-code: pg_jieba.sql:46-52]`.

## How it hooks into PG

- **The 4+1-callback FTS parser API.** The install SQL registers eight C
  functions and wires four parsers, each with the core HEADLINE:
  ```sql
  CREATE TEXT SEARCH PARSER jieba (
      START    = jieba_start,
      GETTOKEN = jieba_gettoken,
      END      = jieba_end,
      LEXTYPES = jieba_lextype,
      HEADLINE = pg_catalog.prsd_headline );
  ```
  `[verified-by-code: pg_jieba.sql:46-52]`. Distinct START functions
  (`jieba_start` / `jieba_query_start` / `jieba_mp_start` / `jieba_hmm_start`)
  select the segmenter mode, while GETTOKEN/END/LEXTYPES are shared across all
  four parsers `[verified-by-code: pg_jieba.sql:42-90]`. As in zhparser, HEADLINE
  is **borrowed from core** (`pg_catalog.prsd_headline`) — pg_jieba writes a
  segmenter, not a headline generator `[verified-by-code: pg_jieba.sql:50]`.

- **`internal`-typed glue, exactly like core parsers.** Callbacks take/return
  `internal`: `jieba_start(internal, integer)` returns `internal`;
  `jieba_gettoken(internal, internal, internal)` returns `internal`;
  `jieba_end(internal)` returns `void`; `jieba_lextype(internal)`
  `[verified-by-code: pg_jieba.sql:1-38]`. The C side matches the core parser
  contract: START is handed `(char *buf, int len)` and returns an opaque state
  pointer (`ParserState`); GETTOKEN fills `char **t, int *tlen` and returns the
  int token-type id; END frees `[verified-by-code: pg_jieba.c:33-39, 134-228]`.

- **`PG_FUNCTION_INFO_V1` + `_PG_init`/`_PG_fini`.** Eight V1 fmgr entry points
  are declared `[verified-by-code: pg_jieba.c:48-70]`; `PG_MODULE_MAGIC` at
  `pg_jieba.c:25`. `_PG_init` registers GUCs **only when loaded via
  shared_preload_libraries** (`process_shared_preload_libraries_in_progress`),
  else it emits a LOG that variables can't be configured, then unconditionally
  calls `recompute_dicts_path()` to build the dictionary
  `[verified-by-code: pg_jieba.c:101-117]`. `_PG_fini` frees the engine
  (`Jieba_Free`) — symmetric teardown though PG rarely calls `_PG_fini`
  `[verified-by-code: pg_jieba.c:122-129]`.

- **GUCs (`pg_jieba.*`), all PGC_POSTMASTER.** Three string GUCs:
  `pg_jieba.hmm_model` (default `jieba_hmm`), `pg_jieba.base_dict` (default
  `jieba_base`), `pg_jieba.user_dict` (CSV list, default `jieba_user`, with a
  `check_user_dict`/`assign_user_dict` hook pair)
  `[verified-by-code: pg_jieba.c:257-289]`. All three are `PGC_POSTMASTER`
  precisely because the dictionary is loaded once at postmaster startup and the
  segmenter object is process-global — they cannot be re-read mid-session
  `[verified-by-code: pg_jieba.c:265,275,285; inferred]`.

- **A SQL-callable dictionary reload.** `jieba_reload_dict()` flips
  `userDictsValid = false` and re-runs `recompute_dicts_path()`, rebuilding the
  cppjieba engine in place so an updated `jieba_user.dict` takes effect without a
  postmaster restart `[verified-by-code: pg_jieba.c:249-255]`. (But see
  divergence #6 — the assign hook that *should* invalidate on GUC change is
  commented out, so this manual call is the only reload path.)

## Where it diverges from core idioms

1. **A C↔C++ FFI boundary with NO exception firewall — the headline
   divergence.** pg_jieba is split in two: `pg_jieba.c` is pure PG-facing C
   (fmgr, palloc, GUCs), and `jieba.cpp` wraps cppjieba behind an `extern "C"`
   shim (`Jieba_New/Free/Cut/GetNext`, `ParStat_New/Free`)
   `[verified-by-code: jieba.h:17-48; jieba.cpp:25-27,51-170]`. The C side calls
   straight through this boundary (`pst->stat = Jieba_Cut(...)`,
   `Jieba_GetNext(...)`) `[verified-by-code: pg_jieba.c:143,198]`. The shim
   functions allocate with C++ `new` (`new JiebaCtx()`, `new vector<string>()`,
   `new DictTrie(...)`) and call `MixSegment::Cut`, `DictTrie`/`HMMModel`
   constructors — **all of which can throw** (`std::bad_alloc`, cppjieba file
   errors) `[verified-by-code: jieba.cpp:54-67, 84-117]`. **There is no
   `try{...}catch(...)` anywhere in jieba.cpp.** A C++ exception unwinding across
   the `extern "C"` frame into PG's C call site is undefined behaviour: it
   bypasses PG's `sigsetjmp`/`PG_TRY` error stack and any in-flight palloc
   cleanup. This is the exact inverse of the disciplined boundaries elsewhere in
   the corpus: [[knowledge/ideologies/pgrouting]] wraps every C++ entry in a
   catch-all that funnels errors to out-params before the C side `ereport`s, and
   [[knowledge/ideologies/pgrx]] wraps every C call in `pg_guard_ffi_boundary`
   with `sigsetjmp` to bridge ereport-longjmp ↔ Rust unwind. pg_jieba does
   neither — it trusts cppjieba not to throw `[inferred from absence; verified
   no catch in jieba.cpp:1-175]`.

2. **`MemoryContextSwitchTo(TopMemoryContext)` around `new` is a no-op for the
   thing it appears to protect.** `recompute_dicts_path` switches to
   `TopMemoryContext`, then calls `Jieba_New(...)` "to save it in permanent
   storage" `[verified-by-code: pg_jieba.c:314-323]`. But `Jieba_New` allocates
   the dict trie, HMM model, and segmenters with C++ `new`
   `[verified-by-code: jieba.cpp:54-60]` — these land on the **C++ heap**, which
   is entirely outside PG's MemoryContext machinery, so the context switch has no
   effect on them. The only allocation the switch actually governs is the
   `pstrdup(user_dicts)` on the line above the `Jieba_New` call
   `[verified-by-code: pg_jieba.c:316-321]`. The engine lives for backend life
   regardless, but it is invisible to `MemoryContextStats`, never reset by error
   unwind, and freed only by the explicit `Jieba_Free` in `recompute_dicts_path`
   (on rebuild) or `_PG_fini` `[verified-by-code: pg_jieba.c:330-334, 122-129]`.
   Contrast zhparser, which is acutely aware its SCWS handle is foreign and
   registers `MemoryContextRegisterResetCallback` to free it on any unwind
   ([[knowledge/ideologies/zhparser]] divergence #5); pg_jieba has no such
   callback, so a longjmp out of `Jieba_Cut` mid-segmentation leaks the
   per-call `vector<string>` (see #4).

3. **Token type = POS string looked up through a C++ `unordered_map`, not an
   ASCII-code clamp.** Core parsers number tokens by a fixed enumeration
   (ASCIIWORD, NUMWORD, …). pg_jieba ships a 56-entry POS table `lex_descr[]` in
   `jieba_token.h` (`{ .token="n", .descr="noun"}`, `{ .token="eng",
   .descr="letter"}`, …) `[verified-by-code: jieba_token.h:24-40]`. `Jieba_New`
   loads this table into a `std::unordered_map<string,int> lex_id_` keyed on the
   POS string `[verified-by-code: jieba.cpp:39, 62-65]`; `Jieba_LookupType`
   calls cppjieba's `MixSegment::LookupTag` to get the POS for a word and maps it
   back to the table index (0 = unknown if not found)
   `[verified-by-code: jieba.cpp:142-154]`. `LASTNUM` (the lextype count) is
   `sizeof(lex_descr)/sizeof(lex_descr[0]) - 1`, computed in the C side
   `[verified-by-code: pg_jieba.c:28]`, and `jieba_lextype` materialises the
   table as a palloc'd `LexDescr[]` for `pg_ts_parser`
   `[verified-by-code: pg_jieba.c:230-247]`. This is **richer but heavier** than
   zhparser's "lexid = ASCII code of the POS letter, clamped to ['a','z']"
   ([[knowledge/ideologies/zhparser]] divergence #1): pg_jieba supports
   multi-char tags (`eng`, `nz`, `mq`, `nrt`) that don't fit in one byte, at the
   cost of a hash lookup per token.

4. **Per-call token storage is a heap `vector<string>`, with a `unsigned char`
   length-truncation footgun.** `Jieba_Cut` builds a fresh
   `new vector<string>()`, runs the segmenter into it, and hands back a `ParStat`
   holding the vector + an iterator `[verified-by-code: jieba.cpp:84-117]`.
   `Jieba_GetNext` returns `result->str = cur_iter->c_str()` — a pointer **into
   the live `std::string` inside that vector**, valid until `ParStat_Free`
   `[verified-by-code: jieba.cpp:119-140]`. So unlike zhparser (which returns a
   zero-copy `(offset,len)` window into the *caller's* buffer), pg_jieba's tokens
   live in cppjieba-owned C++ memory and the C side copies them out via the core
   FTS machinery. The sting: `JiebaResult.len` is declared `unsigned char`
   `[verified-by-code: jieba.h:27]` and assigned `result->len =
   cur_iter->length()` `[verified-by-code: jieba.cpp:134]` — any token whose
   UTF-8 byte length exceeds 255 is silently truncated mod 256. (Chinese words
   are short, so this rarely bites, but it is a real on-the-wire limitation core
   never has.) Cleanup is eager-only: `jieba_end` calls `ParStat_Free` (which
   `delete`s the vector) and `pfree`s the `ParserState`
   `[verified-by-code: pg_jieba.c:216-228; jieba.cpp:164-170]` — but because
   there is no reset callback (#2), an ERROR thrown between START and END leaks
   the vector.

5. **One process-global engine shared by every parser invocation — no
   per-call fork.** pg_jieba keeps a single `static JiebaCtx* jieba` per backend
   `[verified-by-code: pg_jieba.c:81]`, built once and pointed to by every
   `ParserState.ctx` `[verified-by-code: pg_jieba.c:141,155,169,183]`. The
   `JiebaCtx` bundles all four segmenters + the shared `DictTrie`/`HMMModel`
   `[verified-by-code: jieba.cpp:29-40]`. This is safe under PG's
   one-process-per-backend model only because cppjieba's `Cut`/`LookupTag` are
   read-only against the immutable trie/model after construction — there is **no
   mutable per-session state to protect**, so pg_jieba needs nothing like
   zhparser's `scws_fork`-per-call clone ([[knowledge/ideologies/zhparser]]
   divergence #3). The flip side: there is exactly one dictionary configuration
   per backend (GUC-fixed at postmaster start), with none of zhparser's
   per-session flag tuning.

6. **A dead assign hook: changing `pg_jieba.user_dict` does nothing until a
   manual reload.** `assign_user_dict` is registered as the GUC assign hook
   `[verified-by-code: pg_jieba.c:287, 380-389]`, but its only meaningful line —
   `userDictsValid = false` — is **commented out**
   `[verified-by-code: pg_jieba.c:388]`, with a comment claiming it defers work
   "until it's needed." Combined with the GUC being `PGC_POSTMASTER` (so it can't
   change at runtime anyway), the effect is that the dictionary is only ever
   rebuilt by `_PG_init` at startup or by an explicit `SELECT
   jieba_reload_dict()` call `[verified-by-code: pg_jieba.c:249-255]`. The core
   GUC idiom — assign hook invalidates derived state, recompute lazily — is
   present in skeleton but disabled, leaving the manual SQL function as the real
   reload seam.

7. **Path-traversal guard borrowed near-verbatim from core ts_locale.** Because
   dict basenames flow from GUCs into `snprintf` paths under
   `share/tsearch_data`, `jieba_get_tsearch_config_filename` whitelists the
   basename to `[a-z0-9_.]` and `ereport(ERROR, ...
   ERRCODE_INVALID_PARAMETER_VALUE)` on anything else, then builds
   `<sharepath>/tsearch_data/<basename>.<ext>` via `get_share_path` +
   `my_exec_path` `[verified-by-code: pg_jieba.c:399-427]`. This is lifted almost
   word-for-word (comment included) from core's `get_tsearch_config_filename` in
   `src/backend/tsearch/ts_locale.c` — a defensive idiom core FTS *templates*
   already own, re-instantiated here because the parser, not a dictionary
   template, is doing the file resolution. The CSV `pg_jieba.user_dict` is split
   with core's `SplitIdentifierString` and each name resolved the same way, joined
   with `;` for cppjieba `[verified-by-code: pg_jieba.c:432-480]`.

## Notable design decisions (with cites)

- **Mode selection by distinct START function, shared GETTOKEN/END.** Four START
  entry points each call `Jieba_Cut(..., MODE_*)` with `MODE_MIX/MP/HMM/QRY`
  `[verified-by-code: pg_jieba.c:134-188; jieba.h:31-34]`; the mode picks which
  pre-built segmenter (`mix_seg_`/`mp_seg_`/`hmm_seg_`/`query_seg_`) runs
  `[verified-by-code: jieba.cpp:92-108]`. Keeps the SQL surface to one shared
  GETTOKEN while exposing four configurations.
- **GETTOKEN end-of-stream contract.** When `Jieba_GetNext` returns NULL,
  `jieba_gettoken` sets `*tlen = 0` and returns type `0`, the core "no more
  tokens" signal `[verified-by-code: pg_jieba.c:198-213]`.
- **Engine rebuild is destroy-then-create, guarded by `userDictsValid`.**
  `recompute_dicts_path` early-returns if already valid, builds the new engine,
  frees the old (`Jieba_Free(jieba)`), then assigns and marks valid — so a
  failed `Jieba_New` (if it didn't throw) would leave the old engine in place
  `[verified-by-code: pg_jieba.c:291-343]`.
- **`extern "C"` linkage spans both the struct definitions and the API.** The
  opaque `JiebaCtx`/`ParStat` structs are *defined* inside the `extern "C"`
  block in jieba.cpp (only forward-declared in jieba.h), so the C side only ever
  holds opaque pointers `[verified-by-code: jieba.h:21-22; jieba.cpp:25-47]` —
  textbook opaque-handle FFI.
- **`_PG_fini` symmetric free** mirrors zhparser; both free the foreign engine on
  unload despite PG rarely calling `_PG_fini`
  `[verified-by-code: pg_jieba.c:122-129]`.

## Links into corpus

- FTS parser seam: the core analog is `src/backend/tsearch/`'s `pg_ts_parser` +
  `prsd_*` callbacks (default parser in `wparser_def.c`, HEADLINE
  `prsd_headline`, path helper in `ts_locale.c`) — pg_jieba substitutes only
  START/GETTOKEN/END/LEXTYPES.
- fmgr / `internal`-typed C functions: [[knowledge/idioms/fmgr]] —
  `PG_FUNCTION_INFO_V1`, `PG_GETARG_POINTER`, opaque-state passing.
- Memory discipline: [[knowledge/idioms/memory-contexts]] — and the **anti**-idiom
  here: a `MemoryContextSwitchTo` that doesn't govern the C++ `new` it wraps
  (#2), and the missing `MemoryContextRegisterResetCallback` for the foreign
  per-call vector (#4).
- GUC wiring: [[knowledge/idioms/guc-variables]] —
  `DefineCustomStringVariable`, check/assign hooks (and a disabled one, #6),
  PGC_POSTMASTER.
- Catalog: [[knowledge/idioms/catalog-conventions]] — `CREATE TEXT SEARCH
  PARSER` / `pg_ts_parser` registration.
- **Sibling FTS / search ideologies (contrast):**
  - [[knowledge/ideologies/zhparser]] — the direct twin (Chinese segmentation
    via the same 5-callback parser API). **Contrasts:** cppjieba C++ vs SCWS C;
    process-global engine vs per-call `scws_fork`; POS-string `unordered_map`
    lookup vs ASCII-code clamp; **no** exception/cleanup firewall vs zhparser's
    reset-callback + path hardening; PGC_POSTMASTER GUCs vs PGC_BACKEND.
  - [[knowledge/ideologies/pgroonga]] — embeds a foreign C search engine as a
    full **index AM** (owns storage + MVCC + WAL); pg_jieba is far lighter,
    replacing only the tokenizer.
  - [[knowledge/ideologies/zombodb]] — remote Elasticsearch index AM; opposite
    extreme of integration weight.
  - [[knowledge/ideologies/pg_textsearch]] — BM25 ranking as a native AM;
    pg_jieba adds no ranking, only segmentation.
- **Sibling C++ FFI-boundary ideologies (contrast on exception handling):**
  - [[knowledge/ideologies/pgrouting]] — C/fmgr SRF marshals into a Boost-Graph
    C++ driver behind a load-bearing catch-all firewall. **pg_jieba omits this
    firewall entirely** — the cleanest negative example in the corpus of the
    C++-exception-across-extern-"C" hazard.
  - [[knowledge/ideologies/pgrx]] — `pg_guard_ffi_boundary` bridges
    ereport-longjmp ↔ Rust unwind at every call.

## Sources

| URL | HTTP |
|---|---|
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/README.md | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/pg_jieba.control | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/pg_jieba.cpp | 404 (manifest typo — no such file) |
| https://api.github.com/repos/jaiminpan/pg_jieba/git/trees/master?recursive=1 | 200 (resolved real source: pg_jieba.c + jieba.cpp/.h) |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/pg_jieba.c | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/jieba.h | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/jieba.cpp | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/jieba_token.h | 200 |
| https://raw.githubusercontent.com/jaiminpan/pg_jieba/master/pg_jieba.sql | 200 |

**Fetch notes / substitutions:**
- Manifest hint `pg_jieba.cpp` is a **404** — the repo's IDENTIFICATION comments
  still say `.cpp` (a rename relic), but the PG-facing source is `pg_jieba.c`
  `[verified-by-code: pg_jieba.c:1-12 header says "IDENTIFICATION pg_jieba.cpp"]`.
  Resolved the real layout via the tree API and fetched `pg_jieba.c` +
  `jieba.cpp`/`jieba.h`/`jieba_token.h`/`pg_jieba.sql` for the C/C++ split, GUC,
  and divergence story.
- cppjieba itself (`libjieba/` submodule) is **not in the repo tree** (git
  submodule), so claims about `MixSegment::Cut`/`LookupTag` reentrancy and
  throw-behaviour are `[inferred]` from the call sites, not verified against
  cppjieba source.
- `pg_jieba.control` resolved at the repo root (NOT a `*.control.in`).
- Test surface (`sql/`/`expected/` golden pairs) not fetched — not load-bearing
  for the divergence doc.
</content>
