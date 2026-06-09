# utils/bytea.h — BYTEA output-format GUC

Source: `source/src/include/utils/bytea.h` (28 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Tiny header. Declares the `bytea_output` GUC enum (escape vs hex). The actual BYTEA varlena format is just a generic varlena (`bytea` = `varlena` in c.h).

## Public API

- `ByteaOutputType` enum: `BYTEA_OUTPUT_ESCAPE`, `BYTEA_OUTPUT_HEX` (`bytea.h:19-23`).
- `extern int bytea_output;` (`bytea.h:25`) — GUC, declared `int` for the GUC enum machinery, cast to `ByteaOutputType` at use sites.

## Invariants

- **INV-bytea-output-default-hex** [from-config, not visible here]: default since 9.0 is hex. Confirmed in `guc_tables.c`. Header doesn't say.
- **INV-bytea-storage-is-varlena** [inferred]: BYTEA on disk is a plain varlena; no extra header beyond `vl_len_`. There is no `bytea_struct`; just `varlena`.

## Trust-boundary / Phase-D surface

- **bytea_recv** [inferred — not in this header]: just copies the binary payload as-is — no encoding interpretation. The only Phase-D concern is varlena size validation (handled by generic varlena recv path).

## Cross-refs

- `source/src/backend/utils/adt/varlena.c` — bytea_in/out/recv/send implementations.
- c.h — `typedef struct varlena bytea` alias.

## Issues

- None — this header is intentionally minimal.
