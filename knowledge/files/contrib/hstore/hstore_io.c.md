# hstore_io.c

## One-line summary

Text and binary I/O for hstore plus the family of conversion functions
(hstore↔text, hstore↔array, hstore↔record, hstore→json, hstore→jsonb in
strict + "loose" variants); includes the hand-rolled state-machine
hstore text parser, the `hstoreUniquePairs` dedup pass, and the public
`hstorePairs` constructor.

Source pin: `4b0bf0788b0`.

## Public API / entry points

### SQL-registered functions

- `hstore_in(cstring) -> hstore` — text input
  (`hstore_io.c:478-499`) [verified-by-code]. Soft-error capable via
  `fcinfo->context = escontext`.
- `hstore_recv(internal) -> hstore` — binary input over the wire
  (`hstore_io.c:502-562`) [verified-by-code].
- `hstore_from_text(text, text) -> hstore` — build 1-pair hstore
  (`hstore_io.c:565-598`) [verified-by-code].
- `hstore_from_arrays(text[], text[]) -> hstore` — paired keys+values
  arrays (`hstore_io.c:601-714`) [verified-by-code].
- `hstore_from_array(text[]) -> hstore` — 1-D or 2-D array
  (`hstore_io.c:717-808`) [verified-by-code].
- `hstore_from_record(anyrecord) -> hstore` — composite type → hstore
  (`hstore_io.c:833-989`) [verified-by-code].
- `hstore_populate_record(anyrecord, hstore) -> anyrecord` — reverse of
  above; handles domain-over-composite (`hstore_io.c:992-1207`)
  [verified-by-code].
- `hstore_out(hstore) -> cstring` — text output
  (`hstore_io.c:1224-1292`) [verified-by-code].
- `hstore_send(hstore) -> bytea` — binary output
  (`hstore_io.c:1295-1330`) [verified-by-code].
- `hstore_to_json(hstore) -> text` — strict JSON conversion
  (`hstore_io.c:1393-1432`) [verified-by-code].
- `hstore_to_json_loose(hstore) -> text` — heuristic
  number/bool conversion (`hstore_io.c:1341-1391`) [verified-by-code].
- `hstore_to_jsonb(hstore) -> jsonb` (`hstore_io.c:1434-1474`)
  [verified-by-code].
- `hstore_to_jsonb_loose(hstore) -> jsonb` — heuristic
  number/bool conversion using jsonb-native types
  (`hstore_io.c:1476-1549`) [verified-by-code].

### C-level helpers

- `hstoreCheckKeyLen(size_t) -> size_t` and `hstoreCheckValLen` — ereport
  if length > `HSTORE_MAX_*_LEN = 0x3FFFFFFF`
  (`hstore_io.c:407-415, 427-435`) [verified-by-code].
- `hstoreUniquePairs(Pairs*, l, *buflen) -> int` — qsort + dedup, returns
  new length and total byte cost (`hstore_io.c:358-405`)
  [verified-by-code].
- `hstorePairs(Pairs*, pcount, buflen) -> HStore*` — allocates and
  encodes (`hstore_io.c:448-475`) [verified-by-code].

## Key invariants

- All input paths funnel through `hstoreUniquePairs` → `hstorePairs`,
  which produces a value with `HS_FLAG_NEWVERSION` set and the keys
  sorted+unique by (keylen ASC, key ASC).
