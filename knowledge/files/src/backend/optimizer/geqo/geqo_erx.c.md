# geqo_erx.c — Edge-Recombination Crossover (default GEQO operator)

- **Source:** 479 lines · **Last verified commit:** `ef6a95c7c64`

ERX, default operator (selected via `#define ERX` in `geqo.h`). Builds an
edge table from both parents (`gimme_edge_table` / `gimme_edge`), then walks
it to produce a child tour (`gimme_tour` / `gimme_gene`). Negative edge
entries mark "shared" (preferred) edges. [verified-by-code:85-290]
On edge failure increments `edge_failures` for diagnostics. [verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
