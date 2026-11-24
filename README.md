# statement-export-eval

One hand-built evaluation task for AI coding agents: a prompt, a small repository to work in, and a grader that scores the attempt from 0 to 100.

The task asks an agent to fix a month-end statement export for a credit union whose accounts are split across a legacy core and a new one. The repository's tests pass for a fix that is wrong in production. The grader measures whether the agent worked out what production actually does, from captured traffic, and built for that.

It is small on purpose: a worked example of building one task carefully, with the validation and the mistakes left in view.

## The task

The agent receives [`TASK.md`](TASK.md) as its prompt and the contents of [`workspace/`](workspace/) as its repository. It never sees `grader/` or `solutions/`.

The ticket reports two problems. Accounts on the new core are missing from statements, and a production statement came out with 75 of 165 transactions while reporting success. The second problem cannot be reproduced against the developer simulators in the repository.

## Why it is hard in the way real work is hard

- **The stand-in is more forgiving than production, and nothing says how.** The API notes list fields and no more. What production does with them has to be worked out from two captured traffic files in `workspace/logs/`: where a list resumes when a request carries both a token and a skip count, which way a balance moves on a credit, what a last page looks like, and what a script did when it got that wrong.
- **Passing tests is not the finish line.** The visible suite has one failing test. A change that makes it pass, and does nothing else, scores 28.5 out of 100.
- **The costly failure is silent.** The existing code returns a short statement and reports success. The runbook says an incomplete statement is worse than no statement, so part of the task is making failures loud.
- **The bug has a twin.** The same paging fault sits in a holds report that the ticket never mentions. Fixing only what was reported leaves it in place.
- **Nothing is a guessing game.** Every behavior the grader checks can be established from the ticket, the runbook, the API notes or the captures. The captures are real recordings: `grader/make_captures.py` produced them by running the unmodified code against the grader's production-faithful transports.

## What the grader scores

| Check | Points | What it shows |
| --- | --- | --- |
| Complete read of a 165-row account against production paging | 15 | Found the cause of the short export |
| Tern accounts included, period bounds respected | 15 | Built the new integration |
| The same paging fault fixed in the holds report | 10 | Fixed the cause, not only the reported symptom |
| A dead core or a short list fails the export instead of shortening it | 10 | No silent partial statements |
| Tern DEBIT and CREDIT shown from the member's point of view | 10 | Inferred the sign convention from the captured balances |
| PENDING and REJECTED postings left off | 10 | Noticed what production returns that the simulator does not |
| Accounts in migration, unknown or missing fail the export and are never read | 10 | Fails closed |
| Existing format unchanged for a legacy-only member | 10 | No regression |
| Empty-string cursor ends the list | 5 | Saw how production ends a list |
| Zero is written `0.00` | 3 | No floating-point artifacts in money |
| Simulators, fixtures, docs and captures untouched | 2 | Left alone what it was told to leave alone |

Two checks give half credit: an export that fails with the wrong exception type is better than one that returns a wrong statement, and the score says so. Those two checks only count if the same member exports correctly when nothing is wrong, so refusing everything earns nothing.

## Validation

`python3 validate.py` builds and grades three versions of the workspace, and fails if any of them does not come out as below:

| Version | Visible tests | Score |
| --- | --- | --- |
| Untouched repository | 1 failing | 13.5 |
| Naive fix (`solutions/naive`): adds the new core, stops when the tests pass | pass | 28.5 |
| Reference fix (`solutions/reference`) | pass | 100 |

Three models then attempted the task from the prompt and a fresh copy of the workspace, once at each of three effort settings:

| Model | Low | Medium | High |
| --- | --- | --- | --- |
| Claude Haiku | 65 | 87 | 100 |
| Claude Sonnet | 97 | 100 | 100 |
| Claude Opus | 100 | 100 | 100 |

Where the points went:

- **Haiku, low effort (65).** It read the capture as a fault partway through the list. The capture has no fault in it, only pages that skip ahead. The real cause stayed in place, behind a new completeness check that now fails the export loudly. It also found the twin in the holds report and left it for a separate ticket.
- **Haiku, medium effort (87).** It found the paging cause, left the holds report for a separate ticket, and wrote zero as `-0.00`.
- **Sonnet, low effort (97).** It wrote zero as `-0.00`.