- The text format uses `"key"=>"value", "k2"=>NULL, ...` with `\` as
  escape and `NULL` (case-insensitive, unquoted) as the null sentinel
  (`hstore_io.c:282-305`) [verified-by-code].
- The binary format is `int32 count | (int32 keylen | keybytes |
  int32 vallen-or-(-1-for-null) | valbytes?){count}`
  (`hstore_io.c:502-562, 1295-1330`) [verified-by-code]. `vallen = -1`
  means SQL NULL; `keylen = -1` is rejected.
- Both `hstore_in` and `hstore_recv` are gated by `hstoreCheckKeyLen` /
  `hstoreCheckValLen` (1 GiB caps) PLUS the `pcount > MaxAllocSize /
  sizeof(Pairs)` (= ~26 M Pairs) check (`hstore_io.c:521-525`).
- The parser is bytewise (not multibyte-aware in the dispatch) — but
  uses `scanner_isspace` from `parser/scansup.h` to handle whitespace;
  the body bytes inside a value are taken raw without encoding
  validation.

## Notable internals

### `hstore_in` parser state machine

Top-level: `parse_hstore` (`hstore_io.c:217-326`) [verified-by-code]
runs a state machine over `WKEY, WEQ, WGT, WVAL, WDEL`. Each WKEY/WVAL
state calls `get_val` (`hstore_io.c:95-208`) which has its own inner
state machine: `GV_WAITVAL, GV_INVAL, GV_INESCVAL, GV_WAITESCIN,
GV_WAITESCESCIN`. Values come quoted (`"foo"`) or bare (read until
delimiter); backslash escapes any next char including itself and the
quote. **Embedded NUL bytes are forbidden in text input** because `\0`
terminates the input cstring — the parser only checks for `'\0'` and
treats it as EOF, never as a key/value byte.

The "NULL" keyword detection (`hstore_io.c:296-301`) [verified-by-code]:
ONLY recognized for VALUES (not keys), ONLY when the lexeme was UNQUOTED
(`!escaped`), ONLY when the lexeme has exactly 4 bytes that match
`null` case-insensitive. A null KEY would be a syntax error.

Buffer growth: `RESIZEPRSBUF` (`hstore_io.c:51-60`) doubles the local
parse buffer; starts at 32 bytes. There's no hard upper limit on the
re-allocation — the limit comes from `hstoreCheckKeyLength` /
`hstoreCheckValLength` called *after* the parse completes
(`hstore_io.c:244, 290`). So an input of 100 MB of bare characters can
expand the parse buffer through ~22 doubling rounds (~2 GB) before the
length check rejects. With `MaxAllocSize = 1 GiB` the `repalloc` itself
will reject at ~512 MB. `[ISSUE-memory: hstore_in parses arbitrarily-
long values into a doubling buffer before length-checking; OK in
practice because MaxAllocSize fires first, but it's a "fail later than
necessary" pattern (nit)]`.

Soft-error path: both `prssyntaxerror` and `prseof` use `errsave` (not
`ereport`) — so if a caller (e.g. a `COPY ... ON_ERROR` or domain-check
context) provided an `escontext`, syntax errors are reported softly and
the function returns NULL via `PG_RETURN_NULL()`
(`hstore_io.c:64-86, 491-492`) [verified-by-code].

### `hstoreUniquePairs` dedup (PROMPT-SPECIFIC)

`hstore_io.c:358-405` [verified-by-code]. qsort by `comparePairs`
(`hstore_io.c:328-350`): primary key (keylen, memcmp); secondary key
`needfree` so the to-be-pfree'd duplicate appears LATER in the sorted
order. The dedup loop then walks the array and `pfree`s the duplicate's
key/val if `needfree` (`hstore_io.c:380-401`). The kept entry is the
EARLIER one in sort order — and since needfree-true sorts later, the
kept one is whichever ISN'T marked needfree. (If both are needfree,
ties broken by qsort stability.)

Important semantic: **the LAST instance of a duplicate key in input
order is NOT necessarily kept** — it's the first one in
(keylen, memcmp, needfree) order. For most callers (hstore_in,
hstore_from_arrays) all pairs have the same needfree, so dedup keeps
whichever qsort happened to put first. For `hstore_from_record` etc.
this can matter, but those have no duplicate keys by construction
(column names are unique).

### `hstore_recv` binary input (PROMPT-SPECIFIC — Phase D!)

`hstore_io.c:502-562` [verified-by-code].

1. Read `pcount = pq_getmsgint(buf, 4)` — signed int32.
2. If `pcount == 0`, return empty hstore.
3. **Bound check**: `pcount < 0 || pcount > MaxAllocSize / sizeof(Pairs)`
   → ereport `ERRCODE_PROGRAM_LIMIT_EXCEEDED`. `sizeof(Pairs) = 40` on
   64-bit, so the cap is roughly `MaxAllocSize / 40 ≈ 26.8M pairs`.
4. `pairs = palloc(pcount * sizeof(Pairs))` — `26M * 40 = ~1GB`, within
   `MaxAllocSize`.
5. For each pair: `rawlen = pq_getmsgint(buf, 4)` (signed), `rawlen < 0`
   on keys is an error (`ERRCODE_NULL_VALUE_NOT_ALLOWED`); on values it
   means SQL NULL.
