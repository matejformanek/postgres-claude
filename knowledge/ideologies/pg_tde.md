# pg_tde — whole-cluster Transparent Data Encryption by *replacing the storage manager*, not extending SQL

> Extension: `percona/pg_tde` @ `main` (control reports `default_version = '2.2'`,
> `module_pathname = '$libdir/pg_tde'`, `relocatable = false`, comment
> `'pg_tde access method'`) `[verified-by-code: pg_tde.control:1-4]`. 214★, C.
> One durable "how this diverges from core PG design" doc. Line cites are into
> the upstream pg_tde tree (`src/smgr/pg_tde_smgr.c`,
> `src/access/pg_tde_xlog_smgr.c`, `src/access/pg_tde_xlog.c`, `src/pg_tde.c`,
> `src/catalog/tde_principal_key.c`, `src/keyring/keyring_api.c`,
> `src/encryption/enc_aes.c`), **NOT** into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** the crypto twin in the corpus is
> [[knowledge/ideologies/pgsodium]] — but the two sit at *opposite* layers.
> pgsodium is **column-level**, SQL-visible crypto (libsodium wrappers +
> SECURITY-LABEL-driven view rewriting; the user calls encrypt/decrypt or labels
> a column). pg_tde is **whole-cluster at-rest** crypto that operates entirely
> *below* the SQL layer: it intercepts the storage manager (`md.c`) and the WAL
> writer so that pages and WAL are ciphertext on disk and plaintext in shared
> buffers, with no change to query semantics. Read this doc against pgsodium's;
> the layer contrast is the payload.

## Domain & purpose

pg_tde is Percona's Transparent Data Encryption for PostgreSQL: it encrypts
relation data files and (optionally) the WAL stream **at rest**, transparently,
so that the on-disk bytes are AES ciphertext while every page in shared buffers
stays plaintext. The design intent is that encryption sits at the lowest
possible layer — the single-magnetic-disk (`smgr`) boundary — so the executor,
planner, heap AM, MVCC, and the buffer manager are all oblivious to it. A
relation is encrypted with a per-relation **internal key**; that internal key is
itself wrapped/derived under a per-database (or global/server) **principal key**;
and the principal key never lives in the data directory — it is fetched at use
time from an external **key provider** (a local file, HashiCorp Vault, or a
KMIP server) `[verified-by-code: src/include/keyring/keyring_api.h:10-16;
from-README]`. The control file literally calls it an "access method" and the
extension also ships a thin table-AM handler (`pg_tdeam_handler` returning the
core heap AM routine) `[verified-by-code: pg_tde.control:1; src/pg_tde.c:250-254]`,
but the real machinery is the smgr replacement, not the table AM.

## How it hooks into PG

- **It is `shared_preload_libraries`-only, and says so by FATAL.** `_PG_init`
  errors out with `elog(FATAL, "pg_tde can only be loaded at server startup")`
  if `!process_shared_preload_libraries_in_progress` — the comment explains FATAL
  (not ERROR) is chosen so `pg_restore`/psql can't continue and silently create
  *unencrypted* tables `[verified-by-code: src/pg_tde.c:100-110]`.

- **It registers a whole storage manager via `smgr_register`.** Unlike a
  hook-chaining extension, pg_tde installs a full `f_smgr` vtable named `"tde"`
  and *takes over* the global `storage_manager_id`, refusing to load if another
  smgr was registered first `[verified-by-code: src/smgr/pg_tde_smgr.c:599-641]`.

- **A custom resource manager (rmgr) for key WAL.** `RegisterCustomRmgr(RM_TDERMGR_ID,
  &tdeheap_rmgr)` registers an rmgr named `"pg_tde"` with redo/desc/identify
  callbacks handling seven op codes (create/delete relation key, add/rotate/delete
  principal key, write key provider, install extension)
  `[verified-by-code: src/access/pg_tde_xlog.c:28-39, 41-95, 146-167]`.

- **A custom XLog storage manager for WAL encryption.** `SetXLogSmgr(&tde_xlog_smgr)`
  installs `seg_read`/`seg_write` hooks (`XLogSmgr`) that en/decrypt WAL segment
  bytes on the way to/from disk `[verified-by-code: src/access/pg_tde_xlog_smgr.c:40-43,
  221-225]`.

