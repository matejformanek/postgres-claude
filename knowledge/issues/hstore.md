# Issues — `contrib/hstore`

Per-subsystem issue register for **hstore**, the key-value-pairs-as-
a-type extension. 7 source files / ~4 520 LOC.

**Parent docs:** `knowledge/files/contrib/hstore/*` (7 docs).

**Source:** ~42 entries surfaced 2026-06-09 by A13-1.

## Headlines

1. **Forged `HS_FLAG_NEWVERSION` bypasses ALL validation in
   `hstoreUpgrade`** (`hstore_compat.c:242-243`). Fast path
   "if HS_FLAG_NEWVERSION set, return immediately" trusts the bit on
   a structurally-old hstore — downstream accessor macros
   (`HSE_ISFIRST`, `HSE_ISNULL`, `HSE_ENDPOS`) read garbage; downstream
   `HSTORE_KEY`/`HSTORE_VAL` memcpy off attacker-controlled offsets =
   controllable OOB-read. **Closest hstore equivalent to A7 binary-
   decoder confusion + A3 pg_dump trust-the-source pattern.** The
   dump/restore channel is the realistic forgery vector.

2. **`hstore_compat.c` in-place re-encode has unchecked
   `pos+keylen` arithmetic** (`hstore_compat.c:334-336`).
   `HENTRY_POSMASK` (0x3FFFFFFF) silently truncates overflow; the
   `hstoreValidNewFormat` check catches the call but bytes are
   rewritten in place — if the value persists (concat with normal
   hstore + UPDATE), trust boundary permanently shifted.

3. **`hstore_recv` ~26M-pair cap is loose** (`hstore_io.c:521-525`).
   Better than A7 tsvectorrecv but a single ~240 MB recv message
   spins tens of seconds of palloc churn + qsort over 26M Pairs.
   Per-element length well-bounded by `hstoreCheckKeyLen`.

4. **GiST signature uses CRC32 (collision-trivial) + default
   128-bit signature** (`hstore_gist.c:80-90,23`). False positives
   reconciled by `recheck=true`; **attacker who controls inserted
   hstore content can compute CRC32 collisions targeting hot
   signature bits**, polluting index pages to force pessimal recheck
   workloads. Unreasonably-low `siglen` lower bound of 1 byte (8
   bits = 100% FP rate) — knobs that can be misused.

## Cross-sweep references

- **A3 pg_dump trust-the-source** — hstore_compat is the canonical
  restore-from-untrusted-dump surface
- **A7 tsvectorrecv DoS** — hstore_recv is the better-bounded sibling
- **A12 pageinspect bounds-checking discipline** — hstore's varlena
  format trust assumptions parallel pageinspect's `PageGetItem`
  invariants

## Entries (~42 total)

### hstore.h

- [ISSUE-defense-in-depth: HENTRY_POSMASK silently truncates top-2
  bits; only secondary validation catches forged endpos (maybe)]
- [ISSUE-audit-gap: HS_COPYITEM/HS_ADDITEM macros memcpy without
  internal length cap; correctness depends on every caller
  pre-validating (likely)]
- [ISSUE-documentation: comment on hstore.h:88-89 names
  hstore_compat.c as "the exception" but underspecifies the other
  writers (nit)]
- [ISSUE-api-shape: HSTORE_POLLUTE_NAMESPACE defaults to 1; old
  pre-namespace names registered as SQL-visible C symbols even in
  modern installs (maybe)]

### hstore_compat.c

- [ISSUE-correctness: pos+keylen arithmetic in re-encode loop has
  no overflow guard; HENTRY_POSMASK truncation silently buries
  overflow (likely)] — `source/contrib/hstore/hstore_compat.c:334-336`.
- [ISSUE-security: forged HS_FLAG_NEWVERSION bit on structurally-
  old hstore bypasses ALL validation; downstream accessors OOB-read
  (likely)] — `source/contrib/hstore/hstore_compat.c:242-243`.
- [ISSUE-defense-in-depth: hstoreValidOldFormat does not fast-fail
  on garbage count; CALCDATASIZE is the only gate, ~128M iterations
  per forged value (maybe)].
- [ISSUE-security: hstoreUpgrade is the primary "trust the dump file"
  surface (maybe)].
- [ISSUE-error-handling: ambiguous-resolution unconditionally
  WARNINGs even on "resolved as hstore-old"; 15+ year stale XXX
  (nit)].
- [ISSUE-defense-in-depth: reserved bits 0x70000000 in size_ not
  validated; "left for future use" comment (nit)].
- [ISSUE-api-shape: hstore_version_diag SQL-registered but
  "otherwise undocumented" (nit)].

### hstore_gin.c

