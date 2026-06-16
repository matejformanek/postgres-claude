# hstore_compat.c

## One-line summary

Forward-compatibility shim that, on every `DatumGetHStoreP` call, detoasts
the input and — if the on-disk value was written by the pre-PG-8.4 hstore
implementation (or the prerelease pgfoundry "hstore-new") — re-encodes it
in place to the new HEntry-based format. Also exposes the diagnostic
`hstore_version_diag(hstore) -> int` for testing.

Source pin: `4b0bf0788b0`.

## Public API / entry points

- `HStore *hstoreUpgrade(Datum orig)` — the single entry point referenced
  from `DatumGetHStoreP()` in the header (`hstore_compat.c:234-346`)
  [verified-by-code]. EVERY consumer of an hstore Datum goes through
  this.
- `hstore_version_diag(hstore) -> int4` — SQL-callable; returns
  `valid_old * 10 + valid_new`, used for testing
  (`hstore_compat.c:349-358`) [verified-by-code, from-comment].

## Key invariants

- `HOldEntry` is exactly two 32-bit words = `2 * sizeof(HEntry)`, enforced
  by `StaticAssertDecl` (`hstore_compat.c:99-109`) [verified-by-code]. So
  `ARRPTR()` macros work for both layouts; only the bit-meaning differs.
- `HS_FLAG_NEWVERSION = 0x80000000` set in `hs->size_` ⇒ definitively
  new-format; short-circuit return (`hstore_compat.c:242-243`)
  [verified-by-code].
- Empty hstore (`size_ == 0`) is identical in both formats
  (`hstore_compat.c:249-255`) [verified-by-code, from-comment].
- Three on-disk formats considered (`hstore_compat.c:5-9` header comment)
  [from-comment]:
  1. Old `contrib/hstore` (pre-PG-8.4).
  2. Pre-release pgfoundry "hstore-new" — same layout as (3) BUT without
     `HS_FLAG_NEWVERSION` set.
  3. Modern `contrib/hstore`.
- For non-trivial values that lack the new-version flag, we run BOTH
  `hstoreValidNewFormat()` and `hstoreValidOldFormat()` and decide based
  on which one validates (`hstore_compat.c:257-313`) [verified-by-code].
- Truly ambiguous edge cases (both validators pass; only possible with
  >32 KB of padding slop on the old value) are resolved by a compile-time
  toggle `HSTORE_IS_HSTORE_NEW` (`hstore_compat.c:299-313`)
  [verified-by-code, from-comment]. Modern contrib/hstore lacks that
  define, so it falls to the "old" branch and rewrites in place. A
  `WARNING` is emitted unconditionally in this branch.

## Notable internals — the in-place re-encode

The "must have an old-style value" block (`hstore_compat.c:315-343`)
[verified-by-code]:

