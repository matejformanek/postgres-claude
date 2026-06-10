# uuidv47 — a base type whose on-disk bytes differ from its text form, with GUC-keyed (and fallible) I/O functions

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `stateless-me/uuidv47` @ branch `main`. The PG extension lives under
> `pgext/uuid47/`; the root `uuidv47.h` is a standalone header-only C89 library
> the extension vendors. All `file:line` cites point into that repo (not
> `source/`). Cites verified against the files fetched on 2026-06-10 (see
> Sources footer). Read alongside `[[knowledge/idioms/catalog-conventions]]` and
> the core `uuid`/`pg_uuid_t` type.

## Domain & purpose

uuidv47 "lets you store sortable UUIDv7 in your database while emitting a
UUIDv4-looking façade at your API boundary" (`README.md:4-6`) `[from-README]`.
The core library XOR-masks *only* the 48-bit UUIDv7 timestamp field with a
keyed SipHash-2-4 stream derived from the UUID's own random bits; the mapping is
deterministic and exactly invertible given the 128-bit key
(`README.md:6-8, 120-135`) `[from-README]`. The optional Postgres extension
wraps this as a first-class `uuid47` base type with casts to/from core `uuid`,
B-tree/hash opclasses, and a BRIN minmax-multi distance support function
(`README.md:167-174`) `[from-README]`. The reason to document it: it is the
corpus's sharpest example of a type whose **stored representation deliberately
differs from its presented representation**, and whose input/output functions
depend on — and can fail on — session GUC state, both of which cut against core
type-design invariants.

## How it hooks into PG

A minimal lazy-loaded function extension: bare `PG_MODULE_MAGIC`
(`pgext/uuid47/src/uuid47_pg.c:22`), a tiny `_PG_init` whose *only* job is to
define one GUC, `uuid47.key` (`DefineCustomStringVariable`, `uuid47_pg.c:264-274`)
`[verified-by-code]`. Everything else is `PG_FUNCTION_INFO_V1` C functions wired
up from `sql/uuid47--1.0.sql`:

- **Type I/O**: `uuid47_in`/`uuid47_out`/`uuid47_recv`/`uuid47_send`
  (`uuid47_pg.c:280-378`).
- **Casts** to/from core `uuid`: `uuid47_to_uuid`, `uuid_to_uuid47`, plus
  `_with_key` variants taking an explicit `bytea` key (`:384-488`).
- **Generators**: `uuid47_generate`, `…_monotonic`, `…_at` (`:530-660`).
- **Opclass support**: `uuid47_cmp`/`_eq`/`_lt`/… for B-tree, `uuid47_hash` for
  hash, `uuid47_brin_distance` (BRIN support proc 11) (`:793-914`).
- **Introspection**: `uuid47_timestamp`, `uuid47_as_v7`, `uuid47_explain`
  returning a composite via `get_call_result_type` + `heap_form_tuple`
  (`:666-746`) `[verified-by-code]`.

The C entry point vendors the upstream lib by relative include
`#include "../../uuidv47.h"` (`uuid47_pg.c:20`) `[verified-by-code]` — the same
header used by the standalone library and all its language ports.

Cross-ref `[[knowledge/idioms/fmgr]]`,
`[[knowledge/idioms/catalog-conventions]]`,
`.claude/skills/fmgr-and-spi/SKILL.md`,
`.claude/skills/catalog-conventions/SKILL.md`.

## Where it diverges from core idioms

### 1. On-disk bytes ≠ text/binary representation — the type lies about itself, by design

Core types satisfy `in(out(x)) = x` and, more deeply, `out` renders the stored
datum faithfully. uuid47 stores the **real UUIDv7** 16 bytes on disk, but
`uuid47_out` first calls `uuidv47_encode_v4facade(v7, key)` and renders the
*façade* (`uuid47_pg.c:313-332`) `[verified-by-code]`; `uuid47_in` does the
inverse, decoding a v4-looking input back to v7 before storing
(`:280-311`). So what a client sees (`…-4xxx-…`, version nibble 4) is never what
is on the heap page (`…-7xxx-…`, version 7). The cast `uuid47::uuid` likewise
emits the façade (`uuid47_to_uuid`, `:384-402`). This is a *feature* — index
locality from the sortable v7 while presenting an opaque v4 externally — but it
means the type's textual identity is a keyed transform of its storage, a
property core's type system never assumes.

### 2. Output is **not immutable** and can throw — it depends on `uuid47.key` and errors if unset

