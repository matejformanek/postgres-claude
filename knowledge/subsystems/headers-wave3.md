# Headers skim — wave 3 (libpq / port / foreign / jit / partitioning)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Peter Eisentraut (26), Nathan Bossart (23), Thomas Munro (14), Tom Lane (13)
- **Top reviewers (last 24mo):** Tom Lane (19), John Naylor (13), Andres Freund (10), Chao Li (10)
- **Recent landmark commits (12mo):**
  - `112faf1378e (Fujii Masao, 2025-07-22): Log remote NOTICE, WARNING, and similar messages using ereport().`
  - `fbc57f2bc2e (John Naylor, 2026-04-04): Compute CRC32C on ARM using the Crypto Extension where available`
  - `7d8f5957792 (Tom Lane, 2025-07-25): Create infrastructure to reliably prevent leakage of PGresults.`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Purpose:** one-paragraph inventory of every header read while
  documenting the six wave-3 subsystems, so future sessions can
  jump straight to the right struct/typedef.

## `src/include/libpq/`

- **`libpq.h`** — defines `PQcommMethods` vtable, `pq_*` macros that
  call through it, `PQ_SMALL_MESSAGE_LIMIT=10000` /
  `PQ_LARGE_MESSAGE_LIMIT`, declares `FeBeWaitSet` positions
  (`FeBeWaitSetSocketPos=0`, `…LatchPos=1`, `…NEvents=3`), prototypes
  for `pq_init` / `pq_getmessage` / `pq_putmessage_v2` /
  `pq_check_connection` and the `secure_*` API. Also declares the
  `HostsFileLoadResult` enum and the SSL GUC `extern char *`
  declarations. **Spine header for the subsystem.**
- **`libpq-be.h`** — `Port` struct (lines 128-241), `ClientConnectionInfo`
  (86-106), `pg_gssinfo` (61-74), `ClientSocket` (248-252), and the
  full `be_tls_*` API (287-339) that any TLS backend must
  implement. **Contains the 2048-bit hardcoded DH params** as a
  static string (`FILE_DH2048`, lines 265-273).
- **`libpq-fs.h`** — 23 lines. Just `INV_WRITE=0x00020000` and
  `INV_READ=0x00040000`, the mode flags for `lo_open`.