- [ISSUE-defense-in-depth: extract_hstore_query does not bound
  query key length; GIN's index-key-size limit is the only backstop
  (nit)].
- [ISSUE-api-shape: NULL elements in ExistsAny/ExistsAll text
  arrays silently dropped without warning (nit)].
- [ISSUE-documentation: null-as-flag scheme "9.1" comment is
  ancient; on-disk-compat lock-in deserves a clearer note (nit)].
- [ISSUE-correctness: gin_extract_hstore_query Contains path
  forwards NULL entries pointer; relies on subtle palloc-gated
  NULL (nit)].

### hstore_gist.c

- [ISSUE-defense-in-depth: default siglen=16 (128 bits) gives high
  false-positive rate; recheck enforces correctness (nit, by
  design)].
- [ISSUE-api-shape: siglen lower bound 1 byte is operationally
  useless; no warning at CREATE INDEX (nit)].
- [ISSUE-security: CRC32 hashing is collision-trivial; attacker-
  controlled hstore keys can pollute signature bits to degrade
  query performance (maybe)].
- [ISSUE-documentation: ghstore_in/out error rationale not
  explained (catalog-requirement) (nit)].
- [ISSUE-api-shape: ALLISTRUE flag's bit value 0x04 is unexplained
  historical artifact (nit)].

### hstore_io.c

- [ISSUE-memory: hstore_in's get_val grows parse buffer by doubling
  before length-checking; defers rejection (nit)].
- [ISSUE-defense-in-depth: hstore_recv pcount bound (~26M pairs)
  is loose; combined with qsort can spin ~seconds per recv message
  (maybe)] — `source/contrib/hstore/hstore_io.c:521-525`.
- [ISSUE-correctness: hstore_recv accepts embedded NULs; hstore_out
  emits as-is; asymmetric I/O (maybe)].
- [ISSUE-correctness: hstore_out palloc 2x-overshoots for escape;
  near-1GB hstores can't stringify even though valid (maybe)].
- [ISSUE-correctness: 't'/'f' boolean heuristic in loose-mode JSON
  is lossy by design (nit)].
- [ISSUE-api-shape: hstore_in's "NULL" keyword is ASCII-only
  pg_strcasecmp (nit)].
- [ISSUE-documentation: hstore_out 2x-overshoot TODO has aged
  poorly (nit)].
- [ISSUE-error-handling: hstore_in's get_val state-machine PRSEOF
  duplication across states (nit)].
- [ISSUE-audit-gap: hstoreUniquePairs keeps FIRST duplicate (per
  qsort order), not LAST (nit)].
- [ISSUE-defense-in-depth: hstore_populate_record uses
  lookup_rowtype_tupdesc_domain with noError=false (nit)].
- [ISSUE-audit-gap: hstore_recv calls hstoreUniquePairs AFTER all
  reads; 26M duplicate keys all palloc'd before dedup (maybe)].

### hstore_op.c

- [ISSUE-correctness: hstore_concat early SET_VARSIZE at line 489
  is dead code overwritten by HS_FIXSIZE (nit)].
- [ISSUE-correctness: hstore_cmp depends on canonical sorted
  layout; forged-but-validating hstore would compare unequal
  (maybe)].
- [ISSUE-defense-in-depth: hstore_hash/hash_extended rely on Assert
  for canonical-size invariant; production builds silently hash
  off-spec values differently (maybe)].
- [ISSUE-api-shape: NULL-key handling inconsistent across
  hstore_op.c (slice preserves, delete drops, concat/contains
  can't see) (nit)].
- [ISSUE-documentation: hstore_svals' "ugly ugly ugly" SRF-null
  comment is stale (nit)].
- [ISSUE-audit-gap: setup_firstcall lacks explanatory comment
  beyond "(At least I assume that's why...)" (nit)].
- [ISSUE-correctness: hstore_to_array_internal interleaved-output
  behavior not documented (nit)].
- [ISSUE-error-handling: hstore_populate_record
  lookup_rowtype_tupdesc_domain noError=false (nit)].
- [ISSUE-correctness: hstore_each vs hstore_svals use two different
  ways to emit SQL NULL (nit)].
- [ISSUE-defense-in-depth: hstoreFindKey lowbound in/out has no
  bounds-check on *lowbound; caller trusted (nit)].

### hstore_subs.c

- [ISSUE-memory: subscript assignment overestimates allocation by
  ~header+entries*2; reduces effective MaxAllocSize budget (nit)].
- [ISSUE-api-shape: fetch returns NULL for both "missing key" and
  "key with null value"; documented but worth audit flag (nit)].
- [ISSUE-documentation: file-header doesn't mention null-value-
  returns-SQL-NULL semantics (nit)].