- **`shmem_request_hook` / `shmem_startup_hook` chaining** reserve shared memory
  for the principal-key DSA/dshash cache, the smgr AIO-key array, and the WAL
  encryption state + buffer, plus a named LWLock tranche `TDE_TRANCHE_NAME` with
  `TDE_LWLOCK_COUNT` locks `[verified-by-code: src/pg_tde.c:60-95;
  src/include/pg_tde.h:10, 23-30]`.

- **GUCs under `pg_tde.*`.** `pg_tde.wal_encrypt` (bool, `PGC_POSTMASTER`),
  `pg_tde.enforce_encryption` (bool, `PGC_SUSET`), `pg_tde.inherit_global_providers`
  (bool, `PGC_SUSET`), `pg_tde.cipher` (enum AES-128/256, `PGC_SUSET`, whose
  assign hook sets the global `KeyLength`)
  `[verified-by-code: src/pg_tde_guc.c:14-17, 35-77]`.

- **Three key-provider implementations registered at init.** `InstallFileKeyring()`,
  `InstallVaultV2Keyring()`, `InstallKmipKeyring()` each `RegisterKeyProviderType`
  a `TDEKeyringRoutine` vtable (`keyring_get_key`/`keyring_store_key`/`keyring_validate`)
  `[verified-by-code: src/pg_tde.c:118-120; src/keyring/keyring_api.c:69-80;
  src/include/keyring/keyring_api.h:50-55, 84]`.

- **It owns an on-disk directory `pg_tde/` next to the data files**, created at
  init, holding the per-relation `*_keys` files and a `keys_version` file used for
  format migration `[verified-by-code: src/include/pg_tde.h:8;
  src/pg_tde.c:42-48, 162-241]`.

## Where it diverges from core idioms

1. **It replaces the storage manager wholesale and shadows `md.c`'s private
   struct.** Core PG has exactly one production smgr (magnetic disk, `md.c`) and
   `smgr.c` was only recently made pluggable. pg_tde defines `TDESMgrRelation`
   whose *first fields are a byte-for-byte copy of `md.c`'s private
   `MDSMgrRelationData`* (`SMgrRelationData reln`, then the `md_num_open_segs[]`
   and `md_seg_fds[]` per-fork arrays) so that it can pass its own struct
   straight into the unmodified `md*` functions, then appends its own
   `encryption_status` + `InternalKey relKey`
   `[verified-by-code: src/smgr/pg_tde_smgr.c:37-59]`. The vtable delegates the
   non-crypto operations (`smgr_nblocks = mdnblocks`, `smgr_truncate = mdtruncate`,
   `smgr_init = mdinit`, …) directly to `md.c` and only wraps the read/write/extend/
   create/unlink/open/close paths `[verified-by-code: src/smgr/pg_tde_smgr.c:599-628]`.
   This "subclass md.c by struct-prefix aliasing" is a layering trick core itself
   never performs — it is intimate coupling to `md.c`'s undocumented private
   layout, guarded only by a hand-maintained comment that the fields "must always
   exactly match" `[verified-by-code: src/smgr/pg_tde_smgr.c:37-44]`.

2. **Encryption happens on the write path with an out-of-place ciphertext copy;
   decryption is in-place on read.** `tde_mdwritev` (PG ≥ 17) palloc's an
   IO-aligned scratch buffer (`palloc_aligned(BLCKSZ * nblocks, PG_IO_ALIGN_SIZE,
   0)`), encrypts each page into it via `tde_encrypt_smgr_block`, then hands the
   *ciphertext* buffers to `mdwritev` — never mutating the shared-buffer page that
   the buffer manager still owns `[verified-by-code: src/smgr/pg_tde_smgr.c:245-277]`.
   `tde_mdreadv` instead calls `mdreadv` first and decrypts each block in place
   (`buf, buf`) after the read `[verified-by-code: src/smgr/pg_tde_smgr.c:360-380]`.
   The out-of-place write is mandatory: the page is still pinned/plaintext in
   shared buffers and may be read concurrently, so the cipher must not touch it.
   Core's `md.c` does no such copy. `tde_mdextend` does the same single-block
   copy-and-encrypt `[verified-by-code: src/smgr/pg_tde_smgr.c:334-356]`.

