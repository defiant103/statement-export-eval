# Statement export: runbook

The export runs on the first night of each month, one member at a time. Its
output goes to the reconciliation job, which compares it byte for byte with the
ledger extract, and then to the member's statement.

## The rule that matters

A statement that is missing a transaction, or that includes one it should not,
is worse than no statement. Members act on these figures and so does
reconciliation. A statement lists the transactions that have taken effect on
the account in the period, and only those.

If a complete and correct statement cannot be produced for a member, the export
for that member must fail with `ExportError`. The nightly job catches it, holds
that member's statement and pages the on-call. It never sends a partial one.

## Accounts in migration

While an account is being moved from Kestrel to Tern, the directory reports its
home core as `MIGRATING`. During that window neither core's view of the account
is reliable, and the account must not be read from either. The same applies to
any home core value the export does not recognize, and to an account the
directory has no record of. In each case the member's export fails with an
`ExportError` that names the account.

## Output format

Do not change it. Columns are `account,date,id,description,amount`. Rows are in
date order and then id order within each account, accounts are in directory
order, each account ends with a `subtotal` row and the file ends with a `total`
row. Amounts have two decimal places, a leading minus sign when negative and no
thousands separator. Zero is written `0.00`.