The strongest divergence: `uuid47_out` calls `key_from_guc_or_error()`, which
`ereport(ERROR, …)`s if `uuid47.key` is unset or malformed
(`uuid47_pg.c:248-258, 324`) `[verified-by-code]`. Consequences that break core
expectations:

- `SELECT some_uuid47_col` **fails** in any session that hasn't `SET uuid47.key`
  — output of a stored value depends on session GUC state.
- The same stored datum renders to *different text* under different keys, so
  output is not a pure function of the value. Core requires type output
  functions to be `IMMUTABLE` and total; uuid47's is effectively
  `STABLE`-and-fallible.

`uuid47_in`/`uuid47_recv` are conditionally key-dependent too: a v7 literal is
stored as-is, but a v4-looking literal requires the key to decode
(`:288-311, 347-364`) `[verified-by-code]`. Cross-ref
`[[knowledge/idioms/error-handling]]` (an I/O function that raises on session
state), `.claude/skills/error-handling/SKILL.md`.

### 3. It composes on core `uuid` I/O via `DirectFunctionCall1` instead of reparsing

Rather than re-implement UUID text parsing, the in/out functions delegate to
core: `uuid47_in` calls `DirectFunctionCall1(uuid_in, …)` to get a `pg_uuid_t`,
then rewrites the 16 bytes in place; `uuid47_out` builds a temporary `pg_uuid_t`
and calls `uuid_out` (`uuid47_pg.c:285-286, 330`) `[verified-by-code]`. This is
idiomatic fmgr composition — reuse the core type's parser/printer and only
intervene on the bytes — and a clean contrast with extensions that ship their
own scanners. Cross-ref `[[knowledge/idioms/fmgr]]`.

### 4. Index order is by *true* timestamp; the comparison ignores the façade entirely

`uuid47_cmp`/`_lt`/… are plain `memcmp` over the **stored v7 bytes**
(`cmp16`, `uuid47_pg.c:782-868`) `[verified-by-code]`, so a B-tree on a uuid47
column is ordered by the real 48-bit big-endian timestamp prefix — exactly the
locality win the design exists for — even though users never see that ordering
in the rendered values. The hash opclass uses core `hash_bytes` over the same 16
stored bytes (`uuid47_hash`, `:870-879`). The BRIN minmax-multi **distance
support function** (proc 11) interprets the 16 bytes as a 128-bit magnitude and
returns `|a-b|` as a `float8` via `__uint128_t` math (`uuid47_brin_distance`,
`:894-914`) `[verified-by-code]` — a non-obvious extension surface (BRIN
minmax-multi needs a distance proc to merge ranges) that few hand-written types
bother to provide. Cross-ref `.claude/skills/access-method-apis/SKILL.md`,
`.claude/skills/access-method-apis/SKILL.md`.

### 5. The "monotonic" generator's ordering guarantee is per-backend only

`uuid47_generate_monotonic` keeps its counter/high-bits in *file-scope statics*
(`gen_state_last_ms`, `gen_state_ctr`, `gen_state_hi`, `uuid47_pg.c:494-496`)
and packs a 32-bit counter under a 42-bit random high field using `__uint128_t`
bit math (`:613-629`) `[verified-by-code]`. Because the state is backend-local,
monotonicity holds within one session but not across the cluster — the README is
upfront: "Monotonic generator uses per-backend state; ordering is stable within
a session" (`README.md:230`) `[from-README]`. It also clamps a backwards-moving
clock to the last issued ms (`:580-583`). Randomness uses `pg_strong_random`
with a `random()` fallback (`fill_rand`, `:498-509`) `[verified-by-code]`.

## Notable design decisions (cited)

- **`ALIGNMENT = int4`** for the type (matching core `uuid`) "for better tuple
  formation speed" (`README.md:196-198`) `[from-README]` — a deliberate catalog
  choice in the install SQL, not the default.
- **Key can be passed inline** via `_with_key(bytea)` variants
  (`uuid47_to_uuid_with_key`, `uuid_to_uuid47_with_key`, `uuid47_pg.c:437-488`)
  `[verified-by-code]`, bypassing the GUC — so transforms are usable in contexts
  where setting a session GUC is awkward, at the cost of putting key material in
  the query text.
- **`uuid47.key` parsing is tolerant**: accepts `k0:k1` (two 16-hex LE halves) or
  32 contiguous hex, optional `0x`, spaces stripped (`parse_key_from_guc`,
  `:144-220`) `[verified-by-code]`. A non-throwing `uuid47_key_fingerprint`
  (FNV-1a over the key) lets ops confirm which key a session loaded without
  exposing it (`:752-776`).
