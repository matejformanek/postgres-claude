For backpatching to PG 16, 17, and 18, you'd typically write
`Backpatch-through: 16-18` to indicate the range of branches.

The commit message on each back branch should mention which branch
it's being applied to, e.g. "Backpatch to REL_16_STABLE". You may
want to vary the message slightly per branch to reflect any
differences in the applied diff.

Example trailer:

```
Author: Jane Doe <jane@example.com>
Diagnosed-by: Your Name <you@example.com>
Reviewed-by: Reviewer One, Reviewer Two
Backpatch-through: 16-18
```

You can comma-separate reviewers to save space.
