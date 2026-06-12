# pgsodium — a server-side key the SQL layer can never read, plus SECURITY-LABEL-driven column encryption

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `michelp/pgsodium` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-11 (see Sources footer). Crypto-primitive wrappers
> (`src/aead.c`, `src/box.c`, `src/sign.c`, …) were enumerated from the header
> but not deep-read; the architectural story lives in `pgsodium.c`, the header
> helpers, and `kdf.c`.

## Domain & purpose

pgsodium is "an encryption library extension for PostgreSQL using the libsodium
library for high level cryptographic algorithms" (`README.md:5-8`)
`[from-README]`. It has two layers. The thin layer is a near-1:1 fmgr wrapper
over libsodium — dozens of `pgsodium_crypto_*` SQL functions for secretbox,
AEAD, sign, box, KDF, pwhash, generichash, kx, signcrypt, even IP-address
encryption (`src/pgsodium.h:124-298`) `[verified-by-code]`. The architecturally
interesting layer is **Server Key Management**: pgsodium "loads an external
secret key into memory that is never accessible to SQL [and uses it] to derive
sub-keys and keypairs *by key id*. This id (type `bigint`) can then be stored
*instead of the derived key*" (`README.md:11-16`) `[from-README]`. On top of
that sits **Transparent Column Encryption (TCE)**, which "can automatically
encrypt and decrypt one or more columns of data in a table" (`README.md:18-20`),
driven entirely by `SECURITY LABEL` annotations. pgsodium is the corpus's
clearest example of an extension that deliberately puts a secret *out of reach
of the SQL surface it otherwise extends*.

## How it hooks into PG

The control file pins the extension to schema `pgsodium`, `relocatable = false`,
`default_version = '3.1.11'` (`pgsodium.control:1-5`) `[verified-by-code]`.
`_PG_init` does three things in order (`src/pgsodium.c:104-206`)
`[verified-by-code]`:

1. **`sodium_init()`** — initialize the libsodium runtime, ERROR out if it
   fails (`:114-119`).
2. **`register_label_provider("pgsodium", pgsodium_object_relabel)`** — install
   a security-label provider so the backend will route `SECURITY LABEL FOR
   pgsodium ...` statements to pgsodium's validation callback (`:122`). This is
   done *unconditionally*, even when not preloaded.
3. **If `process_shared_preload_libraries_in_progress`** only: define the
   `pgsodium.enable_event_trigger` (bool, `PGC_USERSET`) and
   `pgsodium.getkey_script` (string, `PGC_POSTMASTER`) GUCs, then **`popen()`
   the getkey script and read the root key from its stdout** (`:128-205`).

So pgsodium is a `shared_preload_libraries` module *for the key-loading path*
but degrades to a plain lazy-loaded crypto library if not preloaded (the
`return` at `:125-126` skips the whole root-key load). Cross-ref
`[[knowledge/files/contrib/sepgsql/label.c]]` (the `register_label_provider`
machinery), `[[knowledge/idioms/bgworker-and-parallel]]` (the
`PGC_POSTMASTER`/`PGC_USERSET` GUC split), and the `extension-development` skill
(preload vs lazy decision table).

## Where it diverges from core idioms

### 1. The root key is loaded from an external process via `popen()` and is never an SQL value

Core's `pgcrypto` takes keys as SQL arguments — they pass through query text,
logs, and memory like any datum. pgsodium inverts this. At postmaster start it
resolves `pgsodium.getkey_script` (default `$sharedir/extension/pgsodium_getkey`),
checks it is executable, then `popen(getkey_script, "r")` and reads exactly one
64-hex-char line as the primary server secret key (`src/pgsodium.c:137-205`)
`[verified-by-code]`. The script can fetch the key from AWS KMS, GCP, Doppler, a
hardware ZMK module, or `/dev/urandom` (`README.md:134-149`) `[from-README]`.
The key thus enters the postmaster's address space *out-of-band*, never as a SQL
literal — "an external secret key ... that is never accessible to SQL"
(`README.md:11-13`). Tying a crypto root to a forked shell command run once in
the postmaster, rather than to a SQL/GUC value, is a posture core crypto never
takes. Cross-ref `[[knowledge/idioms/error-handling]]` (the `ereport` +
`proc_exit(1)` failure ladder if the script is missing/unreadable/wrong-length).

### 2. The secret key lives in libsodium guarded memory (`sodium_malloc`), outside the MemoryContext system

