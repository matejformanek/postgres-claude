# uuid.c — UUID type I/O and v4/v7 generation

## Purpose

`uuid` SQL type. Holds the 16-byte `pg_uuid_t`, text↔binary I/O, comparison, hashing, abbreviated sort-key support, plus `gen_random_uuid()` (v4) and `uuidv7()` (since PG18) per RFC 9562.

Source: `source/src/backend/utils/adt/uuid.c` (779 lines).

## Key functions

- `uuid_in` (77) / `uuid_out` (88) — accepts hex with optional `{}` braces and optional dashes; emits canonical 8-4-4-4-12 lower-case hex. [verified-by-code]
- `string_to_uuid` (130) — strict parser using `strtoul` on 2-char nybble pairs; rejects malformed input via `ereturn` (soft-error). [verified-by-code]
- `uuid_recv` (180) / `uuid_send` (191) — raw 16 bytes. [verified-by-code]
- `uuid_internal_cmp` (203) — `memcmp` of 16 bytes — defines the SQL ordering. NOT byte-stream-equal to time-ordering for v1/v7 in the way users might expect. [verified-by-code]
- `uuid_lt`/`_le`/`_eq`/`_ne`/`_ge`/`_gt` (lines 209-280). [verified-by-code]
- `uuid_cmp` / `uuid_hash` / `uuid_hash_extended` (around 440-500). [verified-by-code]
- `uuid_sortsupport`, `uuid_fast_cmp`, `uuid_abbrev_abort`, `uuid_abbrev_convert` — abbreviated-key sort acceleration. [verified-by-code]
- `uuid_set_version` (507) — inline; sets the v field (top 4 bits of byte 6) and the variant field (top 2 bits of byte 8). [verified-by-code]
- `gen_random_uuid` (524) — v4. Calls `pg_strong_random(uuid, UUID_LEN)`; errors on RNG failure; then sets version=4, variant. [verified-by-code:528]
- `generate_uuidv7` (601) and `uuidv7` SQL functions (later in file) — v7 with monotonic-within-backend timestamps. The 74 random bits also come from `pg_strong_random`. [verified-by-code:625]
- `get_real_time_ns_ascending` (548) — uses `clock_gettime(CLOCK_REALTIME)` and enforces monotonic step `SUBMS_MINIMAL_STEP_NS` per backend. [verified-by-code]

## Phase D notes

- **`gen_random_uuid()` uses `pg_strong_random`** — the CSPRNG path (OpenSSL `RAND_bytes` or `/dev/urandom`), NOT `pg_prng_*` (the deterministic PRNG used for things like `random()`). This is the right choice for security tokens and matches RFC 9562 §6.9 advice. [verified-by-code uuid.c:528]
- **v4 fills version/variant correctly**: only 122 bits are random; the remaining 6 are constants per the spec. [verified-by-code:537]
- **v7 monotonic guarantee** is **per-backend only**. Different backends (or after a backend restart) can re-emit timestamps in any order. Documented in the comment block. [verified-by-code:577-580]
- **No RFC compliance for v1/v3/v5** — only v4 and v7 are generatable in core. v1/v3/v5 must come from extensions or external producers.

## Potential issues

- `[ISSUE-correctness: v7 monotonicity is per-backend; in a connection-pooled app, sequential v7 calls from different sessions can be out of timestamp order. Documented but a real footgun for "v7 sorts chronologically" assumptions (low; documented)]`.
- `[ISSUE-undocumented-invariant: get_real_time_ns_ascending uses a static int64 previous_ns — process-local. A clock skew (NTP step) can stall UUID generation if it bumps the timestamp back by more than SUBMS_MINIMAL_STEP_NS. The clamp at line 577 makes this safe but observable as suddenly-stale timestamps (low)]`.
- `[ISSUE-secret-scrub: uuid_in uses strtoul on a 3-byte stack buffer; no need to scrub (low)]`.
- `[ISSUE-crypto-weakness: gen_random_uuid is correctly CSPRNG-backed; no concern. (n/a)]`.

Confidence: `[verified-by-code]`.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