3. **For PG 18 async IO it smuggles the relation key through shared memory keyed
   by IO-handle id.** Under `io_method=worker`, the backend that *issues* a read
   is not the process that *completes* it, so the completing process must decrypt
   without access to the issuer's key cache. pg_tde allocates a shmem array
   `tde_io_handle_keys` sized at one `InternalKey` per possible IO handle
   (`(MaxBackends + NUM_AUXILIARY_PROCS) * io_max_concurrency`), and
   `tde_mdstartreadv` copies the resolved key into the slot indexed by
   `pgaio_io_get_id(ioh)` before registering a completion callback
   `tde_readv_complete` that decrypts in `complete_shared`
   `[verified-by-code: src/smgr/pg_tde_smgr.c:475-586]`. Putting *plaintext key
   material in main shared memory* (not guarded/locked memory) to bridge the AIO
   issuer/completer split is a sharp departure from how core treats secrets, and
   from pgsodium's `sodium_malloc` guarded-page posture
   ([[knowledge/ideologies/pgsodium]] divergence #2) — here it is justified only
   by "no more wasteful than the allocation of IO handles itself"
   `[from-comment: src/smgr/pg_tde_smgr.c:482-488]`.

4. **A second, independent encryption layer for WAL via a custom `XLogSmgr`,
   with key-by-LSN-range bookkeeping.** WAL is not covered by the relation smgr,
   so pg_tde installs `SetXLogSmgr` hooks. The crux of the design is the
   `WalEncryptionRange`: WAL keys are not per-segment but per **[start LSN/TLI,
   end LSN/TLI) range**, and `TDEXLogCryptBuffer` walks a linked list of cached
   ranges, computing the overlap between each key's LSN range and the buffer being
   read/written, then en/decrypting only the overlapping byte sub-window — with
   special handling for keys that span multiple timelines
   `[verified-by-code: src/access/pg_tde_xlog_smgr.c:466-604]`. Core's WAL has no
   notion of an encryption key at all; this whole range-overlap machinery is novel
   bookkeeping bolted under `XLogWrite`.

5. **A fresh WAL key is generated on every server start, by cryptographic
   necessity.** Because WAL is encrypted with AES in a CTR-like stream mode, two
   divergent copies of the same cluster reusing the same key+IV would leak
   plaintext via XOR. `TDEXLogSmgrInitWrite` therefore *always* creates a new WAL
   range/key on startup when encryption is on, explicitly "to protect against
   attacks on CTR ciphers based on comparing the WAL generated by two divergent
   copies" `[verified-by-code: src/access/pg_tde_xlog_smgr.c:234-257; from-comment
   :249-253]`. This start-time key churn has no analog in core and is the root of
   the LSN-range key model in #4.

6. **CTR-mode crypto is re-implemented on top of AES-ECB for random-access
   seekability.** The author's note explains that real AES-CTR via OpenSSL
   requires re-initializing the cipher context on every seek (a costly op), which
   is unacceptable for an 8 KiB page that can be read at any offset. So pg_tde
   keeps one long-lived ECB context per key, encrypts the *counter/position*
   blocks, and XORs them with data — hand-rolling CTR for two-orders-of-magnitude
   faster random access `[verified-by-code: src/encryption/enc_aes.c:12-33,
   76-90]`. `pg_tde_stream_crypt` batches this in 200-block chunks
   `[verified-by-code: src/encryption/enc_tde.c:13-15, 75-98]`. Rolling your own
   CTR is exactly the kind of thing core crypto (`pgcrypto`) never does
   ([[knowledge/subsystems/contrib-pgcrypto]] uses OpenSSL's modes directly);
   pg_tde does it for the seek-performance reason, and pays for it with a
   delicate IV-prefix computation done in 128-bit integer arithmetic
   (`CalcXLogPageIVPrefix`, with a `__int128` union and explicit endianness
   handling and a "vectorizes poorly" TODO)
   `[verified-by-code: src/access/pg_tde_xlog_smgr.c:606-649]`.

7. **A three-level key hierarchy with the root key kept out of the data
   directory.** Core has no key hierarchy. pg_tde has: (a) **internal/relation
   keys** — one random `InternalKey` (key + base IV) per relation, generated with
   `RAND_bytes`, stored in the `pg_tde/` `*_keys` files
   `[verified-by-code: src/encryption/enc_tde.c:45-68; src/smgr/pg_tde_smgr.c:101-117]`;
   (b) **principal keys** — per-database (or `GLOBAL_DATA_TDE_OID` server-wide),
   cached in shared memory via a **DSA-backed dshash** keyed by database OID, which
   wrap/protect the internal keys
   `[verified-by-code: src/catalog/tde_principal_key.c:52-74, 103-120]`; (c) the
   actual principal-key *bytes* live only in the external **key provider** and are
   fetched on demand, never written to `pg_tde/`
   `[verified-by-code: src/include/keyring/keyring_api.h:50-55, 84-88; from-README]`.
   This mirrors pgsodium's "key id, not key bytes, in your rows" intent
   ([[knowledge/ideologies/pgsodium]] divergence #5) but pushes it down to the
   storage layer and adds the provider indirection.

8. **Key providers are a pluggable vtable, including a *frontend* build.** The
   `TDEKeyringRoutine` is a function-pointer struct registered per `ProviderType`
   (FILE / VAULT_V2 / KMIP) `[verified-by-code: src/include/keyring/keyring_api.h:50-55,
   10-16]`. Crucially, the whole keyring + crypto stack is compiled **both for the
   backend and for frontend tools** (`#ifdef FRONTEND` branches throughout —
   e.g. `keyring_api.c` swaps `List` for `SimplePtrList`, and `pg_tde_xlog_smgr.c`
   swaps atomics+shmem for a plain static struct)
   `[verified-by-code: src/keyring/keyring_api.c:12-15, 23-27, 50-67;
   src/access/pg_tde_xlog_smgr.c:5-9, 67-219]`. This dual-target compilation
   exists because pg_tde ships its own forks of `pg_basebackup`, `pg_rewind`,
   `pg_waldump`, `pg_checksums`, `pg_resetwal` under `fetools/pg{16,17,18}/` plus
   `src/bin/` tools that must decrypt WAL/pages outside a running server
   `[verified-by-code: tree: fetools/, src/bin/]`. Vendoring per-major-version
   copies of core frontend source is a maintenance posture no in-tree extension
   takes.

