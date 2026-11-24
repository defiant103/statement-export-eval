# statement-export-eval

One hand-built evaluation task for AI coding agents: a prompt, a small repository to work in, and a grader that scores the attempt from 0 to 100.

The task asks an agent to fix a month-end statement export for a credit union whose accounts are split across a legacy core and a new one. The repository's tests pass for a fix that is wrong in production. The grader measures whether the agent worked out what production actually does, from captured traffic, and built for that.

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

Some checks give half credit. An export that fails with the wrong exception type is better than one that returns a wrong statement, and the score says so.

## Validation

`python3 validate.py` builds and grades three versions of the workspace:

| Version | Visible tests | Score |
| --- | --- | --- |
| Untouched repository | 1 failing | 13.5 |
| Naive fix (`solutions/naive`): adds the new core, stops when the tests pass | pass | 28.5 |
| Reference fix (`solutions/reference`) | pass | 100 |

Three models then attempted the task once each, from the prompt and a fresh copy of the workspace, at the same effort setting:

| Model | Score | What it missed |
| --- | --- | --- |
| Claude Haiku | 87 | Found the twin of the paging fault in the holds report and recommended a separate ticket instead of fixing it; wrote zero as `-0.00` |
| Claude Sonnet | 100 | Nothing |
| Claude Opus | 100 | Nothing |

What the attempts changed:

- **A first version was too easy.** It documented every production behavior in the API notes, and the same three models scored 95, 100 and 100 by reading them. This version moves that knowledge out of the notes and into the captures, and adds the holds report.
- **They found two faults in the grader.** One check assumed a page size of 25 and failed a correct attempt that used 100. Another failed an attempt that correctly retried a transient fault. Both checks were rewritten to test the behavior and not one way of implementing it.
- **One found a flaw in the data.** The Opus attempt noted that a capture labeled a card purchase as a credit. The narratives were corrected after the runs; nothing the grader scores depended on them.

## Running it

Python 3.10 or later, standard library only.

    python3 validate.py                          # grade the three versions above
    python3 grader/grade.py path/to/workspace    # grade one attempt
    cd workspace && python3 -m unittest discover -s tests   # what the agent can run

To run an attempt, give an agent a fresh copy of `workspace/` and the text of `TASK.md`, then grade the directory it leaves behind. The grader executes the attempt's code, so grade untrusted attempts inside a sandbox.

## How the grader resists shortcuts

- It uses its own transports (`grader/strict_sims.py`) that behave as production does. They do not import the workspace's simulators, so editing those cannot raise a score.
- It builds its own accounts, ids and amounts, so nothing can be hard-coded from the visible fixtures or the captures.
- Statements are compared whole, byte for byte, against a renderer the grader owns. There is no partial credit for a statement that is nearly right.
- Each check runs in its own process with a time limit, so a loop that never ends costs that check and nothing else.
- It records every call an attempt makes to a core, which is how "never read" is checked and not just "raised an error".

## Limitations

- **It does not yet separate strong models.** See the attempts above. It shows the method on a small scale; a task that taxes current frontier models would need a larger codebase and a longer chain of dependent decisions.
- It is one task. It says something about care with evidence and failure handling, and nothing about scale, performance or user-facing work.
- The grader checks behavior, not the quality of the code or of the agent's closing summary. The prompt asks for a note on what could not be verified; scoring that note would take a rubric and a human or model judge.
- Each model was run once. One run per model is an anecdote, not a measurement.
- The holds check scores a judgment call. An agent that reports the twin and recommends a separate ticket has made a defensible choice and still loses those points.

## Where it comes from

The traps are generalized from failures seen in real work with coding agents on banking software, where code that passed against a simulator went on to fail against the real system. The institution, both cores, their APIs and all data here are invented for this task.

Built with an AI coding agent (Claude Code).
