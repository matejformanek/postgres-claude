# pgp-info.c

## One-line summary

Implements `pgp_get_keyid(pgp_data, dst)` — scan a PGP key blob or
encrypted message and emit a 16-hex-char key ID, the string `"SYMKEY"`
for symmetric-only messages, or `"ANYKEY"` for the OpenPGP all-zero
wildcard. Backs SQL `pgp_key_id(bytea)`.

## Public API / entry points

- `pgp_get_keyid(MBuf *pgp_data, char *dst)` —
  `source/contrib/pgcrypto/pgp-info.c:112` [verified-by-code]. `dst`
  must have room for 17 bytes (16 hex + NUL).

## Key invariants

- Parses packets via `pgp_parse_pkt_hdr` + `pgp_create_pkt_reader`. No
  decryption attempted.
- Returns 16 (hex chars) on success for known key ID; 6 for
  `"SYMKEY"` or `"ANYKEY"`. Negative `PXE_*` on error.
- **Rejects multiple main keys** (`PXE_PGP_MULTIPLE_KEYS`),
  `source/contrib/pgcrypto/pgp-info.c:151,205,208`. Limit one per blob.
- Recognizes only signature-skipping packets:
  `MARKER/TRUST/USER_ID/USER_ATTR/SIGNATURE/PRIV_61` and skips them
  with `pgp_skip_packet`. Anything unknown → `PXE_PGP_CORRUPT_DATA`,
  `source/contrib/pgcrypto/pgp-info.c:181-183`.

## Notable internals

- `read_pubkey_keyid(pkt, keyid_buf)` —
  `source/contrib/pgcrypto/pgp-info.c:38`. Reads the public-key
  half (skips secret half), then keeps the key_id only if the algo is
  encryption-capable (Elgamal, RSA-enc, RSA-enc-sign). Returns 0 for
  signing-only keys (e.g. RSA-sign, DSA), 1 for encryption keys.
- `read_pubenc_keyid(pkt, keyid_buf)` —
  `source/contrib/pgcrypto/pgp-info.c:71`. Parses just the v3
  pubenc-sesskey header to extract the recipient key_id.
- The main loop breaks at the first encrypted-data packet to avoid
  attempting to skip past large bodies.
- **Sanity check** at the end: if both a `PUBLIC_KEY` packet and a
  `PUBENCRYPTED_SESSKEY` are present, that's malformed
  (`source/contrib/pgcrypto/pgp-info.c:201-202`). A keyring + a
  ciphertext shouldn't be combined.

## Crypto trust boundary / Phase D surface

- **Information disclosure.** `pgp_key_id(bytea)` reveals the key ID
  to anyone who has the ciphertext or public-key blob. This is **by
  design** — RFC 4880 puts the key ID right in the pubenc packet
  precisely so the recipient knows which key to use. Not a leak.
- **Long Key ID = 64 bits = 8 bytes.** OpenPGP key IDs are the last 8
  bytes of the SHA-1 fingerprint (`pgp-pubkey.c:151`). The SKS
  keyserver "evil 32" attack (2013) showed that **short** 32-bit key
  IDs are trivially collidable; 64-bit is borderline (estimated $/$
  thousand-dollar collision). For key *selection* (e.g. "decrypt with
  the key whose ID matches"), this is concerning if pgcrypto were to
  consume keyrings; but it doesn't — one key per `PGP_Context`.
  [ISSUE-defense-in-depth: 64-bit long-key-ID is the only key
  selector; collision-resistance is ~2^32 work; modern OpenPGP uses
  full v4 fingerprints (20B SHA-1) or v5 (32B SHA-256). Pgcrypto
  exposes only the long key ID via `pgp_key_id` (maybe)] —
  `source/contrib/pgcrypto/pgp-info.c:217-223`.
- **Returns "ANYKEY" for all-zero key ID.** Lets the caller see that
  the ciphertext can be tried against any private key.
- **`pgp_get_keyid` is purely a parser** — no key material loaded, no
  decryption. Lower-risk surface than `pgp_pub_decrypt`.

## Cross-references

- `pgp-pubkey.md` — `_pgp_read_public_key` parses the keys here, sets
  `pk->key_id` via SHA-1 fingerprint truncation.
- `pgp-decrypt.md` — uses similar packet-iteration but actually
  attempts decryption.
- `pgp-pgsql.md` — `pgp_key_id_w` SQL wrapper.

<!-- issues:auto:begin -->
- [Issue register — `pgcrypto`](../../../issues/pgcrypto.md)
<!-- issues:auto:end -->

## Issues spotted

- [ISSUE-defense-in-depth: exposes only 64-bit long key ID, not full
  v4 fingerprint; collision-resistance ~2^32 (maybe)] —
  `source/contrib/pgcrypto/pgp-info.c:217-223`.
- [ISSUE-correctness: at end-of-loop, `pkt = NULL` is set inside the
  loop and `pkt` is re-checked outside (line 194); double-free guard
  is defensive but suggests history of bugs (nit)] —
  `source/contrib/pgcrypto/pgp-info.c:185-194`.
- [ISSUE-audit-gap: no warning if input is partial (no encrypted-data
  packet seen but EOF reached); silently returns whatever key_id was
  parsed (nit)] —
  `source/contrib/pgcrypto/pgp-info.c:213-231`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pgcrypto.md](../../../subsystems/contrib-pgcrypto.md)