9. **Encryption decisions are made at `smgr_create` time and pivot on a
   per-session "encrypt mode", explicitly skipping catalog relations.**
   `tde_mdcreate` decides whether the new relation gets a key by calling
   `tde_smgr_should_encrypt`, which (a) hard-refuses to encrypt catalog relations
   (`IsCatalogRelationOid`), (b) consults `currentTdeEncryptModeValidated()`
   (PLAIN / ENCRYPT / RETAIN), and (c) in RETAIN mode inherits the old relation's
   status across a rewrite `[verified-by-code: src/smgr/pg_tde_smgr.c:171-197,
   402-456]`. It also defends against OID reuse after a crash by deleting
   "leftover" keys for a relfilenode now being created unencrypted
   `[verified-by-code: src/smgr/pg_tde_smgr.c:137-151, 435-449]`. The catalog
   carve-out is a structural limitation (system catalogs are never encrypted) that
   a column-level scheme like pgsodium does not face.

10. **Operations on smgr paths run "post-commit", so they are forbidden from
    throwing.** Both `tde_mdunlink` and `tde_mdopen` carry comments that the
    transaction "might already be committed when this function is called, so do
    not call any code that uses `ereport(ERROR)`"
    `[verified-by-code: src/smgr/pg_tde_smgr.c:307-332, 458-473]`. Key deletion on
    unlink therefore happens after `mdunlink`, gated on `MAIN_FORKNUM`, with no
    error path. This no-throw discipline at the smgr boundary is inherited from
    `md.c`'s own constraints but is unusually load-bearing here because pg_tde is
    doing key *file* mutation (not just data unlink) in that window.

