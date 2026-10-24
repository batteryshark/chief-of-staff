# Fable admission and unsent cancellation

New Fable admissions reserve $17. The conservative estimate is four turns at
128,000 input tokens at $20/million plus 32,768 output tokens at $50/million:
$16.7936. This bound requires the operator-owned provider input to enforce
`max_tokens <= 32768` and the HIGH variant. The generic provider example shows
that cap; existing `promo-opencode.json` definitions are local and do not change
automatically. Review local provider inputs before admitting new Fable work.

Existing holds, cycles and history are unchanged. Public grant, 90% stop and
renewal policy remain operator-owned. Household hash-pinned rollout helpers are
not portable migrations and are not shipped. No automatic migration is claimed.

`{"action":"promo-cancel-unsent","attempt":"PREPARED_ATTEMPT","confirmed_not_sent":true}`
releases only a pristine prepared, unbound, unsettled attempt. Confirm it was
never sent first. Cancellation serializes atomically against creation, retains
the original bound and cycle, records a terminal administrative zero and no
provider receipt, and forbids ID replay. Bound or uncertain work cannot be
released this way.
