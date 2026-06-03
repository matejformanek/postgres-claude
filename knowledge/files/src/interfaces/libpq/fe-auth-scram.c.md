---
path: src/interfaces/libpq/fe-auth-scram.c
anchor_sha: 4b0bf0788b0
loc: 953
depth: deep
---

# fe-auth-scram.c

- **Source path:** `source/src/interfaces/libpq/fe-auth-scram.c`
- **Lines:** 953
- **Last verified commit:** `4b0bf0788b0`
- **Companion files:** `fe-auth.c` (`pg_SASL_init` mounts `pg_scram_mech`), `src/common/scram-common.c` (`scram_SaltedPassword`, `scram_ClientKey`, `scram_ServerKey`, `scram_H`, `scram_build_secret`), `src/common/saslprep.c` (`pg_saslprep`), `src/common/hmac.c` (`pg_hmac_*`), `src/common/base64.c`, `fe-secure-openssl.c::pgtls_get_peer_certificate_hash` (for channel-binding payload).

## Purpose

Client-side implementation of **SCRAM-SHA-256** and **SCRAM-SHA-256-PLUS** (channel-binding variant) per RFC 5802 / RFC 7677. Exports `pg_scram_mech`. Drives the 3-message exchange: client-first → server-first → client-final + proof → server-final + signature. [verified-by-code, fe-auth-scram.c:24-38]

## API surface

- `pg_scram_mech` (33-38) — the mechanism vtable: `scram_init`, `scram_exchange`, `scram_channel_bound`, `scram_free`. Consumed by `pg_SASL_init` in fe-auth.c.
- `pg_fe_scram_build_secret(password, iterations, errstr)` (914-953) — client-side verifier builder for `PQencryptPasswordConn(algorithm="scram-sha-256")`. Generates a random salt via `pg_strong_random` and calls `scram_build_secret`.

## Internal state

`fe_scram_state` struct (52-81):
- `state` — 4-step enum `FE_SCRAM_INIT` → `NONCE_SENT` → `PROOF_SENT` → `FINISHED`.
- `password` — SASLprep-normalized (or original if SASLprep failed).
- `sasl_mechanism` — strdup of the chosen mech name (used by `channel_bound` to gate on `-PLUS`).
- `hash_type` / `key_length` — hardcoded `PG_SHA256` / `SCRAM_SHA_256_KEY_LEN`.
- `SaltedPassword` — the PBKDF2-derived key, cached for use in both `calculate_client_proof` and `verify_server_signature`.
- `client_nonce`, `client_first_message_bare`, `client_final_message_without_proof` — material that must be carried across the exchange for HMAC computation.
- `salt`, `saltlen`, `iterations`, `nonce` — from server-first message.
- `ServerSignature` — from server-final, compared in constant time against locally computed expected sig.

## Mechanism flow (verified)

### `scram_init` (96-147)
- `calloc` zero-init the state struct.
- Run `pg_saslprep(password, &prep_password)`. If `SASLPREP_OOM` fail; otherwise even on `SASLPREP_FAILURE` (e.g. invalid UTF-8) fall back to the literal `strdup(password)`. [verified-by-code, fe-auth-scram.c:126-142]
- Default `hash_type = PG_SHA256`, `key_length = SCRAM_SHA_256_KEY_LEN` — currently SCRAM is hardcoded to SHA-256; the struct allows extension.

### `build_client_first_message` (349-449)
- `pg_strong_random(raw_nonce, SCRAM_RAW_NONCE_LEN)` (line 363) — the platform's crypto-RNG. Falls back to `OPENSSL_RAND_bytes`, `arc4random_buf`, `getrandom`, or `/dev/urandom` depending on build. Failure aborts with "could not generate nonce". [verified-by-code, fe-auth-scram.c:363-367]
- Base64-encode the nonce → `state->client_nonce`.
- Construct gs2-header:
  - `p=tls-server-end-point` if `-PLUS` (399-402).
  - `y` if SSL + non-disabled binding but the client wishes to advertise support without using it (404-411).
  - `n` otherwise (413-419).
- Final message: `<gs2>,,n=,r=<client_nonce>`. The `n=` username is **empty** because the backend uses the startup-packet username (390-393). NB: this skips SASLprep on the username, so a username with `=` or `,` would break message parsing — but libpq never sends a username via the SASL stream. [from-comment, fe-auth-scram.c:387-391]