- **`uuid47_explain`** returns the SipHash 10-byte message, decoded timestamp,
  version, and façade as a composite row (`get_call_result_type` +
  `BlessTupleDesc` + `heap_form_tuple`, `:691-746`) `[verified-by-code]` — a
  debugging SRF-of-one built the manual fmgr way.

## Links into corpus

- core `uuid` / `pg_uuid_t` — uuid47 stores the same 16-byte layout and delegates
  text I/O to `uuid_in`/`uuid_out` via `DirectFunctionCall1`, then transforms the
  bytes.
- `[[knowledge/idioms/fmgr]]` — `PG_FUNCTION_INFO_V1` surface,
  `DirectFunctionCall1` composition, `get_call_result_type`/`heap_form_tuple` SRF.
- `[[knowledge/idioms/error-handling]]` — a type *output* function that raises
  `ERROR` on session GUC state, contra core's immutable-total I/O contract.
- `[[knowledge/idioms/catalog-conventions]]` — custom base type with B-tree/hash
  opclasses and a BRIN minmax-multi distance support proc (support number 11).
- `.claude/skills/access-method-apis/SKILL.md` — opclass/support-function wiring,
  BRIN distance proc.

## Anthropology takeaway

uuidv47 is the doc-set's cleanest **"presentation ≠ storage" type**, and a
pointed stress test of two core invariants. (a) Type output is assumed
`IMMUTABLE` and total; uuid47 makes it depend on a session GUC and throw when
unset — so a plain `SELECT` of a column can error purely from configuration.
That is a concrete cautionary case for a `knowledge/issues` note on *type I/O
purity* and a thing planners/EXPLAIN that assume cheap immutable output may not
expect. (b) The deliberate divergence between *index order* (by stored v7
timestamp, sortable) and *displayed value* (scrambled v4) is the whole point and
a genuinely clever use of opclass freedom — comparison is over storage, not over
the rendered text. For Phase-D / leak-hardening: a type that round-trips through
a keyed PRF, with optional inline-key variants that embed key material in SQL
text, is worth flagging — the key lives in `uuid47.key` (a `PGC_USERSET` GUC,
hence visible in `pg_settings`/logs if set in a logged statement) and in
`_with_key` arguments (visible in `pg_stat_statements`/query text). The
`uuid47_key_fingerprint` helper shows the author was conscious of not exposing
the key directly, which makes the GUC/argument exposure surface the more
interesting contrast.

## Sources

Fetched 2026-06-10 (branch `main`):

- `https://api.github.com/repos/stateless-me/uuidv47/git/trees/main?recursive=1`
  @ 2026-06-10 → HTTP 200 (tree listing; manifest `uuidv47.control`/`uuidv47.c`
  at repo root are 404 — the extension lives under `pgext/uuid47/`:
  `src/uuid47_pg.c`, `uuid47.control`, `sql/uuid47--1.0.sql`, substituted; root
  `uuidv47.h` is the vendored header-only lib).
- `https://raw.githubusercontent.com/stateless-me/uuidv47/main/README.md`
  @ 2026-06-10 → HTTP 200 (9841 bytes; spec + PG section read).
- `.../main/uuidv47.control` @ 2026-06-10 → HTTP 404.
- `.../main/uuidv47.c` @ 2026-06-10 → HTTP 404.
- `.../main/uuidv47.h` @ 2026-06-10 → HTTP 200 (6430 bytes; header-only lib,
  skimmed for the encode/decode API surface).
- `.../main/pgext/uuid47/src/uuid47_pg.c` @ 2026-06-10 → HTTP 200 (23367 bytes;
  deep-read — I/O, casts, generators, opclass support, GUC, BRIN distance).
- `.../main/pgext/uuid47/uuid47.control` @ 2026-06-10 → HTTP 200 (169 bytes).
- `.../main/pgext/uuid47/sql/uuid47--1.0.sql` @ 2026-06-10 → HTTP 200 (6817 bytes;
  read for type/opclass/cast DDL).

All cites are `[verified-by-code]` against the fetched `uuid47_pg.c`/`.control`
except the façade-mapping cryptography, the index-locality motivation, the
`ALIGNMENT = int4` rationale, and the per-session-monotonicity caveat, which are
`[from-README]`. The SipHash internals (`uuidv47.h`) were skimmed, not audited;
claims about *that* the timestamp is XOR-masked with a keyed PRF rest on the
README + the visible `uuidv47_encode/decode_v4facade` call sites.
