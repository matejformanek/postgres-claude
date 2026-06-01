# `src/backend/utils/hash/pg_crc.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~150
- **Source:** `source/src/backend/utils/hash/pg_crc.c`

Provides the lookup tables for CRC-32C and CRC-32 (Ethernet). Only
table data — the actual CRC loop is in `port/pg_crc32c_*.c` (with SSE4.2
/ ARMv8 / SW fallback implementations selected at configure time).

- `pg_crc32c_table[]` — Castagnoli polynomial (0x1EDC6F41 reflected),
  used for WAL records, page checksums, replication protocol message
  CRCs.
- `pg_crc32_table[]` — IEEE 802.3 polynomial, kept for legacy
  compatibility (used in a few external tools).

The hot path code (`pg_comp_crc32c`) lives in `src/port/`; the table
arrays here are linked into the backend so SW-fallback `pg_comp_crc32c_sb8`
can find them. [from-comment]
