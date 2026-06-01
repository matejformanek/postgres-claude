# conversioncmds.c

- **Source path:** `source/src/backend/commands/conversioncmds.c`
- **Lines:** 135
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Conversion creation command support code." [from-comment, conversioncmds.c:3-4] CREATE CONVERSION registers an encoding-conversion function in pg_conversion so the backend can translate between two encodings at the client-server boundary (using `pg_do_encoding_conversion`). Tiny file.

## Public surface

- `CreateConversionCommand` — look up the named function (signature: `(integer, integer, cstring, internal, integer) → void`), record (from_encoding, to_encoding, function_oid) in pg_conversion. Optionally marks it as DEFAULT for that encoding pair.

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=1`
