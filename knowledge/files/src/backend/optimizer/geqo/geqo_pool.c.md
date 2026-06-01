# geqo_pool.c — GA chromosome pool management

- **Source:** 268 lines · **Last verified commit:** `ef6a95c7c64`

`alloc_pool` / `free_pool` / `random_init_pool` / `sort_pool` / `alloc_chromo`
/ `free_chromo` / `spread_chromo`. Sort order is ascending by `worth`
(= fitness from `geqo_eval`); `spread_chromo` does an insertion-sort-style
insert that drops the worst chromosome to make room. [verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
