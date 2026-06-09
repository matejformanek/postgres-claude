# ltree_io.c

## One-line summary

I/O for `ltree` and `lquery`: hand-rolled recursive-descent parsers (no flex/bison) implemented as character-by-character state machines (`parse_ltree`, `parse_lquery`), plus `_in` / `_out` / `_send` / `_recv` SQL entry points. The `_recv` functions are not binary parsers — they wrap a 1-byte version tag around the text input and feed it through the same text parser, sidestepping all binary-layout DoS concerns.

## Public API / entry points

- `Datum ltree_in(PG_FUNCTION_ARGS)` (line 173, `PG_FUNCTION_INFO_V1`) — text → `ltree`, soft-error capable.
- `Datum ltree_out(PG_FUNCTION_ARGS)` (line 186) — `ltree` → text.
- `Datum ltree_send(PG_FUNCTION_ARGS)` (line 203) — wire format: `int8 version=1 + pq_sendtext(text)`.
- `Datum ltree_recv(PG_FUNCTION_ARGS)` (line 228) — wire format: reads `int8 version`, then `pq_getmsgtext`, then `parse_ltree` on the decoded string.
- `Datum lquery_in(PG_FUNCTION_ARGS)` (line 757) — text → `lquery`.
- `Datum lquery_out(PG_FUNCTION_ARGS)` (line 770) — `lquery` → text via `deparse_lquery`.
- `Datum lquery_send(PG_FUNCTION_ARGS)` (line 787) — same wire shape as `ltree_send`.
- `Datum lquery_recv(PG_FUNCTION_ARGS)` (line 812) — same wire shape.

Internal:

- `static ltree *parse_ltree(const char *buf, struct Node *escontext)` (line 36) — two-pass: count dots → palloc nodeitem array → state-machine scan filling labels → palloc result → copy.
- `static char *deparse_ltree(const ltree *in)` (line 144) — simple level walk with `.` separators.
- `static lquery *parse_lquery(const char *buf, struct Node *escontext)` (line 268) — 9-state machine (`LQPRS_WAITLEVEL` ... `LQPRS_WAITVAR`).
- `static bool finish_nodeitem(...)` (line 599) — back up over flag chars and validate label length.
- `static char *deparse_lquery(const lquery *in)` (line 641).

## Key invariants

- INV-LTREE-LABEL-COUNT: `parse_ltree` rejects more than `LTREE_MAX_LEVELS = 65535` labels at line 64 (counts dots, checks `num+1`). `[verified-by-code]`
- INV-LQUERY-LEVEL-COUNT: `parse_lquery` rejects more than `LQUERY_MAX_LEVELS = 65535` levels at line 306. `[verified-by-code]`
- INV-LQUERY-VARIANT-COUNT-PER-LEVEL: `parse_lquery` uses `pg_add_u16_overflow` to bump `numvar` per `|` alternative (line 348), erroring out at `PG_UINT16_MAX`. `[verified-by-code]`
- INV-LQUERY-LEVEL-TOTALLEN: each level's serialized size must fit `uint16`; checked at line 553 with explicit message. `[verified-by-code]`
- INV-LABEL-WLEN-1000: per-label character count cap enforced in `finish_nodeitem` (lines 628-633). Byte length is recomputed `ptr - lptr->start` at line 618. `[verified-by-code]`
- INV-LABEL-NONEMPTY: empty labels rejected at line 621 in `finish_nodeitem`. `[verified-by-code]`
- INV-LQUERY-LOW-LE-HIGH: parser rejects `{N,M}` with N > M (line 448). `[verified-by-code]`
- INV-LQUERY-COUNT-RANGE: low and high bounded by `LTREE_MAX_LEVELS` (lines 424, 442). `[verified-by-code]`
- INV-RECV-VERSION-1-ONLY: both `ltree_recv` (line 238) and `lquery_recv` (line 822) hard-error `unsupported ... version number` on anything ≠ 1. Forward-compat hook present but no other version exists. `[verified-by-code]`
- INV-SOFT-ERROR-IN-TEXT-PATH-ONLY: `ltree_in` / `lquery_in` propagate `fcinfo->context` so soft errors (e.g. `COPY ... ON_ERROR ignore`) get back to the caller. `_recv` passes `NULL` for `escontext` (lines 242, 826), so recv errors are always hard `ereport(ERROR)` — consistent with the no-soft-errors-from-binary-protocol convention. `[verified-by-code]`

## Notable internals

