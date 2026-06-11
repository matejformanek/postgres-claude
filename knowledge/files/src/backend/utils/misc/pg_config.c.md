# `src/backend/utils/misc/pg_config.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~50
- **Source:** `source/src/backend/utils/misc/pg_config.c`

Backend implementation of the `pg_config()` SQL set-returning function
(SRF). Exposes the same `name → setting` rows that the command-line
`pg_config` utility prints, but materialised through the tuplestore
SRF infrastructure. [verified-by-code]

## API

- `Datum pg_config(PG_FUNCTION_ARGS)` — registered SRF returning
  `(text, text)` tuples. Calls `InitMaterializedSRF` (the canonical
  materialize-mode setup), then `get_configdata(my_exec_path, &len)`
  from `common/config_info` to read the embedded build-time values.
  For each entry, packs `name` and `setting` as text Datums via
  `CStringGetTextDatum` and pushes a tuple into `rsinfo->setResult`.
  [verified-by-code]

## Notable invariants / details

- The function reads `my_exec_path` (set during postmaster/backend
  init from argv[0] resolution); on a misconfigured exec path the
  underlying `get_configdata` may return synthesized defaults rather
  than the real install values. [inferred]
- No ACL check inside this function — callable by PUBLIC by default
  (per `pg_proc.dat` definition; not verified here). Means any
  authenticated user can see compile-time `--with-*` flags and paths
  like LIBDIR/PKGLIBDIR/SHAREDIR. Same exposure as the CLI
  `pg_config` tool's output, intentionally so. [inferred] [ISSUE-info-disclosure:
  compile-time paths/options exposed to PUBLIC (nit)]
- `nulls[]` is zeroed but never set true — both columns are always
  non-null. The `memset(values, 0, …)` line is defensive (the loop
  writes them right after). [verified-by-code]
- Function returns `(Datum) 0` per materialize-mode SRF convention;
  the actual rows are in `rsinfo->setResult`. [verified-by-code]

## Potential issues

- File-line: pg_config.c:23-49. No per-row CHECK_FOR_INTERRUPTS, but
  `configdata_len` is tiny (~40 entries) so this is fine. [ISSUE-style:
  trivially small loop, no interrupt check warranted (nit)]
- The exposure of `CC`, `CFLAGS`, `CONFIGURE` arguments is sometimes
  used by attackers fingerprinting target PG installations. Mitigation
  would be revoking EXECUTE from PUBLIC, but doing so breaks
  monitoring tools. [inferred] [ISSUE-info-disclosure: fingerprinting
  surface for PG installations (nit)]
