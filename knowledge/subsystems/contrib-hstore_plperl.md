# contrib-hstore_plperl (hstore ↔ Perl hash transform)

- **Source path:** `source/contrib/hstore_plperl/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.0` (per `hstore_plperl.control`)
- **Requires:** `hstore`, `plperl` (or `plperlu`)
- **Variants:** `hstore_plperl` (trusted, plperl) +
  `hstore_plperlu` (untrusted, plperlu)

## 1. Purpose

A **PL transform** — when a PL/Perl function receives an
`hstore` argument or returns one, the transform converts
between `hstore` and Perl `%hash`. Without the transform,
PL/Perl sees hstore as a text blob; with it, the function
body sees and produces a native Perl hash.

This is the **reference implementation** of the transform
mechanism for PL/Perl. Same shape applies to
`hstore_plpython`, `jsonb_plperl`, etc.

## 2. The transform mechanism

PL functions normally receive arguments as
`Datum` and pass through `SQL function → C handler → PL
runtime → user code`. For types the PL runtime doesn't
natively understand, the conversion is via the text
representation — `hstore_out(hstore) → 'a=>1, b=>2' → string
in Perl`.

A **transform** replaces the text-conversion with a direct
in-memory conversion: `hstore → native Perl hash`. The PL
function declares the transform; the dispatcher uses it
instead of the text path.

## 3. The SQL setup

```sql
CREATE EXTENSION hstore_plperl;

CREATE FUNCTION process_hstore(h hstore) RETURNS hstore
TRANSFORM FOR TYPE hstore   -- engages the transform
LANGUAGE plperl
AS $$
    my $h = $_[0];   -- now a Perl hash, not a string
    $h->{processed} = 1;
    return $h;
$$;
```

The `TRANSFORM FOR TYPE hstore` clause tells the function
to use the registered hstore↔plperl transform.

## 4. The implementation strategy

[verified-by-code `hstore_plperl.c:12-22`]

Cross-module access via function pointers:

```c
typedef HStore *(*hstoreUpgrade_t) (Datum orig);
static hstoreUpgrade_t hstoreUpgrade_p;
/* ... 4 more function pointers ... */

StaticAssertVariableIsOfType(&hstoreUpgrade, hstoreUpgrade_t);
```

The transform module loads `hstore.so` symbols at init,
caches them in static variables, and uses them at call
time. The `StaticAssertVariableIsOfType` ensures the
typedefs match the originals — catches API drift at build
time.

## 5. The conversion functions

The transform exports two `PG_FUNCTION_INFO_V1`-tagged
functions:

- **`hstore_to_plperl(internal)`** — converts an HStore
  to a Perl HV (hash value).
- **`plperl_to_hstore(internal)`** — converts a Perl
  reference (HV / scalar / array) to HStore.

The PL/Perl runtime calls these when entering / leaving a
function with the TRANSFORM clause.

## 6. The trusted vs untrusted variants

| Extension | PL | Use case |
|---|---|---|
| `hstore_plperl` | plperl (trusted) | Safe for ordinary users |
| `hstore_plperlu` | plperlu (untrusted) | Superuser-only PL/Perl |

Both ship from the same `hstore_plperl.so` binary — the
`module_pathname` is the same. The `requires` clause is
what differentiates them at CREATE EXTENSION time.

## 7. The conversion edge cases

- **NULL hstore key** — PG allows it; Perl hash keys must
  be strings. NULL is rejected with ERROR.
- **NULL hstore value** — represented as Perl `undef`.
- **Unicode** — both sides handle UTF-8 strings natively.
- **Deeply-nested structures** — hstore is flat
  (string→string); Perl hash can be nested; nested hashes
  produced from a PL/Perl function ERROR when converted
  back.

## 8. Production-use guidance

- **The trusted variant is the default** — use unless
  you specifically need untrusted-Perl features.
- **For deeply structured data**, use `jsonb` +
  `jsonb_plperl` instead — hstore is flat.
- **Performance** is the win: native hash vs string
  parse-then-walk is significantly faster.
- **Don't use without TRANSFORM clause** — without it,
  the function still sees a string.

## 9. Invariants

- **[INV-1]** Requires both `hstore` and `plperl` (or
  `plperlu`).
- **[INV-2]** Engaged via `TRANSFORM FOR TYPE hstore` in
  function definition.
- **[INV-3]** Hstore→Perl: keys + values become Perl
  scalars; NULL keys ERROR.
- **[INV-4]** Cross-module access via cached function
  pointers; StaticAssert validates types at build.
- **[INV-5]** Trusted (`hstore_plperl`) vs untrusted
  (`hstore_plperlu`) — same binary, different EXTENSION
  registration.

## 10. Useful greps

- The conversion entry points:
  `grep -n 'PG_FUNCTION_INFO_V1\|hstore_to_plperl\|plperl_to_hstore' source/contrib/hstore_plperl/hstore_plperl.c`
- Cross-module loading:
  `grep -n 'load_external_function\|hstoreUpgrade_p' source/contrib/hstore_plperl/hstore_plperl.c | head -5`

## 11. Cross-references

- `knowledge/subsystems/contrib-hstore.md` — the
  hstore type this transform handles.
- `knowledge/subsystems/contrib-jsonb_plperl.md` —
  sibling transform; jsonb instead of hstore.
- `knowledge/subsystems/contrib-hstore_plpython.md` —
  sibling transform; Python instead of Perl.
- `.claude/skills/fmgr-and-spi/SKILL.md` — PL function
  registration pattern.
- `.claude/skills/extension-development/SKILL.md` —
  cross-extension dependencies.
- `source/contrib/hstore_plperl/hstore_plperl.c` —
  implementation (156 LOC).