- `parse_ltree` is single-state (`LTPRS_WAITNAME`/`LTPRS_WAITDELIM`) — minimal. The label-character predicate `ISLABEL(ptr)` is the only place where multibyte / locale-aware classification happens; the state machine advances by `pg_mblen_cstr(ptr)` (lines 58, 73, 103) so each iteration consumes one **codepoint**, not one byte.
- `parse_lquery` is a 9-state machine. Notable: levels are first allocated into a scratch `lquery_level` array (one per dot-separated segment), with the variant list hung off via the `GETVAR(curqlevel) = palloc0_array(nodeitem, numOR + 1)` trick at lines 322 and 329 — `numOR + 1` is the total `|` count in the WHOLE query, so each level over-allocates its variant scratch space. Wasteful but bounded by `PG_UINT16_MAX × ITEMSIZE`.
- The two-pass design (count dots first, then parse) means the parser walks the input string twice. Both passes are O(input bytes); no recursion in either parser.
- `finish_nodeitem` (line 599) is where flag suffixes (`@*%`) get peeled back off the byte range so `lptr->len` reflects just the label text. The flag chars are NOT counted toward `LTREE_LABEL_MAX_CHARS`.
- `firstgood` (line 535) is a small optimization counter: the parser records how many leading `lquery` levels are simple-match (`numvar == 1, flag == 0`), used by `gist_tqcmp` (`ltree_gist.c:517`) to bound the GiST index range when searching with a partially-anchored query.
- `deparse_lquery` (line 641) is the inverse — pre-computes a generous upper bound (`2 * 11 + 4` per count-range, etc.) at lines 654-666 then `sprintf`s into it. Buffer accounting is hand-tuned; the comments don't justify the magic constants but they appear correct (max integer printed: 11 chars `-2147483648` though here `low/high` are `uint16` so ≤6).

## Trust boundary / Phase D surface

- **`ltree_recv` / `lquery_recv` / `ltxtquery_recv` binary input is text-on-the-wire**: each reads one byte for version, then `pq_getmsgtext(buf, buf->len - buf->cursor, &nbytes)` — i.e. the rest of the message is treated as encoded text and decoded to server encoding by libpq, then handed to the SAME parser as `_in`. **There is no separate binary-format parser to attack.** All input bounds checking (`LTREE_MAX_LEVELS`, `LTREE_LABEL_MAX_CHARS`, `numvar` cap, level-totallen-u16) still applies. `[verified-by-code]`
- **`pq_getmsgtext` decodes from client encoding**: a hostile client can send malformed UTF-8 or a different encoding declaration, but server-side encoding validation rejects malformed sequences before reaching `parse_ltree`. The parser's `pg_mblen_cstr` (line 58 etc.) trusts the encoding to be well-formed; failure to validate would cause read-past-end on a 0xC0 0x00 sequence. Validation happens earlier in `pq_getmsgtext` → `pg_verify_mbstr`. `[inferred from libpq convention]`
- **No recursion in either parser**: `parse_ltree` and `parse_lquery` are iterative state machines. **No `check_stack_depth()` is needed or present.** This is a strength compared to the ltxtquery parser (`ltxtquery_io.c:214`) which IS recursive. Cross-link: A5 jsonapi finding — the recursive-descent json parser has a 6400-byte stack cap; ltxtquery uses `check_stack_depth()`; ltree/lquery dodge the issue entirely by being iterative.
- **CPU bounds on parser**: both parsers are O(input characters) with no quadratic behavior. The maximum legitimate input is `LTREE_MAX_LEVELS × LTREE_LABEL_MAX_CHARS = 65535 × 1000 = ~65 MB` of UTF-8 character data plus separators — a single call could allocate that much working memory (the `nodeitem` array at line 69 is `num+1` pointers, ~512 KB for 65535 levels).
- **`palloc_array(nodeitem, num + 1)` at line 69**: a maliciously crafted text with 65535 dots will palloc ~3 MB of nodeitem scratch before any label is parsed. The check at line 64 already gates `num+1 > LTREE_MAX_LEVELS`, so 3 MB is the per-call worst-case. Bounded.
- **`palloc0(ITEMSIZE * num)` at line 311**: each level slot is `ITEMSIZE = MAXALIGN(LQL_HDRSIZE+sizeof(nodeitem*))` ~24 bytes; 65535 levels → ~1.5 MB scratch. Plus the variant-array hanging off each level at `palloc0_array(nodeitem, numOR + 1)` (line 322) where `numOR` is the TOTAL `|` count across the whole query. **A query of 65535 levels each containing 65535 `|`-separated variants would have `numOR = 65535²` — but the parser uses `pg_add_u16_overflow` on per-level `numvar` (line 348), so each level is capped at 65535 OR'd variants, AND the global `numOR` is also bounded by total input length.** A 65535 × 65535 attack would need ~4 GB of `|`-separated input. Practically unreachable, but the `numOR + 1` over-allocation per level means `parse_lquery` is `O(num_levels × numOR)` in scratch memory. (Note: each per-level palloc is bounded by `numOR + 1` total `|` count.) **For a worst-case input of ~256 KB containing ~65000 levels and ~65000 `|`s, scratch allocation is ~65000 × 65000 × sizeof(nodeitem) ≈ 100 GB. This is a memory amplification of ~400000×.** See ISSUE below.
- **Binary protocol version compatibility**: version 1 is the only version; future bumps would land here. The byte at offset 0 of the recv message is `int8` — values 0, 2-255 all error.
- **No byteorder concerns**: text-on-wire format means no endian issues. The varlena `int32 vl_len_` is set on the server side using `SET_VARSIZE` in network order via `pq_endtypsend` for `_send`; for `_recv` the result is a freshly-built local varlena. `[inferred]`
- **`palloc0` failure path**: like all PG palloc, OOM throws `ereport(ERROR)` via the memory-context allocator. The 65535×65535 attack would OOM before exhausting backend memory; effectively a CPU/memory DoS that the backend recovers from on transaction abort.

