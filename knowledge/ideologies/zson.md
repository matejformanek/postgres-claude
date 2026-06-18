# zson — a custom JSONB-skin type whose compression dictionary lives in a user catalog table, cached per-backend with a wall-clock TTL

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `postgrespro/zson` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against files fetched
> on 2026-06-18 (see Sources footer). Read alongside
> `[[knowledge/ideologies/postgresql-hll]]` (the other "custom base type as a
> thin skin over an existing representation" case) and
> `[[knowledge/ideologies/uuidv47]]` (a type whose I/O depends on out-of-band
> session/catalog state, like zson does).

## Domain & purpose

zson is "a PostgreSQL extension for transparent JSONB compression. Compression
is based on a shared dictionary of strings most frequently used in specific
JSONB documents (not only keys, but also values, array elements, etc)"
(`README.md:7-9`) `[from-README]`. It registers a single base type, `zson`,
which is a drop-in replacement for `jsonb`: you store `zson` columns, query them
with the same `->`/`->>` operators (via an implicit cast back to `jsonb`), and
on disk each value is a dictionary-substituted, PGLZ-friendly byte string
instead of a raw `jsonb` image (`README.md:109-122`, `zson--1.1.sql:120-138`)
`[verified-by-code]`.

The reason to document it: zson is the corpus's clearest example of a **custom
type whose on-disk encoding is parameterized by mutable data in a user-visible
catalog table** (`zson_dict`). Core compression (TOAST/PGLZ/LZ4) is dictionary-
*less* and self-contained — a compressed datum carries everything needed to
decompress it. A `zson` value, by contrast, is meaningless without the matching
row-set of `zson_dict`; the value stores only a *dict_id* header and 16-bit
*codes* that index into a dictionary loaded separately (`zson.c:11-23,
571-582`). This is the "shared dictionary compression" idea (cf. Zstandard
trained dictionaries) bolted onto Postgres entirely in extension space, with the
dictionary kept as ordinary heap rows rather than in any core catalog.

## How it hooks into PG

zson is a pure type extension — no `_PG_init`, no hooks, no background worker,
no shared memory. Everything is the type-definition machinery
(`[[knowledge/idioms/fmgr]]`, `[[knowledge/scenarios/add-new-data-type]]`):

- **The type and its I/O**: `CREATE TYPE zson (INTERNALLENGTH = -1, INPUT =
  zson_in, OUTPUT = zson_out, STORAGE = extended)` (`zson--1.1.sql:120-125`)
  `[verified-by-code]`. `STORAGE = extended` means a `zson` datum is itself
  TOASTable and PGLZ-compressed by core *on top of* zson's own dictionary
  substitution — a deliberate two-layer scheme (see "design decisions").
- **The casts that make it a jsonb skin**: `CREATE CAST (jsonb AS zson) … AS
  ASSIGNMENT` and `CREATE CAST (zson AS jsonb) … AS IMPLICIT`
  (`zson--1.1.sql:137-138`) `[verified-by-code]`. The `zson → jsonb` cast is
  **IMPLICIT**, so any operator/function expecting `jsonb` silently upgrades a
  `zson` argument; this is what lets `x -> 'aaa'` work on a `zson` column with
  no operator class of its own (`README.md:119-122`).
- **I/O delegates to core jsonb**: `zson_in` is literally `jsonb_in` then
  `jsonb_to_zson` via `DirectFunctionCall1`, and `zson_out` is `zson_to_jsonb`
  then `jsonb_out` (`zson.c:347-366`) `[verified-by-code]`. zson never parses
  JSON itself — it reuses core's parser/serializer through fmgr, and only owns
  the byte-level transform between a `jsonb` image and its compressed form.
- **The dictionary is a config-dumped user table**: `CREATE TABLE zson_dict
  (dict_id SERIAL, word_id INTEGER, word text, PRIMARY KEY(dict_id, word_id))`
  followed by `SELECT pg_catalog.pg_extension_config_dump('zson_dict', '')`
  (`zson--1.1.sql:6-13`) `[verified-by-code]`. The `pg_extension_config_dump`
  call is the one genuinely-correct catalog-convention touch: it marks the
  table's *data* (not just its schema) to be emitted by `pg_dump`, because the
  dictionary is user data that the type's values structurally depend on
  (cf. `[[knowledge/idioms/catalog-conventions]]`).

## Where it diverges from core idioms

### 1. The decisive divergence: a value's meaning depends on a mutable catalog table, and on a per-backend cache of it

Decompression reads a `dict_id` out of the value header and loads that
dictionary by querying `zson_dict` over SPI (`zson.c:571-582, 95-173`). The
dictionary is **not** carried in the value, so a `zson` datum is only
interpretable in a database where the matching `zson_dict` rows still exist.
The README spells out the data-loss footgun: "If **all** ZSON documents are
migrated to the new dictionary the old one could be safely removed … In general,
it's safer to keep old dictionaries just in case. Gaining a few KB of disk space
is not worth the risk of losing data" (`README.md:151-159`) `[from-README]`.
Core compression has no such cross-row, cross-table dependency.

### 2. Per-backend `malloc`/`calloc` caches outside any MemoryContext, evicted by `gettimeofday` wall-clock TTL

The dictionary cache is a hand-rolled singly-linked list of `DictListItem`
rooted in a file-scope `static DictListItem dictList` (`zson.c:66-93`)
`[verified-by-code]`. Each `Dict` is `calloc`'d (`zson.c:100`), its words
`malloc`'d (`zson.c:145`), and freed with bare `free` (`zson.c:175-184`) — **not**
`palloc`/`pfree` in any MemoryContext. This is a direct violation of the core
memory discipline (`[[knowledge/idioms/memory-contexts]]`): the cache deliberately
lives outside query/transaction context lifetimes because it must survive across
statements for the life of the backend. Eviction is by `gettimeofday(&tv, NULL)`
comparison against `DICT_LIST_TTL_SEC` (120s) and `DICT_LIST_CLEAN_INTERVAL_SEC`
(60s) (`zson.c:76-82, 240-270`). The "current dict_id" is likewise cached in a
`static int32 cachedDictId` refreshed only every `DICT_ID_CACHE_TIME_SEC` = 60s
(`zson.c:87-88, 316-318`) — which is why the README warns "it will take about a
minute before ZSON realizes that there is a new dictionary" (`README.md:133-136`).
Core has no equivalent of "type behavior changes ~60s after you write a catalog
row, on a timer."

### 3. A `Dict` is a ~half-megabyte fixed-size struct, sized for the 16-bit code space

`typedef struct { … Word words[DICT_MAX_WORDS]; uint16
code_to_word[DICT_MAX_WORDS]; } Dict` with `DICT_MAX_WORDS = (1 << 16)`
(`zson.c:50-64`) `[verified-by-code]`. Every loaded dictionary therefore
allocates 65 536 `Word` structs plus a 128 KB `code_to_word` index up front,
regardless of how many words the dictionary actually has. The 16-bit ceiling is
also why `zson_learn` caps the dictionary at `limit 65534` words
(`zson--1.1.sql:70`) and code `0` is reserved as `DICT_INVALID_CODE`
(`zson.c:84-85`).

### 4. SPI prepared plans kept alive forever via `SPI_keepplan`, with `public.`-hardcoded queries

Both lookup plans (`select max(dict_id) …` and `select word_id, word from
public.zson_dict …`) are prepared once into file-scope `static SPIPlanPtr` and
pinned with `SPI_keepplan` so they outlive the `SPI_finish`
(`zson.c:90-91, 108-119, 322-330`) `[verified-by-code]`. The schema is
hardcoded as `public.zson_dict`, which is the mechanical cause of the README's
"Known limitations: Installing ZSON in a schema other than `public` is not
supported" (`README.md:178-180`) `[verified-by-code]`. Cross-ref
`[[knowledge/idioms/spi]]`.

### 5. The on-disk format reserves a 32-byte "PGLZ hint" to cooperate with core's second compression pass

The value layout is `VARHDRSZ · zson_version[u8] · dict_version[u32] ·
decoded_size[u32] · hint[u8 × 32] · (skip/code stream)` (`zson.c:11-23,
41-48`) `[verified-by-code]`. The `PGLZ_HINT_SIZE = 32` leading zero bytes
(`zson.c:48, 387`) exist specifically so that the *outer* `STORAGE = extended`
PGLZ pass has compressible material to latch onto — zson does dictionary
substitution, then lets core PGLZ/TOAST do entropy compression on the result.
`zson_info` reports the ratio of "zson size (without pglz compression)" to jsonb
size (`zson.c:599-621`), making the two-layer model visible to the user.

### 6. Type I/O functions marked `IMMUTABLE` while actually depending on catalog + cache + clock

`zson_in`/`zson_out`/`jsonb_to_zson`/`zson_to_jsonb` are all declared `STRICT
IMMUTABLE` (`zson--1.1.sql:110-135`) `[verified-by-code]`, yet
`jsonb_to_zson` calls `get_current_dict_id()` which runs SPI against
`zson_dict` and consults a time-based cache (`zson.c:489-501`). The output of
"the same input" therefore changes when the dictionary changes — a textbook
`IMMUTABLE`-purity violation, exactly the pattern flagged in
`[[knowledge/ideologies/uuidv47]]` (a type whose I/O reads a GUC) and
`[[knowledge/ideologies/index_advisor]]` ("no C therefore safe" inverted). It
is "transparent" only as long as the dictionary is append-mostly; rewriting or
deleting dictionary rows retroactively changes what stored values decode to.

## Notable design decisions with cites

- **Dictionary matching is a longest-prefix binary search over a
  length-then-byte-sorted word array.** `dict_find_match` binary-searches
  `pdict->words` (kept sorted by `word`), and a `check_next` flag on each entry
  marks "the next word shares this word's full prefix," letting the search walk
  forward to a longer match (`zson.c:54-56, 156-165, 186-232`)
  `[verified-by-code]`. This is how a single pass greedily replaces the longest
  dictionary string at each input offset.
- **The compressed stream is a run of `{skip_bytes, literal bytes, uint16
  code}` records.** `zson_fastcompress` emits a skip count, the un-dictionaried
  literal bytes, then a 2-byte code (0 = none); a 255-skip overflow forces a
  flushed record with a `DICT_INVALID_CODE` (`zson.c:374-425`)
  `[verified-by-code]`. `zson_fastdecompress` is the careful inverse, with
  bounds checks on every `memcpy` against both `encoded_size` and `decoded_size`
  to refuse a malformed/short value rather than overrun (`zson.c:427-486`).
- **`decoded_size` is stored in the header so decompression can `palloc` the
  exact output buffer in one shot** (`zson.c:522, 577`), avoiding a grow-and-
  copy loop — at the cost of trusting the stored size (it is used directly as a
  `palloc` length).
- **`zson_learn` is plpgsql that builds a `UNION ALL` of `zson_extract_strings`
  over sampled rows, ranks strings by frequency, and bulk-inserts the top 65534
  into a new `dict_id`** (`zson--1.1.sql:16-81`). `zson_extract_strings` is a
  recursive plpgsql walker over `jsonb_typeof` that returns keys, string values,
  and array elements (`zson--1.1.sql:83-108`). Training is therefore pure SQL;
  only the hot encode/decode path is C.

## Links into corpus

- `[[knowledge/ideologies/postgresql-hll]]` — sibling "custom base type as a
  thin skin / new representation" extension from the same Citus/Postgres-Pro
  lineage; HLL adds a genuinely new aggregate-able type, zson re-skins an
  existing one.
- `[[knowledge/ideologies/uuidv47]]` and `[[knowledge/ideologies/index_advisor]]`
  — the "I/O / behavior secretly depends on out-of-band state while claiming
  purity" pattern (GUC for uuidv47, catalog+cache+clock for zson).
- `[[knowledge/idioms/catalog-conventions]]` — `pg_extension_config_dump` for
  dumping extension-owned table *data* is the one place zson follows the core
  convention exactly.
- `[[knowledge/idioms/memory-contexts]]` — the contrast: zson's malloc'd,
  TTL-evicted, MemoryContext-free per-backend cache.
- `[[knowledge/idioms/spi]]` — `SPI_prepare` + `SPI_keepplan` pinned plans, and
  the `public.`-hardcoded query that limits the install schema.
- `[[knowledge/idioms/fmgr]]` — `DirectFunctionCall1` delegation to core
  `jsonb_in`/`jsonb_out` and the `IMMUTABLE` labeling question.
- `[[knowledge/scenarios/add-new-data-type]]` — the `CREATE TYPE` + I/O + CAST
  scaffold zson instantiates.

## Sources

Fetched 2026-06-18 via `raw.githubusercontent.com/postgrespro/zson/master`:

- `README.md` @ 2026-06-18 → 200
- `zson.c` @ 2026-06-18 → 200
- `zson.control` @ 2026-06-18 → 200
- `zson--1.1.sql` @ 2026-06-18 → 200
- `sql/zson.sql` @ 2026-06-18 → 200 (regression-test fixture; skimmed, not cited)

No manifest gaps. `zson--1.0--1.1.sql` (upgrade script) and `docs/benchmark.md`
were not fetched; the 1.1 install script is self-contained for the type/catalog
story above.
