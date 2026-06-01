# hashfunc.c

- **Source path:** `source/src/backend/access/hash/hashfunc.c` (428 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in hash-opclass support functions: `hashint2`, `hashint4`, `hashint8`, `hashfloat4`, `hashfloat8`, `hashoidvector`, `hashname`, `hashtext`, `hashvarlena`, `hash_numeric`, and their **extended variants** taking a seed (procnum 2). Most are thin wrappers over `hash_any()` or `hash_uint32()` (in `utils/hash/`). [from-comment, hashfunc.c:1-25]

## Rule

"It is expected that every bit of a hash function's 32-bit result is as random as every other; failure to ensure this is likely to lead to poor performance of hash joins, for example." [from-comment, hashfunc.c:21-24]

## Notes

- For `text`: `hashtext` hashes the *byte representation* under the collation's default encoding; for deterministic collations, that's just the bytes; for ICU non-deterministic, the function uses the collation key. (See `varlena.c`'s `hashtext` implementation reused here.)
- For floats: `+0.0` and `-0.0` hash to the same value; NaN normalizes to a single canonical NaN.

Tags: [from-comment, hashfunc.c:1-25].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