## Cross-references

- `source/contrib/ltree/ltree.h:33-126` — the varlena layouts this file constructs.
- `source/contrib/ltree/ltxtquery_io.c:368` — the parallel `queryin` for ltxtquery (recursive, contrasts with iterative parsers here).
- `source/src/backend/libpq/pqformat.c` — `pq_begintypsend`, `pq_sendint8`, `pq_sendtext`, `pq_getmsgint`, `pq_getmsgtext`, `pq_endtypsend`.
- `source/src/include/mb/pg_wchar.h` — `pg_mblen_cstr`.
- `source/src/include/common/int.h:113` — `pg_add_u16_overflow`.
- A5 jsonapi finding — incremental parser uses explicit 6400-byte stack frame; the ltree/lquery parsers avoid the issue by being iterative.
- A7 binary-recv DoS surface — ltree/lquery/ltxtquery are insulated because they re-route binary input through the text parser; no separate binary-format ABI to attack.

## Issues spotted

- [ISSUE-cost: at line 322 / 329 `palloc0_array(nodeitem, numOR + 1)` is allocated PER LEVEL, where `numOR` is the global count of `|` characters in the input. **A query with N levels and M total `|`s allocates N × (M+1) × sizeof(nodeitem) of scratch.** With `N=M=65000`, that is `65000 × 65001 × 24 ≈ 100 GB` of scratch on a single `lquery_in` call. The size of the malicious input would be ~256 KB. **Amplification factor ~400000×.** This is the canonical Phase D memory-DoS finding for ltree. Mitigation: each per-level palloc should size to that level's own variant count, not the global count. (likely — should validate via reproduction)] — `source/contrib/ltree/ltree_io.c:322,329`.
- [ISSUE-correctness: line 622-627 — the `is_lquery` flag selects between `lquery syntax error at character %d` and `ltree syntax error at character %d` for an empty label. The errdetail is "Empty labels are not allowed." Two identical-looking errors with the only difference being the message prefix. Minor consistency issue. (nit)] — `source/contrib/ltree/ltree_io.c:622-627`.
- [ISSUE-security: `parse_ltree` and `parse_lquery` both trust `ISLABEL` (encoding-aware) — meaning the SAME ltree value typed under different `lc_ctype` settings may parse differently. A label like `é.bar` parses as one level under `lc_ctype=C` (`é` not alnum → syntax error) but two-character label under `en_US.UTF-8`. **An ltree stored under one locale may become invalid input if re-parsed under another.** Stored varlenas don't need re-parsing (only `_in` / `_recv` do); but logical replication / pg_dump / COPY round-trips do re-parse. (likely — operational footgun)] — `source/contrib/ltree/ltree_io.c:78,87` (uses `ISLABEL` from `ltree.h:130`).
- [ISSUE-cost: `parse_ltree` is two-pass (first count dots, then parse). A 1-GB input string with `t_iseq(ptr, '.')` checks at line 59 is O(N) on the first pass, then errors out at line 64 if `num+1 > LTREE_MAX_LEVELS`. So a 1-GB input with 65536 dots blocks the backend for the duration of one O(N) scan before the error fires — single-digit seconds. Not catastrophic but worth noting. (nit)] — `source/contrib/ltree/ltree_io.c:56-62`.
- [ISSUE-API-shape: `ltree_recv` and `lquery_recv` accept arbitrary-length text after the version byte. There's no explicit cap on the length of the encoded text; the parser later enforces level / label limits, but a 4-GB recv payload would `palloc` the decoded string before the parser even runs. `pq_getmsgtext` decodes the whole tail. (likely — generic to all text-via-binary recv functions)] — `source/contrib/ltree/ltree_io.c:241,825`.
- [ISSUE-correctness: line 422 `int low = atoi(ptr);` — `atoi` on `99999999999` silently overflows int; the parser then checks `low > LTREE_MAX_LEVELS` which catches the bad value, but `atoi` undefined-behavior on overflow per ISO C. In practice on glibc `atoi` saturates to INT_MIN/INT_MAX and the `low < 0` check at line 424 catches it. (nit)] — `source/contrib/ltree/ltree_io.c:422,440`.
- [ISSUE-correctness: line 568 `pfree(GETVAR(curqlevel))` frees the per-level scratch nodeitem array. If `palloc0_array(nodeitem, numOR + 1)` at line 322/329 fails (OOM), `parse_lquery` leaks the previously-allocated `tmpql` and any earlier level-variant arrays. Not a security bug — backend memory context cleanup at transaction abort reclaims it. (nit)] — `source/contrib/ltree/ltree_io.c:568`.
- [ISSUE-doc: line 60-62 — counting `|` characters for global `numOR` doesn't account for `|` appearing inside `{N,M}` ranges. Lucky for the parser, `|` is never valid inside `{}` (line 466-471 only accepts digits/`,`/`}`), so the over-count is exactly the true total. Worth a comment. (nit)] — `source/contrib/ltree/ltree_io.c:299-303`.