6. `pq_getmsgtext(buf, rawlen, &len)` validates that `rawlen` bytes are
   available in the message AND encoding-converts the bytes (`pq_getmsgtext`
   uses `pg_any_to_server`). It returns `len` after possible encoding
   conversion. **`pq_getmsgtext` itself bounds `rawlen ≤ available
   message bytes`**, so a forged `rawlen` claiming 1 GB on a 100-byte
   message is rejected with `insufficient data left in message`.
7. `hstoreCheckKeyLen(len)` then enforces `HSTORE_MAX_KEY_LEN`.

**Bound-check analysis vs A7 record_recv / tsvectorrecv pattern:**

- Per-element length: BOUNDED by `pq_getmsgtext` (message-relative) AND
  by `hstoreCheckKeyLen`/`hstoreCheckValLen` (absolute) — GOOD.
- Count: BOUNDED by `pcount > MaxAllocSize / sizeof(Pairs)` =
  ~26.8M pairs — meaning a single hstore_recv invocation can claim up
  to ~26M pairs and force ~26M iterations + 26M palloc()s of small
  buffers from `pq_getmsgtext`. Each iteration is O(1) work + a small
  alloc, so the absolute upper bound is ~tens-of-seconds of CPU on
  modern hardware per single recv. That's a DoS amplifier compared to
  raw bytes-on-the-wire: the attacker sends `<int32:26M> <26M *
  (int32:1, byte:'k', int32:-1)>` = roughly 9 bytes per pair = 240 MB
  of wire data to spin up tens of seconds of server work. Not great,
  but proportional. `[ISSUE-defense-in-depth: hstore_recv pcount is
  bounded by MaxAllocSize/sizeof(Pairs) ≈ 26M; combined with
  message-bounded per-pair sizes the worst case is ~tens of seconds per
  recv, proportional to wire bytes but with palloc/pfree amplification
  (nit/maybe)]`.
- Also: even after a forged binary hstore is accepted by `hstore_recv`,
  it has to survive a final `hstoreUniquePairs` qsort. qsort with 26M
  elements is `O(n log n)` ≈ 25 \* 26M ≈ 650M comparisons, several
  seconds.
- No recursion in `hstore_recv` itself.

### `hstore_send` output

`hstore_io.c:1295-1330` [verified-by-code]. Simple: `pq_sendint32(count)`,
then for each pair `pq_sendint32(keylen) + pq_sendtext(key, keylen)`,
followed by either `pq_sendint32(-1)` (null value) or
`pq_sendint32(vallen) + pq_sendtext(val, vallen)`. **`pq_sendtext`**
applies encoding conversion from server encoding to client encoding —
note this means the on-wire `keylen` is the POST-conversion length, not
the stored byte length. `hstore_recv` correctly uses the post-conversion
`len`, so round-trip is symmetric.

### `hstore_to_jsonb` / `hstore_to_jsonb_loose` (PROMPT-SPECIFIC stack
depth)

Per task prompt: stack depth in nested-JSON conversion; recursion checks?

Looking at `hstore_to_jsonb` (`hstore_io.c:1434-1474`): it's a
SINGLE-LEVEL conversion — hstore is flat (no nested values), so the
output is one `WJB_BEGIN_OBJECT` ... `WJB_END_OBJECT` pair with `count`
key/value pushes. **No recursion** in this file [verified-by-code]. The
"recursion" concern only arises if you do
`jsonb_build_object('foo', hstore_to_jsonb(hs))` and chain — but that's
jsonb's recursion concern (A7), not hstore's.

`hstore_to_jsonb_loose` calls `DirectFunctionCall3(numeric_in, ...)`
(`hstore_io.c:1530-1533`) for value-looks-like-number — that's an SPI-
ish recursion into PG's numeric input. `numeric_in` is itself O(string
length), bounded by hstore value length. Not a stack-blow concern.

The JSON conversion functions (`hstore_to_json`, `hstore_to_json_loose`)
use `escape_json_with_len` which is a known-safe byte-by-byte escaper.
`IsValidJsonNumber` is a pure validator. **No recursion** anywhere in
hstore_io.c [verified-by-code].

Conclusion on the "stack depth" task prompt: **N/A for hstore** because
hstore values are scalars (text or null), no nesting. The Phase D
recursion concern that applied to jsonb_recv doesn't transfer.

