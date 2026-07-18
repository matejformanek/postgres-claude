# _intbig_gist.c

`source/contrib/intarray/_intbig_gist.c` (597 lines).

## One-line summary

`gist__intbig_ops` GiST opclass: stores `int4[]` as a fixed-size signature bitmap (default 2016 bits = 252 bytes), with an `ALLISTRUE` short-circuit flag for fully-set signatures. Lossy → all consistent checks set `recheck = true`.

## Public API / entry points

- `g_intbig_consistent(entry, query, strategy, subtype, recheck)` — `source/contrib/intarray/_intbig_gist.c:17,462-583` [verified-by-code]
- `g_intbig_compress(entry)`, `g_intbig_decompress(entry)` (no-op) — `_intbig_gist.c:18,143-205,247-250`
- `g_intbig_penalty` — Hamming distance — `_intbig_gist.c:20,290-302`
- `g_intbig_picksplit` — Hamming-distance Guttman — `_intbig_gist.c:21,319-460`
- `g_intbig_union(entryvec, *size)` — bitwise OR — `_intbig_gist.c:22,265-288`
- `g_intbig_same(a,b,*result)` — bit-equality with ALLISTRUE handling — `_intbig_gist.c:23,110-141`
- `g_intbig_options(relopts)` — `siglen` reloption — `_intbig_gist.c:24,585-597`
- `_intbig_in`/`_intbig_out` — always raise `ERRCODE_FEATURE_NOT_SUPPORTED` (the `intbig_gkey` type is internal-only) — `_intbig_gist.c:26-47`
- `signconsistent` (in `_int_bool.c`) is called for `@@` (BooleanSearchStrategy) — `_intbig_gist.c:481-489`

## Key invariants

- All consistent results are lossy: `*recheck = true` at line 476 — `_intbig_gist.c:476` [verified-by-code]
- `ALLISTRUE` signatures cover the entire universe → `g_intbig_consistent` short-circuits to `true` immediately — `_intbig_gist.c:478-479`
- Signature length is per-opclass-option (`siglen`), default 252 bytes (2016 bits), range `[1, GISTMaxIndexKeySize]` ≈ `[1, 8132]` — `_intbig_gist.c:585-596`, header constants at `_int.h:62-67`
- `g_intbig_compress` promotes to `ALLISTRUE` if every byte of the signature is 0xff — `_intbig_gist.c:182-201` [verified-by-code]
- `_intbig_overlap`/`_intbig_contains` test each query bit against the signature; only correct as a LOSSY upper bound — `_intbig_gist.c:74-108`
- `<@` (contained-by) is unreachable since intarray 1.4 (same as `_int_gist.c`) — `_intbig_gist.c:539-577` [from-comment]
- `recheck = true` always — the recheck happens by re-running the operator on the heap tuple — `_intbig_gist.c:476`

## Notable internals

- **Hash function**: `HASHVAL(val, siglen) = ((unsigned int) val) % (siglen * 8)`. Plain modulo. Deterministic across hosts. Bits set with `SETBIT`. — `_int.h:80-81`, `_intbig_gist.c:84,102,510,554`
- **Hamming distance** (`hemdistsign`) uses `pg_number_of_ones[]` byte table — `_intbig_gist.c:215-228`
- **`hemdist`** with ALLISTRUE: `dist = SIGLENBIT(siglen) - sizebitvec(other)` — i.e. the number of unset bits in the other sig — `_intbig_gist.c:230-244` [verified-by-code]
- **`sizebitvec`** uses `pg_popcount(sign, siglen)` — fast, hardware-popcount when available — `_intbig_gist.c:208-212`
- **PickSplit**: same Guttman quadratic structure as `_int_gist.c` but with Hamming-distance cost — `_intbig_gist.c:319-460`
- **Union** is bitwise OR over all entry signatures, short-circuiting to ALLISTRUE if any input is ALLISTRUE — `_intbig_gist.c:265-288`
- `_intbig_in`/`_intbig_out` raise `ERRCODE_FEATURE_NOT_SUPPORTED` — the GIST-internal key type is never user-visible — `_intbig_gist.c:30-47`