The root key is not `palloc`'d. It is allocated with
`sodium_malloc(crypto_sign_SECRETKEYBYTES + VARHDRSZ)`
(`src/pgsodium.c:193-194`) `[verified-by-code]` — libsodium's hardened
allocator, which places the buffer in `mlock`'d pages flanked by guard pages and
canaries so the key can't be swapped to disk or read past. The transient hex
buffer read from the script is wiped with `sodium_memzero` and `free`d
(`:203-204`), and a `LOG` line confirms load (`:205`). Holding long-lived secret
state *entirely outside* `TopMemoryContext`/palloc — so neither a context reset
nor a leak ever exposes it — is a deliberate departure from the
`memory-contexts` idiom every other extension follows for persistent state.
Cross-ref `[[knowledge/idioms/memory-contexts]]`.

### 3. Function results carry a reset-callback that zeroes plaintext on context teardown

Even the *transient* crypto outputs get special handling. The allocator helper
`_pgsodium_zalloc_bytea` (and its `text` twin) `palloc`s the result, then
registers a `MemoryContextCallback` whose `func` is `context_cb_zero_buff` —
`sodium_memzero(ptr, size)` — via `MemoryContextRegisterResetCallback`
(`src/pgsodium.h:51-97`) `[verified-by-code]`. So when the surrounding context
is reset/deleted, the plaintext bytes of every returned `bytea` are scrubbed
before the memory is recycled, instead of being left in freed-but-unzeroed
AllocSet chunks. Core's palloc gives no such guarantee; pgsodium bolts
defense-in-depth onto the normal allocate-and-forget result path. (A code
comment `// verify where this cb fires` at `:77` flags the author's own
uncertainty about exact firing semantics.) Cross-ref
`[[knowledge/idioms/memory-contexts]]` (reset callbacks),
`[[knowledge/idioms/fmgr]]` (the `bytea` result convention this wraps).

### 4. SECURITY LABEL is repurposed as the declaration language for column encryption

pgsodium does not add DDL or catalog columns to mark encrypted fields. Instead
its label provider's relabel callback `pgsodium_object_relabel` validates a tiny
grammar layered onto core's `SECURITY LABEL` (`src/pgsodium.c:32-101`)
`[verified-by-code]`:

- On a **column** (`RelationRelationId`, `objectSubId != 0`): the label must
  start `ENCRYPT WITH` (`:55-56`), e.g.
  `SECURITY LABEL FOR pgsodium ON COLUMN private.users.secret IS 'ENCRYPT WITH
  KEY ID <uuid>'` (`README.md:393-394`) `[from-README]`.
- On a **table** (`objectSubId == 0`): must start `DECRYPT WITH VIEW` (`:46-47`).
- On a **role** (`AuthIdRelationId`): must be `ACCESS` (`:65-67`).
- Anything else: `ereport(ERROR, ERRCODE_FEATURE_NOT_SUPPORTED ...)` (`:90-95`).

The label is a *validated configuration string*, and an event trigger
(gated by `pgsodium.enable_event_trigger`) regenerates the decrypting views and
triggers when labels change. Using the security-label subsystem as a
domain-specific annotation grammar — rather than for its intended
MAC/SELinux-style purpose — is a creative reuse of a core extensibility seam; it
is what lets TCE work with zero schema changes to the protected table. Cross-ref
`[[knowledge/files/contrib/sepgsql/label.c]]`,
`[[knowledge/ideologies/uuidv47]]` (another extension that makes the *stored*
form differ from the *presented* form, there via type I/O rather than views).

### 5. Keys are addressed by id, and the API is doubled into `*_by_id` variants

Because the root key never surfaces, the entire crypto API is mirrored: a raw
form that takes key bytes, and a `*_by_id` form that takes a `bigint`/UUID key id
and derives the actual key internally (`pgsodium_crypto_secretbox_by_id`,
`..._aead_ietf_encrypt_by_id`, `..._auth_hmacsha256_by_id`, etc.,
`src/pgsodium.h:138-297`) `[verified-by-code]`. Derivation is libsodium's KDF:
`pgsodium_derive_helper` calls `crypto_kdf_derive_from_key` with the in-memory
`pgsodium_secret_key`, an 8-byte context, and the subkey id
(`src/pgsodium.h:99-120`), and `kdf.c` exposes `crypto_kdf_derive_from_key` as
SQL with strict null/size/context checks (`src/kdf.c:84-119`)
`[verified-by-code]`. The design intent: store the key *id* in your rows, never
the key, and reconstruct the key on demand from the unreachable root
(`README.md:179-208`) `[from-README]`. Maintaining two parallel API surfaces so
that callers can stay key-bytes-free is a structural consequence of decision #1.

## Notable design decisions (cited)

- **Label provider registered even when not preloaded** (`src/pgsodium.c:122`
  runs before the `process_shared_preload_libraries_in_progress` guard at
  `:125`) — `SECURITY LABEL FOR pgsodium` validation works in any backend that
  has loaded the `.so`, even if the root key was never loaded; the key load is
  the only preload-gated part.
- **Exactly 64 hex chars enforced** for the script output
  (`src/pgsodium.c:181-185`) — the root key is a 32-byte value; a wrong-length
  line is a hard ERROR + `proc_exit(1)`, failing postmaster startup rather than
  running with a malformed key.