### `read_server_first_message` (606-687)
- **Nonce check** (line 632-638): the server's nonce MUST start with the client's nonce, compared via `timingsafe_bcmp`. Mismatch = `"invalid SCRAM response (nonce mismatch)"`. [verified-by-code, fe-auth-scram.c:632-638]
- Parse `s=<base64 salt>`, `i=<iterations>`. Validates `iterations >= 1` (677), no garbage after. [verified-by-code, fe-auth-scram.c:677-684]
- **Iteration count** is server-controlled and unvalidated upper bound — a malicious server can set `iterations = INT_MAX` and force the client to spin in PBKDF2. No upper-bound check. See ISSUE.

### `build_client_final_message` (454-601)
- For `-PLUS`: pull `pgtls_get_peer_certificate_hash(conn, &cbind_data_len)` (line 486), prepend `"p=tls-server-end-point,,"`, base64-encode the whole thing as the `c=` attribute. [verified-by-code, fe-auth-scram.c:474-532]
- For non-PLUS with SSL + non-disabled binding: `c=eSws` (base64 of `y,,`).
- Otherwise: `c=biws` (base64 of `n,,`).
- Append `,r=<combined nonce>`.
- Call `calculate_client_proof` to compute the proof; base64-encode and append as `,p=`.

### `calculate_client_proof` (765-836)
- `scram_SaltedPassword(password, salt, iterations) → SaltedPassword` (PBKDF2-HMAC-SHA-256). Stored in state for reuse by `verify_server_signature`. [verified-by-code, fe-auth-scram.c:792-797]
- `scram_ClientKey(SaltedPassword) = HMAC(SaltedPassword, "Client Key")` (797-799).
- `scram_H(ClientKey) = SHA256(ClientKey) = StoredKey` (806).
- `ClientSignature = HMAC(StoredKey, AuthMessage)` where `AuthMessage = client-first-bare,server-first,client-final-without-proof` (812-824).
- `ClientProof[i] = ClientKey[i] XOR ClientSignature[i]` (831-832).
- **`scram_client_key_binary` override** (783-786): if set on the connection (LDAP injection or test harness), `ClientKey` is taken verbatim and SaltedPassword is **not computed**. This means `verify_server_signature` will need `scram_server_key_binary` set too — there's no derivation path from a binary ClientKey to a ServerKey.

### `verify_server_signature` (845-906)
- `ServerKey = HMAC(SaltedPassword, "Server Key")` (866).
- `expected_ServerSignature = HMAC(ServerKey, AuthMessage_full)` (876-889).
- **Constant-time compare** via `timingsafe_bcmp` (line 899-903). [verified-by-code, fe-auth-scram.c:899-903]
- If the override `scram_server_key_binary` is set (line 860), use it directly instead of deriving from `SaltedPassword`. [verified-by-code, fe-auth-scram.c:860-862]

### `read_server_final_message` (693-758)
- Detects an `e=<errmsg>` server-error response and propagates the message (708-721).
- Parses `v=<base64 server signature>` and decodes into `state->ServerSignature`. Length-checked against `key_length`. [verified-by-code, fe-auth-scram.c:735-755]

### `scram_channel_bound` (157-176)
- Returns true ONLY if state is `FE_SCRAM_FINISHED` AND mechanism is `SCRAM-SHA-256-PLUS`. The triple check (exchange completed + state finished + mech name) prevents calling code from being fooled by an aborted-mid-exchange state. [verified-by-code, fe-auth-scram.c:157-176]

## Invariants & gotchas (security-critical)

- **Nonce comparison uses `timingsafe_bcmp`** (line 634) even though the client nonce is a random prefix not really a secret. Defensive against pathological micro-architectural side channels in the prefix-compare. [verified-by-code, fe-auth-scram.c:632-638]
- **ServerSignature compared with `timingsafe_bcmp`** (line 899). This is the actual mutual-auth check — if a MITM is trying to forge the server signature, the constant-time comparison prevents byte-by-byte timing leak. [verified-by-code, fe-auth-scram.c:899-903]
- **Mechanism string must match between init and final messages.** The gs2-header channel-binding byte (`p`/`y`/`n`) chosen in `build_client_first_message` and the `c=` attribute in `build_client_final_message` must be derivable from the SAME inputs — they are, but the comment at lines 470-472 explicitly flags that the server cross-checks these to detect a MITM stripping channel binding. [from-comment, fe-auth-scram.c:470-472]
- **`scram_free` does NOT scrub `password`** (line 186 just `free(state->password)`). The SASLprep'd password (or the original) sits in libc free-list memory. [verified-by-code, fe-auth-scram.c:182-203]
- **`SaltedPassword`** lives in the state struct as a stack-like `uint8[SCRAM_MAX_KEY_LEN]` (66). The `scram_free` does NOT memset it. Same scrub-on-free issue as the password. [verified-by-code, fe-auth-scram.c:66, 182-203]
- **Hash type is hardcoded to PG_SHA256** (line 113-114). A future SCRAM-SHA-512-PLUS would need code changes here, not just a new mech-name constant. [verified-by-code, fe-auth-scram.c:113-114]
- **`build_client_final_message` for `-PLUS` without USE_SSL** is a logic dead-end (line 533-542): cannot happen because `pg_SASL_init` refuses `-PLUS` mechanism without USE_SSL, but the defensive `#else` branch is present. [verified-by-code, fe-auth-scram.c:533-542]