The medium runs came first. The low and high runs were made after the capture fix and the grader rewrite described below.

What the attempts changed:

- **A first version was too easy.** It documented every production behavior in the API notes, and the same three models scored 95, 100 and 100 by reading them. This version moves that knowledge out of the notes and into the captures, and adds the holds report.
- **They found two faults in the grader.** One check assumed a page size of 25 and failed a correct attempt that used 100. Another failed an attempt that correctly retried a transient fault. Both checks were rewritten to test the behavior and not one way of implementing it.
- **One found a flaw in the data.** The Opus attempt noted that a capture labeled a card purchase as a credit. The narratives were corrected after the runs; nothing the grader scores depended on them.

A code review afterwards found that an attempt could forge its own score, by shipping a file named like one of the grader's modules or by printing a fake result line, and that an attempt which refused every export outscored the untouched repository. The attempt's code now runs in a process of its own, and the two failure checks are gated as described above. The three medium-effort scores were unchanged by the rewrite.

## Running it

Python 3.10 or later, standard library only.

    python3 validate.py                          # grade the three versions above
    python3 grader/grade.py path/to/workspace    # grade one attempt
    cd workspace && python3 -m unittest discover -s tests   # what the agent can run

To run an attempt, give an agent a fresh copy of `workspace/` and the text of `TASK.md`, then grade the directory it leaves behind.

`solutions/naive` and `solutions/reference` hold only the files each solution changes; `validate.py` lays them over a copy of the workspace.

## How the grader resists shortcuts

- **The attempt never shares a process with the grader.** Its code runs in a separate process and reaches the directory and the two cores only through proxies; every call crosses a pipe and is answered on the grader's side (`grader/sandbox.py`). It cannot import, patch or inspect what judges it, and it cannot reach past the API into a transport's data.
- **The grader's transports are its own** (`grader/strict_sims.py`). They import nothing from the workspace, so editing the developer simulators cannot raise a score.
- **The data is its own.** Accounts, ids and amounts are generated by the grader, so nothing can be hard-coded from the visible fixtures or the captures.
- **Statements are compared whole,** byte for byte, against a renderer the grader owns. There is no partial credit for a statement that is nearly right.
- **Every call into the attempt has a time limit,** and a score is computed and capped on the grader's side, never read from the attempt's output.
- **Every call an attempt makes to a core is recorded,** which is how "never read" is checked and not just "raised an error".

## Limitations

- **It separates the low end, not the top.** Scores rise with effort for the smallest model, and the largest scores 100 at every setting.
- **Process separation is not a sandbox.** The attempt's process has the same file and network access as the grader. Run untrusted attempts in a container that cannot read `grader/`.
- It is one task. It says something about care with evidence and failure handling, and nothing about scale, performance or user-facing work.
- The grader checks behavior, not the quality of the code or of the agent's closing summary. The prompt asks for a note on what could not be verified; scoring that note would take a rubric and a human or model judge.
- Each cell in the table is one run. Nine runs show a pattern, not a measurement.
- The holds check scores a judgment call. An agent that reports the twin and recommends a separate ticket has made a defensible choice and still loses those points.

## What a larger version would need

- **A longer task.** A whole service to build, not a fix, so that an attempt takes hours and early choices constrain later ones.
- **Difficulty tuned against the strongest model,** by the same loop used here: run attempts, read where they fail, check the grader is not at fault, then harden.
- **Repeated runs per model and setting,** so that a score is a distribution and not a single result.
- **A scored closing note.** A rubric, applied by a person or a model, for whether the agent said what it could not verify.
- **More than one task,** each drawn from a different kind of real failure.

## Where it comes from

The traps are generalized from failures seen in real work with coding agents on banking software, where code that passed against a simulator went on to fail against the real system. The institution, both cores, their APIs and all data here are invented for this task.

Built with an AI coding agent (Claude Code).
