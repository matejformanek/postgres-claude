# tstoreReceiver.c

- **Source:** `source/src/backend/executor/tstoreReceiver.c` (284 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

A `DestReceiver` that stores rows into a `Tuplestorestate` rather than
sending them to a client. Used by:
- WITH HOLD cursors (results survive across transactions),
- SPI's `SPI_execute_*` cursors,
- functions returning composite tuplestores (Materialize-mode SRF results),
- `RETURN QUERY` in plpgsql.

[from-comment] `:3-12`

## Two optional behaviors

- **Force detoasting** — when storing rows whose toasted columns live in a
  table that may be dropped before the tuplestore is consumed (WITH HOLD
  cursors over temp tables, or across xact boundaries). Toasted pointers
  would dangle; receiver expands them inline before storing.
- **Tuple-conversion map** — when the tuplestore's expected TupleDesc
  doesn't exactly match the source slot's (column reordering, dropped
  columns); the map remaps via `execute_attr_map_slot`.

## API

`CreateTuplestoreDestReceiver()` — allocate.
`SetTuplestoreDestReceiverParams(receiver, tstore, cxt, detoast, attrmap, srcDesc)`
— configure with the target Tuplestorestate, memory context for storing
data, optional detoast flag, optional map.

## Notable

Detoasting decompresses if needed but *does not* compress; that's because
compressed format is fine to keep in a tuplestore (it doesn't reference
external storage). Only EXTERNAL on-disk TOAST pointers are dangerous.

## Tags

- [verified-by-code] API + the detoast/conversion options.
- [from-comment] purpose statement.
