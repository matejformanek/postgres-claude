# utils/pg_crc.h — legacy + traditional CRC-32 macros

Source: `source/src/include/utils/pg_crc.h` (107 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Two flavors of 32-bit CRC, both using the same lookup table but applied differently. CRC-32C (Castagnoli — the only one new code should use) lives in `port/pg_crc32c.h`, not here.

## Public API

- `pg_crc32` typedef (`pg_crc.h:37`).
- **TRADITIONAL** macros (Ethernet polynomial): `INIT_TRADITIONAL_CRC32`, `FIN_TRADITIONAL_CRC32`, `COMP_TRADITIONAL_CRC32`, `EQ_TRADITIONAL_CRC32` (`pg_crc.h:46-50`). Used by ltree, hstore contrib only.
- **LEGACY** macros (broken pre-9.5 WAL algorithm): `INIT_LEGACY_CRC32`, `FIN_LEGACY_CRC32`, `COMP_LEGACY_CRC32`, `EQ_LEGACY_CRC32` (`pg_crc.h:79-83`). On-disk compat ONLY.
- Lookup helpers: `COMP_CRC32_NORMAL_TABLE` (`pg_crc.h:53-63`) and `COMP_CRC32_REFLECTED_TABLE` (`pg_crc.h:89-99`).
- `pg_crc32_table[256]` (`pg_crc.h:105`).

## Invariants

- **INV-CRC-32C-is-the-default** [from-comment, `pg_crc.h:27`]: "The CRC-32C variant is in port/pg_crc32c.h." Two-line redirect; new code should NEVER use traditional or legacy CRC from this header.
- **INV-legacy-is-broken-keep-anyway** [from-comment, `pg_crc.h:65-77`]: "subtly different ... it does not correspond to any polynomial in a normal CRC algorithm, so it's not clear what the error-detection properties of this algorithm actually are. We still need to carry this around because it is used in a few on-disk structures that need to be pg_upgradeable."
- **INV-traditional-only-ltree-hstore** [from-comment, `pg_crc.h:42-44`]: "currently only used in ltree and hstore contrib modules ... New code should use the Castagnoli version instead."
- **INV-Sarwate-algorithm** [from-comment, `pg_crc.h:52, 87`]: both variants use Sarwate's table-driven algorithm; the difference is normal vs reflected table application (and legacy uses normal table with reflected code — a historical mistake).
- **INV-same-table-shared** [verified-by-code, `pg_crc.h:101-104`]: same `pg_crc32_table[256]` works for both because traditional uses normal lookup, legacy uses reflected lookup (which would normally need a reflected table; the bug is that it doesn't).

## Trust-boundary / Phase-D surface

- **A11/A13 collision cluster echo** [from-corpus]: ltree, hstore, and other contrib modules using traditional CRC for hash-like distribution have weaker collision resistance than CRC-32C. For security-relevant hashes (signatures, dedup keys), CRC-32 of any flavor is unsuitable — use SipHash or similar.
- **Legacy CRC is on-disk** — any code reading/writing pre-9.5 WAL or specific contrib on-disk formats MUST use LEGACY macros. Switching to traditional or CRC-32C silently breaks compat.

## Cross-refs

- `source/src/include/port/pg_crc32c.h` — the preferred (Castagnoli) variant for new code.
- `source/src/common/pg_crc.c` — table.
- A14/A13 contrib hash findings: ltree, hstore, bloom, pg_trgm signature collision concerns.

## Issues

- `[ISSUE-DOC: header doesn't loudly redirect to pg_crc32c.h (low)]` — line 27 mentions it; could be a `#pragma message` or top-of-file banner.
- `[ISSUE-INVARIANT: legacy algorithm's error-detection properties unknown (info)]` — `pg_crc.h:67-73` admits this; can't really be fixed without on-disk break.
