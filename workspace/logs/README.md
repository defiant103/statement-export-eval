# Production captures

Pulled by operations for STMT-212. One JSON object per line: the request this
side sent and the response or fault the core returned.

- `prod-kestrel-2026-03-01.jsonl` is this service's own traffic to Kestrel while
  it exported the February statement for the member in the ticket, account
  `K-10482-C`.
- `prod-tern-smoke-2026-02-20.jsonl` is from the migration team's smoke test
  against production Tern after wave 1. It was made with their own script, not
  with this service. The script did not finish and was stopped by hand.

These are production replies. The developer simulators in `sim/` were written
earlier, from the vendors' notes.