### Loose-mode JSON conversion (`hstore_io.c:1341-1391`)

Heuristic: if the value bytes are exactly `'t'` or `'f'` → boolean; if
`IsValidJsonNumber` → unquoted number in JSON output; else quoted
string. Comment notes (`hstore_io.c:1336-1340`): "as long as they don't
start with a leading zero followed by another digit (think zip codes or
phone numbers starting with 0)". `IsValidJsonNumber` enforces JSON's
number grammar including the no-leading-zero rule, so a key like
"phone" with value "0123456" stays as a string. Good.

`[ISSUE-correctness: the 't'/'f' boolean heuristic in loose-mode JSON is
lossy — a legitimate string value of exactly "t" becomes JSON true. The
function name "loose" advertises this, but a SQL injection or trust-
boundary issue could arise if an application uses
`hstore_to_jsonb_loose` to serialize user input and a downstream
consumer expects strings throughout (maybe, by design)]`.

### `hstore_from_record` / `hstore_populate_record`

Hard to abuse: both validate that the input is a composite type,
honor dropped columns (`attisdropped`), use `lookup_rowtype_tupdesc_domain`
to handle domain-over-composite, and rely on `hstoreFindKey`'s binary
search for column-name lookup. `hstore_populate_record` re-applies
`InputFunctionCall` to each text value with the column's input function
(`hstore_io.c:1158-1186`), so a domain-constrained column gets domain
checks. `[verified-by-code]`.

Caveat: the `fn_extra` caching (`hstore_io.c:887-909`) is per-FmgrInfo,
so a long-running session that hits many record types will keep N
ColumnIOData entries in `fn_mcxt` — bounded by call sites.

### `hstore_from_arrays` / `hstore_from_array` overflow guards

Both check `key_count > MaxAllocSize / sizeof(Pairs)` BEFORE the palloc
(`hstore_io.c:638-642, 765-769`) [verified-by-code]. Matches the
`hstore_recv` guard. Good.

### `hstore_out` buffer estimation

`hstore_io.c:1240-1260`: `buflen` accumulates `6 + 2*keylen + 2 +
{2 or 2*vallen}` per pair (the 2x accounts for the worst-case escape of
every char). For a 1 GiB hstore value this would request 2 GiB —
caught by palloc's MaxAllocSize. The comment acknowledges:
"this loop overestimates due to pessimistic assumptions about escaping,
so very large hstore values can't be output. this could be fixed, but
many other data types probably have the same issue."
(`hstore_io.c:1243-1247`) [from-comment]. `[ISSUE-correctness: hstore_out
of a near-1GB hstore palloc-fails by 2x overshoot; documented in code
comment but means hstore_send can roundtrip a value that hstore_out
cannot stringify (maybe)]`.

## Trust boundary / Phase D surface

### `hstore_recv` binary input — primary attacker surface

See "Notable internals — hstore_recv" above. Summary: well-defended
against unbounded count and unbounded per-element size, BUT the
`MaxAllocSize / sizeof(Pairs)` cap (~26M) is a soft cap on amplification,
not a tight one. A single message can force ~26M iterations + qsort.

`[ISSUE-defense-in-depth: hstore_recv allows up to ~26M pairs per
single recv message; qsort dominates work at O(n log n) — proportional
to wire bytes but with multiple per-pair allocs amplifying memory
pressure (maybe)]`.

### Embedded NULs

`hstore_recv` accepts arbitrary bytes via `pq_getmsgtext` → the resulting
keys and values CAN contain embedded NULs. Downstream usage that does
`cstring_to_text_with_len` is fine (text is length-prefixed), but if
an application calls `hstore_out` on such a value, the NULs are emitted
as raw bytes inside `"..."` quoting — receiver-side string handling may
truncate. `hstore_in` cannot produce embedded NULs (it terminates on
`'\0'`). `[ISSUE-correctness: hstore_recv accepts embedded NUL bytes in
keys/values; hstore_out emits them as-is, creating asymmetric I/O where
text format cannot round-trip a binary-format hstore (maybe)]`.

### Encoding validation

`pq_getmsgtext` performs `pg_any_to_server` encoding conversion — so
on-wire bytes are converted to server encoding and validated. Good.

### `hstore_from_record` domain checks

`hstore_populate_record` runs `domain_check` for domain-over-composite
(`hstore_io.c:1198-1202`) [verified-by-code]. Good.

