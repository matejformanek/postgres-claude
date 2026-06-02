(Baseline = no PG skill knowledge; identical to iter-1 baseline.)

For backpatching to PG 16, 17, and 18, you'd typically write
`Backpatch-through: 16-18` to indicate the range of branches.

The commit message on each back branch should mention which branch
it's being applied to. You may want to vary the message slightly per
branch.

Example trailer:

```
Author: Jane Doe <jane@example.com>
Diagnosed-by: Your Name <you@example.com>
Reviewed-by: Reviewer One, Reviewer Two
Backpatch-through: 16-18
```
