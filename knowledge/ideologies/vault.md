# supabase_vault — a secrets store whose root key is loaded from a shell script into libsodium-locked memory, never exposed to SQL, and decrypted on the fly by a view

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `supabase/vault` @ branch `master` (extension `supabase_vault`,
> v0.3.1). All `file:line` cites below point into that repo (not `source/`),
> since this doc characterizes an *external* extension's divergence from core
> idioms. Cites verified against the files fetched on 2026-07-18 (see Sources
> footer). Companion to `[[pgsodium]]` (the libsodium binding vault sits on)
> and `[[pgsodium]]`-family crypto exts.

## Domain & purpose

Vault stores application secrets (API keys, tokens) encrypted at rest.
Callers `INSERT` plaintext into `vault.secrets` (or call
`vault.create_secret(text, name, description)`); the row is stored **encrypted**
on disk and in any `pg_dump`, and reading back the plaintext is done only
through a special view `vault.decrypted_secrets`, which decrypts "on the fly"
using a key "that is itself not available to SQL, but can be referred to by ID"
(`README.md:12-22`, `31-47`) `[from-README]`. The control comment is "Supabase
Vault Extension", `relocatable = false`, `schema = vault`
(`supabase_vault.control.in:1-5`) `[verified-by-code]`.

**The one thing that makes Vault structurally distinct.** The interesting
divergence is not the crypto (that is delegated to `[[pgsodium]]`/libsodium) but
**where the root key comes from and where it lives**. Core Postgres has no
concept of a server-lifetime secret held outside SQL reach. Vault's ~100 lines
of C exist solely to, at postmaster start, **`popen()` an external shell script**,
read a 64-hex-char key off its stdout, and stash it in **libsodium's guarded
`sodium_malloc` heap** (mlock'd, swap-excluded, guard-paged) as a process-global
that SQL can never select — only libsodium C functions can read it
(`supabase_vault.c:41-99`) `[verified-by-code]`. The feature ("secrets table +
decrypting view") is pure SQL on top; the *ideology* is the out-of-band key
bootstrap and the off-`MemoryContext` locked key buffer.

## How it hooks into PG

- **`_PG_init` (`supabase_vault.c:16-100`).** `sodium_init()` first
  (`:26-31`); if not preloaded via `shared_preload_libraries` it returns early
  and does nothing else (`:34-35`) — so the key bootstrap only runs in the
  postmaster `[verified-by-code]`.
- **A `PGC_POSTMASTER` string GUC** `vault.getkey_script`
  (`DefineCustomStringVariable`, `supabase_vault.c:41-43`), defaulting to
  `<sharepath>/extension/<PG_GETKEY_EXEC>` computed from `get_share_path`
  (`:37-39`) `[verified-by-code]`.
- **Depends on `[[pgsodium]]`** — `#include "pgsodium.h"` (`supabase_vault.c:10`)
  and writes the shared global `pgsodium_secret_key` (`:87-96`); `CREATE
  EXTENSION supabase_vault CASCADE` pulls pgsodium in (`README.md:29`)
  `[verified-by-code]`.
- **The whole user-facing feature is SQL** (`supabase_vault--0.3.0.sql`): the
  `vault.secrets` table (`:16-25`), the `vault.decrypted_secrets` view
  (`:31-51`), `vault.create_secret` / `vault.update_secret`
  (`:53-119`), and the AEAD wrapper functions bound to pgsodium C symbols
  (`:1-14`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. Root key from a shell command, at postmaster start, before SQL exists

Vault runs an external program to obtain its master secret:

```
if ((fp = popen (getkey_script, "r")) == NULL) { ereport(ERROR …); proc_exit(1); }
char_read = getline (&secret_buf, &secret_len, fp);
… strip trailing '\n' …
if (secret_len != 64) { ereport(ERROR, errmsg("invalid secret key")); proc_exit(1); }
```
(`supabase_vault.c:62-79`) `[verified-by-code]`. The script's existence and
`X_OK` executability are checked first with `access()`, with tailored
`ereport` messages for `ENOENT`/`EACCES` (`supabase_vault.c:45-60`)
`[verified-by-code]`. This is a deliberate inversion of the usual "secrets live
in a catalog table" model: the *root* key must come from outside the database
(an env-driven script, a KMS fetch, `cat /path/to/key`) so that a database dump
or a `SELECT` can never reveal it. Core has no such bootstrap; the closest
analog is `ssl_passphrase_command`, and Vault generalizes that idea to a
data-encryption root key. Failure aborts the postmaster (`proc_exit(1)`), so a
missing key is fatal, not degraded `[verified-by-code]`.

### 2. Key held in `sodium_malloc` locked memory — outside PG's MemoryContext system

The 32-byte key is decoded into a libsodium **guarded allocation**, not a
`palloc`'d buffer:

```
pgsodium_secret_key = sodium_malloc (crypto_sign_SECRETKEYBYTES + VARHDRSZ);
…
hex_decode (secret_buf, secret_len, VARDATA (pgsodium_secret_key));
sodium_memzero (secret_buf, secret_len);
free (secret_buf);
```
(`supabase_vault.c:87-98`) `[verified-by-code]`. `sodium_malloc` returns memory
that is `mlock`'d (never swapped to disk), flanked by inaccessible guard pages,
and canary-checked — a hardened region that lives entirely **outside PG's
`MemoryContext` hierarchy** (no context owns it, `MemoryContextReset` never
frees it, error `longjmp` cleanup does not touch it). It is allocated once in
the postmaster and, via the fork model, **inherited copy-on-write by every
backend** — so every session shares the one locked key buffer without it ever
being re-read or re-exposed. The intermediate hex buffer from the script is
scrubbed with `sodium_memzero` and freed (`:97-98`) so the plaintext key does
not linger on the C heap `[verified-by-code]`. This is a clean example of an
extension deliberately **refusing** the MemoryContext idiom
(`knowledge/idioms/memory-contexts.md`) because the resource's security
properties (locked, un-dumpable, process-lifetime) are exactly what a context
would undermine.

### 3. Transparent decryption as a plain VIEW; encryption keyed by row-id AAD

`vault.decrypted_secrets` is an ordinary view that adds one computed column,
`decrypted_secret`, by calling the pgsodium AEAD decrypt over the base64-decoded
ciphertext, with the row's `id` bound in as the **additional authenticated
data** and a fixed `key_id := 0` selecting the root-derived key:

```
convert_from(
  vault._crypto_aead_det_decrypt(
    message   := decode(s.secret, 'base64'),
    additional:= convert_to(s.id::text, 'utf8'),   -- AAD = the row id
    key_id    := 0, context := 'pgsodium', nonce := s.nonce),
  'utf8') AS decrypted_secret
```
(`supabase_vault--0.3.0.sql:32-51`) `[verified-by-code]`. Binding the row `id`
as AAD means a ciphertext copied into a different row fails authentication — the
encryption is *bound to its location*. Encryption is symmetric on write:
`create_secret` inserts plaintext then immediately `UPDATE`s the row to the
base64 of `_crypto_aead_det_encrypt(...)` with the same id-as-AAD binding
(`supabase_vault--0.3.0.sql:53-86`) `[verified-by-code]`. Because the decrypt is
a view column, "reading a secret" is a `SELECT` that transparently invokes
libsodium per row — a divergence from column encryption schemes that require an
explicit `decrypt()` call at every read site; here the *view name* is the
capability. (Access control is then a matter of granting the view, not the base
table — the base `vault.secrets` keeps only ciphertext.)

### 4. Deterministic AEAD + generated nonce, and dump-safety

The encrypt/decrypt are the pgsodium **deterministic** AEAD variants
(`pgsodium_crypto_aead_det_encrypt/decrypt_by_id`,
`supabase_vault--0.3.0.sql:1-9`), and `nonce` defaults to
`vault._crypto_aead_det_noncegen()` on insert (`:22`) `[verified-by-code]`. The
crypto functions and the secret-manipulating functions are `REVOKE ALL … FROM
PUBLIC` (`:121-127`), and `create_secret`/`update_secret` are `SECURITY DEFINER`
with `SET search_path = ''` (`:61-63`, `:97-99`) — the standard hardening so a
caller cannot hijack name resolution inside the definer context
`[verified-by-code]`. `pg_extension_config_dump('vault.secrets','')` (`:129`)
marks the (encrypted) table as user-data to include in dumps — so the ciphertext
travels with the dump while the root key (§1/§2) never does, which is the whole
at-rest-plus-in-dumps guarantee `[verified-by-code]`.

## Notable design decisions

- **`relocatable = false`, `schema = vault`** (`supabase_vault.control.in:4-5`)
  — the `vault.` namespace is load-bearing (view and function names are the API)
  `[verified-by-code]`.
- **Tiny C, big SQL** — 100 lines of C do only key bootstrap; the feature is
  ~130 lines of SQL. The C exists *only* because the key must be fetched before
  SQL runs and kept where SQL cannot reach `[verified-by-code]`.
- **`-lsodium`, `-std=c99 -Werror`** (`Makefile:1`, `SHLIB_LINK`) — links
  libsodium directly like pgsodium `[verified-by-code]`.
- **Fatal-on-missing-key** (`proc_exit(1)` on every bootstrap failure path,
  `supabase_vault.c:59,66,78,85,93`) — the server will not start without a valid
  key, a deliberate fail-closed posture `[verified-by-code]`.

## Links into corpus

- Direct dependency on `[[pgsodium]]` (the libsodium AEAD binding + the shared
  `pgsodium_secret_key` global vault populates). Vault is the "secrets table +
  view" layer; pgsodium is the crypto engine.
- The off-`MemoryContext`, process-lifetime, fork-inherited locked buffer is the
  security-motivated mirror of the *foreign-allocator* pattern in
  `[[onesparse]]` / `[[pg_duckdb]]` / `[[pglite-fusion]]` — memory PG's context
  system deliberately does not own. See `knowledge/idioms/memory-contexts.md`.
- External-program-at-startup echoes core's `ssl_passphrase_command` and the
  `popen`-a-helper pattern; contrast `[[pg_auto_failover]]` (outbound libpq at
  runtime) and `[[pgsql-http]]`/`[[pg_net]]` (outbound HTTP) — all exts reaching
  *out* of the backend, here to fetch a key rather than talk to a peer.
- SECURITY DEFINER + `search_path = ''` hardening: `knowledge/idioms/`
  security-definer / search-path notes; cf. `[[set_user]]`, `[[supautils]]`,
  `[[credcheck]]` in the privilege-control cluster.

## Sources

- `src/supabase_vault.c` → HTTP 200 (100 lines; entire `_PG_init` key-bootstrap
  path deep-read).
- `sql/supabase_vault--0.3.0.sql` → HTTP 200 (129 lines; AEAD wrappers, secrets
  table, `decrypted_secrets` view, `create_secret`/`update_secret`, REVOKE +
  `pg_extension_config_dump` — deep-read; this is the base install).
- `sql/supabase_vault--0.3.0--0.3.1.sql` → HTTP 200 (1 line; "no SQL changes in
  0.3.1" — so 0.3.0 is the current feature surface).
- `supabase_vault.control.in` → HTTP 200 (5 lines; schema/relocatable/module).
- `Makefile` → HTTP 200 (25 lines; `EXTENSION=supabase_vault`, `-lsodium`,
  control templating from `.control.in`).
- `README.md` → HTTP 200 (184 lines; encryption-at-rest framing, decrypting-view
  usage, key-not-available-to-SQL claim).

All cites `[verified-by-code]` against the fetched `.c`/`.sql`/`.control` except
the end-user "encryption at rest + in dumps" narrative and the "keys managed for
you, referred to only by id" framing (`[from-README]`), and the
`sodium_malloc` mlock/guard-page/COW-inheritance properties, which are
`[inferred]` from libsodium's documented `sodium_malloc` semantics applied to
the one call site (`supabase_vault.c:87-88`) rather than narrated by this repo.
No earlier base-version SQL was fetchable (only 0.3.0 base + the 0.3.1 no-op
migration are present at these paths on `master`).