### "loose" mode lossy conversion

`hstore_to_json_loose` and `hstore_to_jsonb_loose` apply
type-coercion heuristics that are semantically lossy and may surprise
audits. Documented above as `[ISSUE-correctness]`.

## Cross-references

- `lib/stringinfo.h`, `libpq/pqformat.h` — `pq_getmsg*` / `pq_send*` API.
- `nodes/miscnodes.h` — soft-error `escontext` Node.
- `parser/scansup.h` — `scanner_isspace`.
- `utils/json.h`, `utils/jsonb.h` — `escape_json_with_len`,
  `pushJsonbValue`, `IsValidJsonNumber`, `JsonbValueToJsonb`.
- A7 jsonb_recv DoS findings — same shape (decoder-side count bound).
- A7 record_recv DoS findings — same shape.
- `hstore.h.md` — Pairs struct, length caps.
- `hstore_compat.c.md` — the OTHER input path (legacy-format upgrade on
  `DatumGetHStoreP`).

<!-- issues:auto:begin -->
- [Issue register — `hstore`](../../../issues/hstore.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-memory: hstore_in's get_val grows a parse buffer by doubling
  before length-checking; defers rejection until MaxAllocSize fires
  (~512 MB) instead of HSTORE_MAX_KEY_LEN (1 GiB minus header) up front
  (nit)]`
- `[ISSUE-defense-in-depth: hstore_recv pcount bound (~26M pairs) is
  loose; combined with subsequent qsort can spin ~seconds per recv
  message (maybe)]`
- `[ISSUE-correctness: hstore_recv accepts embedded NULs in keys/values;
  hstore_out emits as-is, creating asymmetric I/O — hstore_recv ⤳
  hstore_send roundtrips, hstore_recv ⤳ hstore_out does not (maybe)]`
- `[ISSUE-correctness: hstore_out palloc 2x-overshoots for escape; very
  large hstores fail to stringify even though they're valid values
  (documented in source comment) (maybe)]`
- `[ISSUE-correctness: 't'/'f' boolean heuristic in loose-mode JSON
  conversion is lossy by design (e.g. a value of "t" becomes JSON true);
  acknowledged via the "loose" naming but worth audit-flagging (nit,
  by design)]`
- `[ISSUE-api-shape: hstore_in's "NULL" keyword recognition is
  case-insensitive ASCII (pg_strcasecmp) — fine for SQL, but a locale-
  weird input like Turkish "ı" would not confuse it; documented for
  completeness (nit)]`
- `[ISSUE-documentation: comment at hstore_io.c:1243-1247 admits
  hstore_out 2x-overshoot is a known issue ("could be fixed, but many
  other data types probably have the same issue") — that's still true
  but the TODO has aged poorly (nit)]`
- `[ISSUE-error-handling: hstore_in's get_val deduplicates the EOF
  detection vs PRSEOF macros across multiple states; a refactor missed
  this duplication. Functional, but harder to audit (nit)]`
- `[ISSUE-audit-gap: hstoreUniquePairs picks the FIRST duplicate (per
  qsort order) when input has duplicate keys, not the LAST; for
  hstore_in this means `'a=>1, a=>2'::hstore` could keep either '1' or
  '2' depending on the qsort stable-ish tiebreak. SQL behavior is
  defined-but-surprising (nit)]`
- `[ISSUE-defense-in-depth: hstore_populate_record uses
  `lookup_rowtype_tupdesc_domain(tupType, tupTypmod, false)` — the false
  means "throw error if not found", good; but a forged anonymous record
  with a stale typmod could trigger a confusing error. Minor (nit)]`
- `[ISSUE-correctness: hstore_to_jsonb passes the hstore key/value
  bytes BY POINTER (jbvString.val.string.val = HSTORE_VAL(...)) into
  pushJsonbValue; the jsonb subsystem copies during JsonbValueToJsonb so
  the temporary hstore can be freed safely. Confirmed by looking at
  pushJsonbValue's contract (verified)]`
- `[ISSUE-audit-gap: hstore_recv calls hstoreUniquePairs AFTER reading
  all pairs from the wire — a forged recv with 26M duplicate keys would
  ALL be read+palloc'd before dedup runs. Memory peak is 26M Pairs +
  26M tiny strings, not the final hstore size (maybe)]`