- **`ERRORIF(B, msg)` macro** (`src/pgsodium.h:39-41`) — a house `ereport(ERROR,
  ERRCODE_DATA_EXCEPTION, errmsg(msg, __func__))` shorthand used pervasively for
  argument validation (null checks, key/context size checks) in the crypto
  wrappers, e.g. `kdf.c:95-110`.
- **Windows `getline` shim** (`src/pgsodium.c:3-21`) — a hand-rolled `getline`
  for `_WIN32` so the `popen`-based key load is portable, mirroring the
  out-of-tree portability burden seen in `[[knowledge/ideologies/wal2json]]`.
- **`relocatable = false`, `schema = pgsodium`** (`pgsodium.control:4-5`) — the
  extension's objects (the key tables, views, masking machinery) are pinned to
  one schema, which the TCE view/trigger generation relies on.

## Links into corpus

- `[[knowledge/files/contrib/sepgsql/label.c]]` — the `register_label_provider`
  + relabel-callback machinery pgsodium repurposes as the TCE declaration
  grammar; the single most important cross-reference.
- `[[knowledge/idioms/memory-contexts]]` — the two divergences from palloc: the
  root key in `sodium_malloc` guarded memory *outside* the context system, and
  the reset-callback that `sodium_memzero`s plaintext results.
- `[[knowledge/idioms/error-handling]]` — the `ereport` + `proc_exit(1)`
  startup-failure ladder around the getkey script, and the `ERRORIF` validation
  macro.
- `[[knowledge/idioms/bgworker-and-parallel]]` — `pgsodium.getkey_script`
  (`PGC_POSTMASTER`) vs `pgsodium.enable_event_trigger` (`PGC_USERSET`); the
  preload-only key-load path.
- `[[knowledge/idioms/fmgr]]` — the `bytea`-returning crypto-wrapper
  convention (`PG_RETURN_BYTEA_P`, `VARDATA`/`SET_VARSIZE`) the zeroing
  allocator wraps.
- `[[knowledge/ideologies/uuidv47]]` — sibling "stored form ≠ presented form"
  extension (façade via type I/O); pgsodium does it via SECURITY-LABEL-generated
  decrypting views instead.
- `[[knowledge/ideologies/wal2json]]` — shares the out-of-tree portability
  burden (hand-rolled `getline` / `#if` shims) of an extension tracking many
  server generations.
- `.claude/skills/extension-development/SKILL.md` — preload-vs-lazy decision
  table (pgsodium straddles it), `DefineCustomXxxVariable`, security-label
  provider registration as a hook.

## Sources

Fetched 2026-06-11 (branch `main`):

- `https://api.github.com/repos/michelp/pgsodium/git/trees/main?recursive=1`
  @ 2026-06-11 → HTTP 200 (tree listing; 121 blobs, src/ enumerated).
- `https://raw.githubusercontent.com/michelp/pgsodium/main/README.md`
  @ 2026-06-11 → HTTP 200 (1285 lines; Server Key Management + TCE +
  SECURITY-LABEL sections read).
- `https://raw.githubusercontent.com/michelp/pgsodium/main/pgsodium.control`
  @ 2026-06-11 → HTTP 200 (5 lines).
- `https://raw.githubusercontent.com/michelp/pgsodium/main/src/pgsodium.c`
  @ 2026-06-11 → HTTP 200 (206 lines; `_PG_init`, relabel callback, getkey-script
  load deep-read).
- `https://raw.githubusercontent.com/michelp/pgsodium/main/src/pgsodium.h`
  @ 2026-06-11 → HTTP 200 (299 lines; allocator+zeroing helpers, derive helper,
  full SQL-function declaration surface).
- `https://raw.githubusercontent.com/michelp/pgsodium/main/src/kdf.c`
  @ 2026-06-11 → HTTP 200 (119 lines; KDF wrappers + the create_key doctest
  header that documents key-type/by-id semantics).

All structural cites (`_PG_init` order, `register_label_provider`, getkey-script
`popen`/length-check, `sodium_malloc` key, `_pgsodium_zalloc_bytea` reset
callback, relabel grammar, `*_by_id` API doubling, KDF derive) are
`[verified-by-code]` against the fetched `.c`/`.h`/`.control`; the
never-accessible-to-SQL framing, getkey-script backends (KMS/GCP/Doppler/ZMK),
and the TCE-via-generated-views narrative are `[from-README]`
(`README.md:5-20, 134-208, 383-428`), cross-checked against the relabel callback
where present. The crypto-primitive wrapper bodies (`aead.c`, `box.c`,
`sign.c`, `secretbox.c`, `ipcrypt.c`, …) and the SQL-side TCE view/event-trigger
generation were not deep-read.
