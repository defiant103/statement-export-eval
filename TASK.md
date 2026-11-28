You are working in the `statement-export` service. The repository is in the current directory.

**STMT-212: migrated members missing from statements, and short exports in production**

Two problems have been reported against the month-end statement export, and both need to be fixed before the March run.

1. Members whose accounts have moved to the new core, Scarif, are getting statements without those accounts. Wave 1 of the migration finished in February and more waves are coming. The export needs to include Scarif accounts.

2. Finance says some February statements produced in production are short. The clearest case is a member with one busy checking account: the ledger shows 165 transactions for the month and the statement has 75. The export reported success. We have not been able to reproduce this against the developer simulators, where the same account exports all of its rows.

Please fix both. The usual constraints for this service apply:

- The output format must not change. Reconciliation compares the file byte for byte.
- A statement must never be silently incomplete or wrong. See the runbook.
- Do not modify anything under `sim/`. Those simulators are shared with other teams.
- Standard library only.

The API notes for both cores and the runbook are in `docs/`. Operations pulled request captures from production for both cores, and those are in `logs/`. When you are done, say briefly what you changed and why, and note anything you could not verify.