## Potential issues

- ISSUE-libpq-scram-001 (severity: likely) — **No upper bound on `iterations`** in `read_server_first_message` (line 677). A malicious or compromised server can set iterations to a very large value (up to INT_MAX) and force the client to PBKDF2-spin. On a low-power client this is a CPU DoS. The server-side `auth-scram.c` checks an upper bound on the verifier-build side, but a server sending an arbitrary value to the client has no client-side cap. [verified-by-code, fe-auth-scram.c:676-681]
- ISSUE-libpq-scram-002 (severity: likely) — **`scram_free` does not scrub the password buffer or `SaltedPassword`** before freeing (lines 182-203). Both are recoverable from process memory after the SASL exchange ends. `explicit_bzero` should be applied per defense-in-depth. (Compare with `pqClearOAuthToken` in fe-auth-oauth.c:1430 which does scrub.) [verified-by-code, fe-auth-scram.c:182-203]
- ISSUE-libpq-scram-003 (severity: maybe) — **`incorrect server signature`** error path (line 281-284): the error is appended to `errorMessage` but `state->state = FE_SCRAM_FINISHED` is set anyway (285). The exchange returns `SASL_FAILED` because `match == false`, but the `client_finished_auth = true` flag is also set unconditionally on line 286. If a higher-level retry happens, `check_expected_areq` may now wrongly believe auth completed. The retry path is normally aborted, but the latch is incongruent. [verified-by-code, fe-auth-scram.c:281-287]
- ISSUE-libpq-scram-004 (severity: maybe) — **No SASLprep on the username.** The comment at line 387-391 acknowledges this is a footgun — a username containing `=` or `,` would break parsing — but libpq sends the empty username in the SCRAM message and relies on the startup packet for the actual login name. A future change that re-introduces the username into the SCRAM stream would need SASLprep. [from-comment, fe-auth-scram.c:387-391]
- ISSUE-libpq-scram-005 (severity: maybe) — `read_attr_value` (307-344) destructively modifies the input buffer (writes `\0` at end of each attribute). The `state->server_first_message` is `strdup`'d before parsing (616), but the duplicate is *also* parsed (line 623-): the strdup is for HMAC use in `calculate_client_proof`, while parsing destroys `input` (the caller's buffer in `pg_SASL_continue`). The buffer is the SASL challenge, freed right after — safe today but fragile. [verified-by-code, fe-auth-scram.c:606-624, 700-705]
- ISSUE-libpq-scram-006 (severity: maybe) — `scram_exchange` for the `FE_SCRAM_PROOF_SENT` case (263-288): if `read_server_final_message` succeeded but `verify_server_signature` reports `errstr`, the code calls `libpq_append_conn_error` (line 277) and returns `SASL_FAILED` — but `state->state = FE_SCRAM_FINISHED` was already set (line 285) AFTER the verify call. Actually order is: verify_server_signature (275), state = FINISHED (285), return SASL_FAILED if !match. This means `client_finished_auth = true` (286) is set even on signature-verification failure. [verified-by-code, fe-auth-scram.c:271-288]

## Cross-refs

- Mechanism vtable callers: `fe-auth.c::pg_SASL_init` (line 501, 537), `pg_SASL_continue` (line 734).
- Cryptographic primitives: `src/common/scram-common.c` (SaltedPassword, ClientKey, ServerKey, H, build_secret), `src/common/hmac.c` (pg_hmac_*), `src/common/saslprep.c`.
- Channel binding: `fe-secure-openssl.c::pgtls_get_peer_certificate_hash` (line 339-412).
- See also: `knowledge/files/src/interfaces/libpq/fe-auth.c.md`.

## Tally
`[verified-by-code]=27 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=0`