## Trust boundary / Phase D surface

This is **the** signature-collision concern in this slice. Full Phase D detail follows.

- **Hash collisions are deterministic and trivially constructible**: `HASHVAL(val) = (uint32) val % (siglen * 8)`. Default siglen → modulo 2016. For any indexed-int4 value, an attacker can precompute the bit position. To make `@@ '<target>'` queries match a chosen target row, the attacker inserts row(s) whose `int4[]` contains values that hash to the same bit set as `<target>`. Because the GiST recheck step re-runs `_int_overlap`/`_int_contains` on the heap, **false positives don't return wrong rows** — they just make the index scan visit and reject more pages. The end result is an **index-amplification DoS**: for each adversarial query an O(1)-looking index lookup walks an attacker-determined fraction of the index. — `_int.h:80`, `_intbig_gist.c:74-108` [verified-by-code] [ISSUE-COLLISION-INTBIG]
- **`ALLISTRUE` as a malicious data choice**: an attacker who can insert an array with values hashing to every bit (e.g. a 2016-element well-distributed `int4[]`) creates an ALLISTRUE leaf signature. Per `g_intbig_consistent:478-479`, every query against this leaf returns `true` immediately, forcing recheck on the heap. Repeat across many leaves and the GiST index becomes useless. — `_intbig_gist.c:182-201,478-479`
- **`siglen` reloption is per-index, attacker doesn't control it**: this is a saving grace — the index creator picks the signature length. A DBA who suspects collision attacks can raise `siglen` to e.g. `SIGLEN_MAX` ≈ 8 KB → 65536 bits, making collisions ~32× rarer at the cost of bigger index keys. — `_intbig_gist.c:585-596`
- **`signconsistent(query, sign, siglen, calcnot=false)` for `@@`**: signature path passes `calcnot=false` so any `! X` subtree returns `true` (upper bound). Correct, but attacker can craft `@@ '!<value>'` queries that force the GiST to never prune that subtree — see `_int_bool.md` for the same dynamic. — `_intbig_gist.c:481-489`
- **`g_intbig_union` palloc bounded by `siglen`** — fixed-size signatures mean a leaf entry is at most ~8 KB; safe. — `_intbig_gist.c:265-288`
- **`g_intbig_picksplit` O(maxoff²)** — same complexity as `_int_gist.c` for seed selection. Bounded by GiST page fanout. — `_intbig_gist.c:352-365`
- **`_intbig_in`/`_intbig_out`**: cannot accept/display the internal type — good (no on-disk-format injection via SQL text input). — `_intbig_gist.c:30-47`
- **`hemdistsign` uses `unsigned char` cast on XOR**: safe widening; no signed-shift UB. — `_intbig_gist.c:223`

## Cross-references

- `_int_bool.c` — `signconsistent` (BooleanSearchStrategy lossy eval)
- `_int_gist.c` — sister opclass for "small" arrays
- `_int_tool.c` — `gensign`
- `access/gist/*`, `port/pg_bitutils.h` (`pg_popcount`, `pg_number_of_ones`)
- A11 contrib top-4 — comparable signature/bloom approaches in `bloom` contrib

## Issues spotted

- [ISSUE-COLLISION-INTBIG: trivial bit-collision construction via `val % siglen_bits`; enables attacker-controlled false-positive amplification and index DoS on `gist__intbig_ops` indexes (Med — recheck still returns correct rows; only perf hit)]
- [ISSUE-ALLISTRUE: malicious 2016-distinct-value array creates ALLISTRUE leaf that defeats GiST pruning; no per-relation safeguard (Med)]
- [ISSUE-UNREACHABLE: `<@` branch (lines 536-577) dead since intarray 1.4 (Cleanup)]
- [ISSUE-DOC: no warning in opclass docs that `siglen=252` is insufficient against adversarial inserts (Doc)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-intarray.md](../../../subsystems/contrib-intarray.md)
