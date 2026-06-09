# utils/arrayaccess.h — element-by-element array iteration

Source: `source/src/include/utils/arrayaccess.h` (127 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Inline `array_iter` walker over either a flat ArrayType or an ExpandedArrayHeader. Caller supplies the running index — iterator does no bound-checking of its own.

## Public API

- `array_iter` struct (`arrayaccess.h:33-50`): discriminator is `datumptr != NULL` (expanded with Datum[]) vs `dataptr != NULL` (flat).
- `array_iter_setup(&iter, AnyArrayType *a, elmlen, elmbyval, elmalign)` (`arrayaccess.h:53-87`).
- `array_iter_next(&iter, *isnull, i)` (`arrayaccess.h:89-125`) returns Datum.

## Invariants

- **INV-arrayiter-sequential** [from-comment, `arrayaccess.h:29-30`]: "these functions can only fetch elements sequentially" — despite the `i` arg looking random-access, internal `dataptr`/`bitmask` advance assumes monotonically-increasing `i`. Skipping or going backwards yields garbage.
- **INV-arrayiter-caller-bounds** [inferred, `arrayaccess.h:89-125`]: no bounds check on `i` vs nelems. Caller must already know nelems.
- **INV-arrayiter-bitmask-cycle** [verified-by-code, `arrayaccess.h:115-121`]: bitmask resets at `0x100` and advances `bitmapptr`. Holds the "1 = non-null, LSB-first" convention from array.h.

## Notable internals

- `it->elmalignby` (line 49) is stored as a precomputed `typalign_to_alignby()` result, not the raw `typalign` char — small but easy-to-miss caller contract.
- For expanded arrays with `dvalues == NULL` (flat embedded), iterator falls through to the flat walker against `xpn.fvalue` (`arrayaccess.h:69-74`).

## Trust-boundary / Phase-D surface

- Iterator trusts callers; if `array_recv` accepted a malformed dimensions/nelems/dataoffset, `array_iter_next` would happily walk off the end of the buffer. The DoS surface lives in the producers of array_iter, not the iterator itself.

## Cross-refs

- `knowledge/files/src/include/utils/array.md`
- `source/src/include/access/tupmacs.h` — `fetch_att`, `att_addlength_pointer`, `att_nominal_alignby`.

## Issues

- `[ISSUE-DOC: "index" arg is misleading (low)]` — `arrayaccess.h:29-30` admits the iterator is sequential despite the `i` parameter; an explicit assert `i == it_prev + 1` (under USE_ASSERT_CHECKING) would catch misuse.