11. **Per-relation key creation is WAL-logged through pg_tde's *own* rmgr, not
    core's.** When a real (non-temp) relation key is created, `tde_smgr_create_key`
    both writes the key file and emits an `XLOG_TDE_CREATE_RELATION_KEY` record via
    `XLogInsert(RM_TDERMGR_ID, …)`, whose redo handler regenerates/saves the key on
    the standby `[verified-by-code: src/smgr/pg_tde_smgr.c:81-117, 119-126;
    src/access/pg_tde_xlog.c:46-51]`. Temp-relation keys, by contrast, live only in
    a backend-local `HTAB` (`TempRelKeys`) and are never WAL-logged
    `[verified-by-code: src/smgr/pg_tde_smgr.c:61-79, 663-721]`. So pg_tde
    introduces a parallel, key-specific WAL+redo pipeline alongside core's, and a
    temp/permanent split in where keys live.

## Notable design decisions (with cites)

- **Takes over the *single* smgr slot and refuses to coexist.** `RegisterStorageMgr`
  FATALs if `storage_manager_id != MdSMgrId` at load — pg_tde assumes it is the
  one and only smgr wrapper `[verified-by-code: src/smgr/pg_tde_smgr.c:630-636]`.
- **Version-stamped on-disk key formats with an auto-migration step.** A
  `keys_version` file records `PG_TDE_SMGR_FILE_MAGIC` / `PG_TDE_WAL_KEY_FILE_MAGIC`
  (magic words "TDE"/"WEK" with the high byte as a format version); at
  `shmem_startup` `pg_tde_migrate_internal_keys` rewrites the `*_keys` files if the
  stamps don't match `[verified-by-code: src/include/pg_tde.h:12-21;
  src/pg_tde.c:162-241]`.
- **128- vs 256-bit AES selected by a single GUC + assign hook.** `pg_tde.cipher`
  sets the global `KeyLength` (`KEY_DATA_SIZE_128` default) consumed everywhere a
  key is generated `[verified-by-code: src/pg_tde_guc.c:14-17, 28-29, 71-77;
  src/encryption/enc_tde.c:29-43]`.
- **The WAL encryption state uses lock-free atomics with an explicit write/read
  barrier ordering between TLI and LSN.** `TDEXLogSetEncKeyLocation` writes TLI,
  `pg_write_barrier()`, then LSN; readers do the inverse with `pg_read_barrier()`,
  so a valid TLI is always observed after a valid LSN
  `[verified-by-code: src/access/pg_tde_xlog_smgr.c:69-107, 483-489]`. The WAL
  encryption buffer is sized at startup and is forbidden from reallocation inside
  the WAL write critical section `[verified-by-code: src/access/pg_tde_xlog_smgr.c
  :150-184; from-comment:150-159]`.
- **The principal-key cache is a DSA area created in the postmaster** precisely
  because DSM allocations can't happen that early; only an initial 256 KiB is
  reserved up front and the dshash grows from DSM on demand
  `[verified-by-code: src/catalog/tde_principal_key.c:103-120, 122-140]`.
- **A single global `EVP_CIPHER_CTX` per CBC key reused across calls** (the AES
  contexts are file-static and initialized once in `AesInit`)
  `[verified-by-code: src/encryption/enc_aes.c:41-74]`.

## Links into corpus

- **Crypto sibling (contrast — opposite layer):**
  [[knowledge/ideologies/pgsodium]] — column-level, SQL-visible libsodium crypto
  driven by SECURITY LABEL; pg_tde is whole-cluster at-rest crypto below the SQL
  layer. Contrasts: `sodium_malloc` guarded key memory vs pg_tde's plaintext key
  in main shmem for AIO (#3); key-id-in-rows vs key-id-in-key-file (#7); no smgr
  involvement vs total smgr replacement (#1).
- Storage manager seam: the core analog is `src/backend/storage/smgr/md.c` +
  `smgr.c` (`f_smgr` vtable, `smgr_register`); pg_tde subclasses `md.c` by
  struct-prefix aliasing. See [[knowledge/subsystems/storage-buffer]] for the
  buffer/smgr boundary the encrypt-on-write copy respects.
- WAL / XLog: core analog is `src/backend/access/transam/xlog.c` (the `XLogSmgr`
  `seg_read`/`seg_write` seam) and `xloginsert.c`. See
  [[knowledge/idioms/wal-record-construction]], [[knowledge/idioms/wal-page-write-flush]],
  and [[knowledge/subsystems/access-transam]] for the WAL write path pg_tde wraps;
  [[knowledge/idioms/xlog-region-replay]] for the redo model its custom rmgr plugs
  into.
- Custom resource manager: [[knowledge/idioms/wal-record-construction]] and the
  `RegisterCustomRmgr` mechanism (core `src/backend/access/transam/rmgr.c`).
- Shared memory + locking: [[knowledge/idioms/lwlock-rank-discipline]],
  [[knowledge/subsystems/storage-ipc]] — the `shmem_request`/`shmem_startup`
  hooks, the `TDE_TRANCHE_NAME` LWLock tranche, the DSA/dshash principal-key cache,
  and the lock-free atomics for WAL key state. [[knowledge/idioms/spinlock-discipline]]
  for the no-alloc-in-crit-section constraint on the WAL encrypt buffer.
- GUCs: [[knowledge/idioms/guc-variables]] — `DefineCustomBoolVariable` /
  `DefineCustomEnumVariable`, the `PGC_POSTMASTER` (`wal_encrypt`) vs `PGC_SUSET`
  (`cipher`/`enforce_encryption`) split.
- Extension load model: [[knowledge/idioms/process-utility-hook-chain]] and the
  `extension-development` / `bgworker-and-extensions` skills — the
  preload-only-or-FATAL load posture (sharper than pgsodium's degrade-to-lazy).
- Catalog: [[knowledge/idioms/catalog-conventions]] — pg_tde adds no system
  catalog columns; its "catalog" is the `pg_tde/` directory of key files plus
  user-facing functions, and it explicitly *excludes* `IsCatalogRelationOid`
  relations from encryption.
- Crypto contrast: [[knowledge/subsystems/contrib-pgcrypto]] — uses OpenSSL
  cipher modes directly; pg_tde re-implements CTR over ECB for seekability (#6).

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/percona/pg_tde/git/trees/main?recursive=1 | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/pg_tde.control | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/smgr/pg_tde_smgr.c | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/pg_tde.c | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/access/pg_tde_xlog_smgr.c | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/access/pg_tde_xlog.c | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/catalog/tde_principal_key.c | 200 (head, lines 1-140) |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/encryption/enc_aes.c | 200 (head, lines 1-90) |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/encryption/enc_tde.c | 200 (head, lines 1-120) |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/keyring/keyring_api.c | 200 (head, lines 1-80) |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/include/keyring/keyring_api.h | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/include/pg_tde.h | 200 |
| https://raw.githubusercontent.com/percona/pg_tde/main/src/pg_tde_guc.c | 200 (grep slice) |

**Fetch notes / substitutions:**
- The manifest guess was directionally right but the real layout splits the
  storage/WAL/key/keyring code across `src/smgr/`, `src/access/`,
  `src/catalog/`, `src/encryption/`, `src/keyring/`, and `src/include/…` — all
  resolved against the tree API before fetching. No path 404'd.
- The control file is `pg_tde.control` at repo root (not a `*.control.in`);
  `default_version = '2.2'` there, while `src/include/pg_tde.h` independently
  defines `PG_TDE_VERSION "2.2.0"` `[verified-by-code: pg_tde.control:2;
  src/include/pg_tde.h:5]`.
- Several large files were read **head-only** (`tde_principal_key.c`,
  `enc_aes.c`, `enc_tde.c`, `keyring_api.c`) — enough to verify the key-hierarchy,
  CTR-over-ECB, stream-crypt batching, and provider-vtable claims; the deeper
  bodies (full principal-key rotation logic, the Vault/KMIP HTTP/`libkmip`
  transport code, `tde_keyring_parse_opts.c`) were **not** deep-read and are not
  cited here.
- `src/libkmip/` is a vendored submodule (KMIP transport) and was not fetched;
  the KMIP provider is characterized only via its registration and the
  `KmipKeyring` struct in `keyring_api.h`.
- The test surface (`t/*.pl`, `sql/`, `expected/`) and the `fetools/`
  per-major-version frontend forks were enumerated from the tree (used to support
  divergence #8) but their contents were not fetched.
