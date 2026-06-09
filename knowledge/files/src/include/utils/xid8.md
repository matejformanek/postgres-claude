# utils/xid8.h — 64-bit FullTransactionId datum wrapper

Source: `source/src/include/utils/xid8.h` (32 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Datum-layer wrappers around `FullTransactionId` (defined in `access/transam.h`). xid8 is the SQL-visible 64-bit XID for safe tracking across epoch boundaries.

## Public API

- `DatumGetFullTransactionId` / `FullTransactionIdGetDatum` (`xid8.h:17-27`).
- `PG_GETARG_FULLTRANSACTIONID` / `PG_RETURN_FULLTRANSACTIONID` (`xid8.h:29-30`).

## Invariants

- **INV-xid8-pass-by-value-on-64bit** [inferred from FullTransactionId being uint64]: pass-by-value on 64-bit platforms; pass-by-ref via Datum-as-int64 on 32-bit.
- **INV-xid8-no-epoch-loss** [inferred from naming]: vs `xid` (32-bit, wraps), `xid8` includes the epoch — appropriate for monitoring/replication tracking.

## Cross-refs

- `source/src/include/access/transam.h` — `FullTransactionId`, `FullTransactionIdFromU64`, `U64FromFullTransactionId`.

## Issues

- None — header is a thin datum bridge.