1. Reuses `ARRPTR(hs)` as a pointer to both old AND new entry arrays —
   they're the same byte region because `sizeof(HOldEntry) ==
   2*sizeof(HEntry)`.
2. Iterates `i = 0..count-1` reading `HOldEntry { keylen, vallen, pos,
   valisnull }`, then writes two `HEntry`s in the SAME memory:
   - `new_entries[2*i].entry = (pos + keylen) & HENTRY_POSMASK;` —
     end-pos of the key.
   - `new_entries[2*i+1].entry = ((pos + keylen + vallen) & HENTRY_POSMASK) | (isnull ? HENTRY_ISNULL : 0);` — end-pos of the
     value, OR with ISNULL bit.
3. Sets `HENTRY_ISFIRST` on entry 0; calls `HS_SETCOUNT`/`HS_FIXSIZE`.

The string buffer is left untouched — the new encoding is intentionally
designed so the underlying key+value bytes don't need to move
(`hstore_compat.c:93-98` comment) [from-comment].

## Notable internals — the validators

### `hstoreValidNewFormat` (`hstore_compat.c:121-165`) [verified-by-code]

Returns 0/1/2 = invalid / valid-with-slop / exactly-valid.

Checks, in order:
1. `HS_FLAG_NEWVERSION` set ⇒ return 2 (trust the value).
2. `count == 0` ⇒ return 2.
3. `HSE_ISFIRST(entries[0])` must be set ⇒ otherwise 0.
4. `CALCDATASIZE(count, last endpos) > VARSIZE(hs)` ⇒ 0.
5. For all `i ≥ 1`: ISFIRST must NOT be set on later entries; endpos must
   be nondecreasing.
6. For all `i ≥ 1`: `keylen[i] ≥ keylen[i-1]` (sort invariant); ISNULL on
   a key entry ⇒ 0 (only values may be null).
7. `vsize != VARSIZE(hs)` ⇒ return 1 (slop); else 2.

### `hstoreValidOldFormat` (`hstore_compat.c:173-228`) [verified-by-code]

1. `HS_FLAG_NEWVERSION` set ⇒ 0.
2. `count == 0` ⇒ 2.
3. `count > 0xFFFFFFF` ⇒ 0 (the 28-bit reservation).
4. `CALCDATASIZE(count, 0) > VARSIZE(hs)` ⇒ 0.
5. First entry's `pos != 0` ⇒ 0.
6. Keylens nondecreasing.
7. Each `entry.pos == lastpos`, with `lastpos +=
   keylen + (valisnull ? 0 : vallen)`; mismatch ⇒ 0.
8. Final `vsize > VARSIZE(hs)` ⇒ 0; `vsize != VARSIZE(hs)` ⇒ 1; else 2.

These two validators are mutually exclusive in 99.9% of cases (header
comment notes the rare edge cases involving "a large excess of padding
and just the right pattern of key sizes" — `hstore_compat.c:75-79`).

## Trust boundary / Phase D surface

This file is **the** trust-the-old-format pattern (A3 pg_dump trust-the-
source). Several distinct concerns:

### Decoder DoS via forged old-format hstore (Phase D!)

`hstoreValidOldFormat` runs a `for (i = 1; i < count; ++i)` loop
(`hstore_compat.c:199-203`, `211-217`) [verified-by-code]. `count` is
read directly from `hs->size_` (a forged hstore could claim `count =
0xFFFFFFF = 268M`); the `count > 0xFFFFFFF` check
(`hstore_compat.c:188-189`) [verified-by-code] only rejects values
strictly greater than that. So a maliciously-crafted old-format hstore
can force `O(count)` iterations on a single forged value. The
preceding `CALCDATASIZE(count, 0) > VARSIZE(hs)` check
(`hstore_compat.c:191-192`) [verified-by-code] is the actual gate —
each HOldEntry is 8 bytes, so an attacker needs `8*count` payload, but
that's at most `VARSIZE(hs) - HSHRDSIZE ≈ MaxAllocSize ≈ 1 GB`. So
`count` is bounded around `128M` per single hstore — still bad if you
can feed many. `[ISSUE-defense-in-depth: hstoreValidOldFormat does not
fast-fail on garbage count before the loop; CALCDATASIZE is the only
gate. Bound is ~128M iterations per value (maybe)]`.

### Trust-the-source on pg_dump restore

The whole point of this file is to silently accept old-format hstores
from a dump (`hstore_compat.c:22-29` comment notes this is normal).
That means a dump file IS a forgery channel: any user with `pg_restore`
authority on a database has authority to feed arbitrary on-disk hstore
bytes through `hstoreUpgrade`. Whether this is a "trust boundary" in
the Phase D sense depends on whether you trust the dump source —
exactly the A3 pattern. `[ISSUE-security: hstoreUpgrade is a primary
"trust the dump file" surface; combined with the modest validator
checks, a malformed dump can trigger O(count) loops + WARNING-spam at
restore time (maybe)]`.

### Version-bit confusion

`hstoreUpgrade` decides between three formats based on (a) whether
`HS_FLAG_NEWVERSION` is set, (b) whether the value LOOKS like new or
old format per the validators. A forged hstore that:
- Has `HS_FLAG_NEWVERSION = 0` (i.e. claims to be old)
- Has an entry layout that ALSO validates as old via `hstoreValidOldFormat`
- Has carefully-chosen "pos" values pointing at attacker-chosen offsets

...will hit the re-encode loop (`hstore_compat.c:315-343`). The loop
computes `new_entries[2*i].entry = (pos + keylen) & HENTRY_POSMASK` —
`pos + keylen` might overflow (both are `uint32`); the `& HENTRY_POSMASK`
silently truncates to 30 bits, which could (a) construct an HStore with
wildly wrong endpos values that escape the validator AND (b) decouple
the key/value boundaries from the actual string-buffer layout. The
`hstoreValidNewFormat` would catch most cases on the NEXT `hstoreUpgrade`
call but NOT on this one — and at that point the on-disk value (if
written back via UPDATE) would be persistently corrupt.
`[ISSUE-correctness: pos+keylen / pos+keylen+vallen arithmetic in the
re-encode loop has no overflow guard; HENTRY_POSMASK truncation can
silently bury overflow into a "valid" new-format hstore that points
outside the string buffer (likely)]`.

### Forged version byte routing to wrong decoder

Per the task prompt: "can a forged version byte route to wrong decoder?"
Answer: yes, *intentionally*. If the user forges
`HS_FLAG_NEWVERSION = 1` on what is structurally an old-format hstore,
`hstoreUpgrade` returns it immediately (`hstore_compat.c:242-243`) — no
validation. Every downstream macro then treats it as new-format and
reads the HEntries with the new bit semantics. Since old format used
the top bit as either `valisnull` (i386 layout) or one of `keylen`'s
bytes (other endianness), the HSE_ISFIRST / HSE_ISNULL / HSE_ENDPOS
extraction will produce arbitrary garbage. The result is type confusion
+ controllable OOB reads from the string buffer. `[ISSUE-security: a
forged HS_FLAG_NEWVERSION bit on a structurally-old hstore bypasses ALL
validation and gets treated as new-format; downstream accessors will
OOB-read (likely)]`. Defense: every consumer assumes input came through
the validated input path (hstore_in / hstore_recv / hstoreUpgrade); a
forgery channel that bypasses those (e.g. binary pg_dump from a
malicious peer) defeats the assumption.

### `hstoreValidNewFormat` doesn't check string-buffer bounds

The check `vsize > VARSIZE(hs)` (`hstore_compat.c:139-141`)
[verified-by-code] ensures the *encoded* size fits; but `vsize =
CALCDATASIZE(count, lastEndPos)`. If `lastEndPos` is small (e.g. all
keys/values have endpos=0) the validator passes even though intermediate
HEntries claim huge endpos. Wait — the nondecreasing check at
`hstore_compat.c:144-149` catches that: any entry's endpos > the last
entry's endpos would have failed the nondecreasing check. OK that's
fine. `[verified-by-code]`.

## Cross-references

- `hstore.h.md` — the HEntry/HStore layout constants this file reverse-
  engineers.
- `hstore_io.c.md` — `hstore_in` / `hstore_recv` produce new-format only;
  this compat layer is exclusively a consumer-side migration.
- A7 jsonb_recv DoS pattern — same shape: forged count in user-controlled
  binary buffer.
- A3 pg_dump trust-the-source — every contrib type that supports old
  on-disk formats inherits this trust assumption.

<!-- issues:auto:begin -->
- [Issue register — `hstore`](../../../issues/hstore.md)
<!-- issues:auto:end -->

## Issues spotted

- `[ISSUE-correctness: pos+keylen arithmetic in re-encode loop has no
  overflow guard; HENTRY_POSMASK truncation can silently bury overflow
  into a hstore pointing outside the string buffer (likely)]`
- `[ISSUE-security: a forged HS_FLAG_NEWVERSION bit on a structurally-old
  hstore bypasses ALL validation and is trusted as-is (likely)]`
- `[ISSUE-defense-in-depth: hstoreValidOldFormat does not fast-fail on
  garbage count before the loop; CALCDATASIZE is the only gate, allowing
  ~128M iterations per forged value (maybe)]`
- `[ISSUE-security: hstoreUpgrade is a primary "trust the dump file"
  surface; combined with modest validator checks, a malformed dump can
  trigger O(count) loops + WARNING-spam at restore (maybe)]`
- `[ISSUE-error-handling: ambiguous-resolution unconditionally elog(WARNING)
  even on the "resolved as hstore-old" path (hstore_compat.c:311); the
  XXX comment notes this should "probably be downgraded to DEBUG1 once
  this has been beta-tested" — that comment dates from the pre-PG-8.4
  era (>15 years stale) (nit)]`
- `[ISSUE-defense-in-depth: HSE_ISNULL bit on a key entry is checked
  (hstore_compat.c:157-158), but a forged ISFIRST bit on entry i>0 is
  also caught (hstore_compat.c:146); however, neither the ISNULL nor the
  reserved-bits in size_ (between HS_FLAG_NEWVERSION at 0x80000000 and
  count mask 0x0FFFFFFF, i.e. 0x70000000) are validated; the comment in
  hstore.h:54 says "Some bits are left for future use" — a forgery that
  sets them won't be rejected (nit)]`
- `[ISSUE-api-shape: hstore_version_diag is publicly SQL-registered (PG_FUNCTION_INFO_V1 + .control file SQL) but the file comment calls it "otherwise undocumented" (hstore_compat.c:81-82); user-visible behavior with no documentation (nit)]`
