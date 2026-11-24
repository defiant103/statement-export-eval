# statement-export

Builds the month-end statement export for Lakeside Credit Union members.

- `export/` the service code. `build_statement` in `export/statement.py` builds statements and `build_holds_report` in `export/holds_report.py` builds the daily holds report.
- `sim/` developer simulators for the two cores, and their fixtures. Shared with other teams.
- `docs/` API notes for each core and the runbook.
- `logs/` request captures from production, pulled by operations for open tickets.
- `tests/` the test suite.

Run the tests from this directory:

    python3 -m unittest discover -s tests

Python 3.10 or later, standard library only.
