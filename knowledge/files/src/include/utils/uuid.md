# utils/uuid.h — UUID type (16 raw bytes)

Source: `source/src/include/utils/uuid.h` (42 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Trivial pass-by-reference fixed-length 16-byte type. `pg_uuid_t` rather than `uuid_t` to avoid clashing with libuuid system header.

## Public API

- `UUID_LEN = 16` (`uuid.h:18`).
- `struct pg_uuid_t { unsigned char data[16]; }` (`uuid.h:20-23`).
- `DatumGetUUIDP` / `UUIDPGetDatum` / `PG_GETARG_UUID_P` / `PG_RETURN_UUID_P` (`uuid.h:26-40`).

## Invariants

- **INV-uuid-len=16** [verified-by-code, `uuid.h:18`]: hardcoded; matches RFC 4122.
- **INV-uuid-typname-pg_uuid_t** [from-comment, `uuid.h:4-6`]: deliberate rename to avoid libuuid `uuid_t` collision on systems where it's a system typedef.
- **INV-uuid-no-version-validation-at-type-level** [inferred]: the type stores raw 16 bytes; v1/v4/v7 version distinctions are interpretive, not enforced. Any 16 bytes accept-able as input.

## Trust-boundary / Phase-D surface

- **uuid_recv** [inferred — not in this header]: just copies 16 bytes; no version/variant validation. PG accepts any 16-byte value as a valid UUID. Apps that rely on "this is a v4 UUID" need to validate at app level, not via the type.
- **uuidv7 / uuidv4 generation** (`utils/adt/uuid.c`): rely on `pg_strong_random` (CSPRNG). Header silent on the generator's randomness source.

## Cross-refs

- `source/src/backend/utils/adt/uuid.c` — gen_random_uuid (v4), uuidv7, uuid_recv.

## Issues

- None — header is appropriately minimal.