- **`auth.h`** — `PG_MAX_AUTH_TOKEN_LENGTH=65535` (matches
  Microsoft's PAC limit per the comment), externs for
  `pg_krb_server_keyfile`, `pg_krb_caseins_users`,
  `pg_gss_accept_delegation`. Hook declarations:
  `ClientAuthentication_hook_type`, `auth_password_hook_typ`
  (`ldap_password_hook`).
- **`hba.h`** — the `UserAuth` enum (kept in sync with
  `UserAuthName[]` in `hba.c`), `IPCompareMethod`, `ConnType`,
  `ClientCertMode`/`Name`, `AuthToken`, the big `HbaLine` flat
  struct, `IdentLine`, `HostsLine`, `TokenizedAuthLine`. Prototypes
  `load_hba`, `load_ident`, `check_usermap`,
  `parse_hba_line`/`parse_ident_line`, the tokenizer
  (`open_auth_file`, `tokenize_auth_file`, `free_auth_file`).
- **`pqcomm.h`** — protocol-level constants used by both backend
  and frontend (read top only; body of `SockAddr` typedef etc. not
  walked). Includes `libpq/protocol.h`.
- **`pqformat.h`** — declarations only: `pq_beginmessage`,
  `pq_sendbyte/int/float/text/string`, `pq_getmsg*`. Top
  comment names every function ([from-comment]
  `pqformat.h:1-12`).
- **`pqmq.h`** — three externs: `pq_redirect_to_shm_mq`,
  `pq_set_parallel_leader`, `pq_parse_errornotice`.
- **`pqsignal.h`** — `BlockSig`, `UnBlockSig`, `StartupBlockSig`
  globals; `pqinitmask` proto; Win32 sigaction emulation.
- **`sasl.h`** — `pg_be_sasl_mech` struct (callbacks
  `get_mechanisms`, `init`, `exchange`) plus the
  `PG_SASL_EXCHANGE_*` return codes (`SUCCESS`, `CONTINUE`,
  `FAILURE`, `ABANDONED`). 127 lines, not fully read.
- **`scram.h`** — externs for `pg_be_scram_mech` (the
  `pg_be_sasl_mech` instance), `pg_be_scram_build_secret`,
  `parse_scram_secret`, `scram_verify_plain_password`,
  `scram_sha_256_iterations`.
- **`crypt.h`** — `MAX_ENCRYPTED_PASSWORD_LEN`, `PasswordType` enum,
  prototypes for `get_role_password`, `encrypt_password`,
  `get_password_type`, `md5_crypt_verify`, `plain_crypt_verify`.
- **`be-fsstubs.h`** — `lo_read` / `lo_write` (non-fmgr callable
  C entry points), `AtEOXact_LargeObject`,
  `AtEOSubXact_LargeObject`.

## `src/include/port/`

- **`atomics.h`** — top of the per-arch dispatch tree. Selects
  `port/atomics/arch-{arm,x86,ppc}.h` then `generic-{gcc,msvc}.h`
  then `fallback.h`. Declares the public `pg_atomic_*` API. Forbids
  frontend inclusion (`#ifdef FRONTEND #error`).
- **`port/atomics/arch-arm.h`** — ARM-specific overrides.
- **`port/atomics/arch-x86.h`** — x86/x86_64 inline-asm spinlock,
  memory-barrier defs.
- **`port/atomics/arch-ppc.h`** — PPC overrides.
- **`port/atomics/generic.h`** — high-level helpers built on
  primitives.
- **`port/atomics/generic-gcc.h`** — uses `__atomic_*` / `__sync_*`
  builtins for the bulk of impls.
- **`port/atomics/generic-msvc.h`** — MSVC intrinsics.
- **`port/atomics/fallback.h`** — spinlock-based emulation of last
  resort.

(All atomics headers skimmed only for purpose; precise impls not
verified.)

## `src/include/foreign/`

- **`foreign.h`** — `ForeignDataWrapper`, `ForeignServer`,
  `UserMapping`, `ForeignTable` structs, `FSV_MISSING_OK` /
  `FDW_MISSING_OK` flags, accessor protos. `MappingUserName`
  macro returns `"public"` for `InvalidOid` userids.
- **`fdwapi.h`** — every FDW callback typedef and the big
  `FdwRoutine` struct (lines 208-286). Read in full as part of
  the FDW subsystem doc.

## `src/include/jit/`

- **`jit.h`** — `PGJIT_*` flag bits, `JitInstrumentation`,
  `SharedJitInstrumentation`, `JitContext`, `JitProviderCallbacks`,
  JIT GUC externs, public `jit_reset_after_error`,
  `jit_release_context`, `jit_compile_expr`, `InstrJitAgg`.
- **`llvmjit.h`** — `LLVMJitContext` (extends `JitContext`), all
  `LLVMTypeRef`/`LLVMValueRef` globals populated from
  `llvmjit_types.c` bitcode, the LLVM-specific entry points
  (`llvm_create_context`, `llvm_mutable_module`,
  `llvm_get_function`, `llvm_inline`, `llvm_compile_expr`,
  `slot_compile_deform`). Includes the C++/C bridge with
  `extern "C"` for cpluspluscheck.

## `src/include/partitioning/`

- **`partbounds.h`** — `PartitionBoundInfoData` (the canonical
  bound representation); `partition_bound_accepts_nulls(bi)` and
  `partition_bound_has_default(bi)` macros; protos for
  `partition_bounds_create`/`_equal`/`_copy`/`_merge`,
  `partitions_are_ordered`, `check_new_partition_bound`,
  `check_default_partition_contents`, the three bsearches
  (`partition_list_bsearch`, `partition_range_datum_bsearch`,
  `partition_hash_bsearch`),
  `check_partitions_for_split`,
  `calculate_partition_bound_for_merge`.
- **`partprune.h`** — `PartitionPruneContext` (the runtime pruning
  state), `PruneCxtStateIdx(partnatts, step_id, keyno)` index macro,
  three entry points: `make_partition_pruneinfo`,
  `prune_append_rel_partitions`, `get_matching_partitions`.
- **`partdesc.h`** — `PartitionDescData` (with
  `last_found_datum_index` / `last_found_part_index` /
  `last_found_count` streak cache),
  `RelationGetPartitionDesc`, the `PartitionDirectory` API
  (`CreatePartitionDirectory`, `PartitionDirectoryLookup`,
  `DestroyPartitionDirectory`), `get_default_oid_from_partdesc`.
- **`partdefs.h`** — (not opened in this pass; holds the small
  shared typedefs `PartitionBoundInfo`, `PartitionDesc`,
  `PartitionDirectory` used by sibling headers to break include
  cycles).
