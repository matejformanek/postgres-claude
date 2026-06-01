# geqo_selection.c — linear-bias parent selection

- **Source:** 112 lines · **Last verified commit:** `ef6a95c7c64`

`geqo_selection` picks two distinct parents via `linear_rand`, which biases
toward better individuals using `Geqo_selection_bias`
(range 1.5–2.0, default 2.0). The sorted pool means index 0 is the fittest.
[verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
