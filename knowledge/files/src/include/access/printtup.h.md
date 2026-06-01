# printtup.h

- **Source path:** `source/src/include/access/printtup.h`
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `printtup.c`, `tcop/dest.c`, `tcop/pquery.c`.

## Purpose

Declares the wire-protocol DestReceiver factory `printtup_create_DR`, the `SendRowDescriptionMessage` helper used outside of printtup.c proper, and the standalone-mode debug receivers (`debugStartup` / `debugtup`). Also forward-declares `spi_dest_startup` / `spi_printtup` — those live in `executor/spi.c` but use the same DestReceiver shape. [verified-by-code, printtup.h:18-33]

## Public surface

- `printtup_create_DR(CommandDest dest)` — Create a fresh receiver for wire-protocol output.
- `SetRemoteDestReceiverParams(DestReceiver *, Portal)` — Attach to a Portal (so column format codes can be read).
- `SendRowDescriptionMessage(StringInfo, TupleDesc, List *targetlist, int16 *formats)` — Emit a `'T'` message; the targetlist provides nicer column metadata than TupleDesc alone (junk columns, expression labels).
- `debugStartup` / `debugtup` — Receivers used in standalone (`--single`) backend mode.
- `spi_dest_startup` / `spi_printtup` — Declared here for historical reasons; implemented in `executor/spi.c`.

## Cross-references

- See `knowledge/files/src/backend/access/common/printtup.c.md`.

## Confidence tag tally
`[verified-by-code]=2 [from-comment]=0 [from-readme]=0 [inferred]=0 [unverified]=0`
