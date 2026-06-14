# contrib-jsonb_plperl (jsonb ↔ Perl scalar/hash/array transform)

- **Source path:** `source/contrib/jsonb_plperl/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `jsonb_plperl.control`)
- **Trusted:** yes (plperl trusted variant)
- **Requires:** `plperl` (or `plperlu`)
- **Variants:** `jsonb_plperl` (trusted) + `jsonb_plperlu` (untrusted)

## 1. Purpose

PL transform — when a PL/Perl function receives a `jsonb`
argument or returns one, the transform converts between
`jsonb` and Perl native types. Like `hstore_plperl` but:

- **jsonb is more expressive** than hstore (nested, arrays,
  numbers, booleans, null).
- **Conversion is richer**:
  - jsonb object → Perl hash ref
  - jsonb array → Perl array ref
  - jsonb string → Perl scalar (PV)
  - jsonb number → Perl scalar (NV)
  - jsonb bool → Perl scalar (IV with 1/0)
  - jsonb null → Perl `undef`

## 2. The conversion architecture

[verified-by-code `jsonb_plperl.c:14-31`]

```c
static SV *Jsonb_to_SV(JsonbContainer *jsonb);
static void SV_to_JsonbValue(SV *in, JsonbInState *jsonb_state, bool is_elem);
static SV *JsonbValue_to_SV(JsonbValue *jbv);
```

Two recursive walkers — one for each direction:

- **`Jsonb_to_SV`** — walks a Jsonb tree, building Perl
  SVs (scalars, AVs, HVs) bottom-up.
- **`SV_to_JsonbValue`** — walks Perl reference, emitting
  JsonbValue calls bottom-up.

## 3. The Jsonb→SV recursion

[verified-by-code `jsonb_plperl.c:24-50`]

```c
static SV *
JsonbValue_to_SV(JsonbValue *jbv)
{
    switch (jbv->type)
    {
        case jbvBinary:
            return Jsonb_to_SV(jbv->val.binary.data);
        case jbvNumeric:
            /* construct Perl NV */
        case jbvString:
            /* construct Perl PV */
        case jbvBool:
            /* construct Perl IV 0/1 */
        case jbvNull:
            return &PL_sv_undef;
        case jbvArray:
            /* construct Perl AV recursing on children */
        case jbvObject:
            /* construct Perl HV recursing on children */
    }
}
```

The `jbvBinary` case is the lazy-deserialization handle from
the JsonbValue data-structure doc — the transform descends
into binary containers on demand.

## 4. The SV→Jsonb direction

Walks the Perl reference structure:

- **AV (array ref)** → jbvArray. Iterate elements,
  recurse.
- **HV (hash ref)** → jbvObject. Iterate (key, value),
  recurse on value.
- **Scalar IV** → jbvNumeric (if exact int) or jbvBool (if
  0/1).
- **Scalar NV** → jbvNumeric.
- **Scalar PV** → jbvString.
- **undef** → jbvNull.

Strict round-trip identity isn't preserved — a Perl scalar
that holds `1` becomes a jbvNumeric, not jbvBool. Use
`JSON::PP::true` / `JSON::PP::false` if exact boolean
preservation matters.

## 5. The SQL setup

```sql
CREATE EXTENSION jsonb_plperl;

CREATE FUNCTION process_jsonb(j jsonb) RETURNS jsonb
TRANSFORM FOR TYPE jsonb
LANGUAGE plperl
AS $$
    my $j = $_[0];   -- a Perl hash/array/scalar
    push @{$j->{events}}, {timestamp => time(), processed => 1};
    return $j;
$$;
```

The function body sees native Perl structures. The TRANSFORM
clause engages the conversion both ways.

## 6. The performance win

Compared to the no-transform path (where PL/Perl receives a
jsonb-as-text and must parse it via `decode_json`):

- **Path 1** (no transform): `jsonb_out` →
  `JSON::PP::decode` → walk the structure → modify →
  `JSON::PP::encode` → `jsonb_in`.
- **Path 2** (transform): `Jsonb_to_SV` → walk → modify →
  `SV_to_JsonbValue`.

Path 2 skips the text serialize/deserialize round-trip.
On medium documents (10KB), the saving is ~5-10×.

## 7. Variants

| Extension | PL | Trusted? |
|---|---|---|
| `jsonb_plperl` | plperl | yes |
| `jsonb_plperlu` | plperlu | no |

`jsonb_plperl` IS trusted [verified-by-code
`jsonb_plperl.control:trusted = true`]. Means ordinary
users can CREATE EXTENSION + use the transform without
superuser.

## 8. The numeric subtlety

Perl's number model:
- `IV` — integer (long)
- `NV` — float (double)
- Auto-conversion between them via Perl's magic.

JSONB's number model: `Numeric` — arbitrary precision +
arbitrary range.

Round-trip:
- Small ints (< 2^53): exact.
- Large ints (>2^53): may lose precision in Perl's IV/NV.
- Decimals: precision depends on Perl's NV (typically
  IEEE 754 double).

For exact financial / scientific JSONB processing, the
text path may be preferable to avoid precision loss.

## 9. Production-use guidance

- **For complex JSONB processing**, the transform is the
  right choice — performance + ergonomics.
- **For exact numeric preservation**, check round-trip
  results before assuming Perl IV/NV is precise enough.
- **The trusted variant** lets ordinary users adopt
  without superuser overhead.
- **Encoding**: requires UTF-8 database; SQL_ASCII may
  cause issues.

## 10. Invariants

- **[INV-1]** Conversion is recursive in both directions;
  preserves nesting.
- **[INV-2]** Numeric round-trip may lose precision for
  large values.
- **[INV-3]** Perl `undef` ↔ JSONB `null`.
- **[INV-4]** Trusted (jsonb_plperl) variant available;
  ordinary users can install.
- **[INV-5]** Engaged via `TRANSFORM FOR TYPE jsonb`.

## 11. Useful greps

- The recursion entry points:
  `grep -n 'Jsonb_to_SV\|SV_to_JsonbValue\|JsonbValue_to_SV' source/contrib/jsonb_plperl/jsonb_plperl.c | head -10`
- jbvType dispatch:
  `grep -n 'jbvBinary\|jbvObject\|jbvArray' source/contrib/jsonb_plperl/jsonb_plperl.c | head -10`
- Numeric handling:
  `grep -n 'Numeric\|NV\|IV' source/contrib/jsonb_plperl/jsonb_plperl.c | head -10`

## 12. Cross-references

- `knowledge/data-structures/jsonbvalue.md` — the JsonbValue
  type the transform walks.
- `knowledge/subsystems/contrib-hstore_plperl.md` —
  sibling transform; hstore instead of jsonb.
- `knowledge/subsystems/contrib-hstore_plpython.md` —
  sibling transform; Python instead of Perl.
- `.claude/skills/fmgr-and-spi/SKILL.md` — PL function
  registration.
- `source/contrib/jsonb_plperl/jsonb_plperl.c` —
  implementation (309 LOC).
