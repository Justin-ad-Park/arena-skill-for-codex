---
name: arena
description: Run a Codex subagent tournament when the user asks for Arena or wants independent agents to compete over the same task. Give each competitor a distinct strategy card, then use peer critiques, revisions, and independent judges to select a winner.
---

# Arena

You coordinate the tournament. Each competitor writes an independent answer to a single shared task. In every match, both competitors critique and revise, and a separate judge scores both revisions without seeing strategy cards. The Python bracket engine applies the rubric and advances winners.

## Prepare the run

1. Read the options from the request. `--agents N` selects 2 to 64 competitors (default 8). `--quick` selects 4 and is mutually exclusive with `--agents`. `--seed S` fixes cards and pairing randomness. `--wave W` caps simultaneous jobs (default 4). Use the smaller of the requested wave and the host's available slots. `--report summary|full` selects the live and final report detail (default `summary`). A natural-language request for a competitor count is equivalent to `--agents N`. Report out-of-range sizes or unknown report modes before spawning anything.
2. Locate `bracket.py` beside this `SKILL.md` and run it using its absolute path and Python 3.8 or newer. For a report of a completed run, go directly to **Deliver the result** using its run path. Otherwise, run `plan` with the chosen size and wave, and tell the user the round count and expected calls before starting. A baseline comparison adds one judge call. An explicit request to use Arena authorizes the tournament. If the user hasn't asked for a tournament or delegation, ask before launching agents.
3. Check that the Codex session has native spawn, follow-up, and completion tools and that its agents share the workspace. Keep all tournament work in this session. In a host that counts idle threads and cannot close them, budget one thread per competitor and one exclusively for judging, plus one more if there is a baseline comparison. If a known hard limit is smaller, explain the capacity needed before spawning them.
4. To resume an unfinished run, use `status --dir <run path>` then continue at `next` with that path. For a new run, write a task brief with a unique filename inside `.arena/` under the user's working directory. Preserve the user's wording, requirements and relevant paths. When invoked without a task, use the most recent relevant user request. Keep your own favored solution out of the brief. If the user wants to beat an earlier answer, or invokes Arena without a task after rejecting the previous answer, save that answer separately as the baseline.
5. Run `init --task-file <task> [--agents N | --quick] [--wave W] [--seed S] [--baseline-file <file>]`. Save the absolute path printed after `arena ready:`. Pass `--dir <run path>` on every remaining command so concurrent runs don't get mixed up.

## Run the bracket

- Drive the run with `next`. For a job phase, run `prompts <phase> --json` to write its briefs and list the pending jobs in waves. Each job has a `worker` role, such as `a001`, `judge`, or `baseline-judge`, and a saved `handle`, if any. After a wave, refresh the listing before dispatching the next one. In particular, a worker spawned for the first judge job will be bound for the remaining tournament judge jobs. The engine uses [the prompt templates](references/prompts.md) and [the scoring rubric](rubric.md).
- **When the job has a reachable handle, continue it.** Use the host's tool that starts a new turn on the existing subagent, such as `followup_task` or `send_input`. Each initial competitor gets its own thread. That same thread handles its critiques and revisions in later rounds. One dedicated thread handles tournament judge jobs sequentially. The optional baseline comparison uses a separate judge who has never seen the winning answer. Do not send competitor briefs to either judge or judging briefs to competitors. Ask each judge to score only the current brief. Give the judge no strategy cards, author information, or scores from the orchestrator.
- **When the job has no reachable handle, spawn once for its role.** Use a clean context when available, especially for judges, and a consistent general-purpose role and model for competitors. Pass only the job ID and absolute brief path, for example `Arena job <id>. Read <absolute path> and complete that brief. Write only its assigned output and scratch files. Reply with a short receipt. Do not delegate.` Pass the same message format for follow-ups. Never forward the live chat reports to a worker. After a successful spawn, immediately save the returned handle with `worker <role> --handle <id> --dir <run path>`. A listed handle means continue, even if the agent is idle. If the host says a saved handle is closed or unknown, clear it with `worker <role> --clear`. The next worker for that role can pick up from the files.
- Run no more than the configured wave limit and wait before assigning another job to a busy worker. **On a spawn limit, keep the current phase and run path.** Finish in-flight jobs and dispatch any pending jobs with idle bound handles. If a new role still needs a slot and the host can close threads, close an idle worker that is no longer needed for the current wave, clear its binding, and retry the unscheduled job. Prefer eliminated competitors, then completed workers. A later job for a closed role can continue from its brief in a newly bound thread. If the host cannot free enough threads for unbound roles, report the actual limit and pending roles. A different competitor's thread is never a substitute for an independent draft or a judge.
- Use `check <phase>` and `next` after each phase. Retry missing outputs once on their assigned worker. Run `collect` when directed. An unreadable verdict is set aside and becomes a pending job again. Give a failing judge at most two retries. If output is still missing or invalid, report the phase and pending job IDs with the run path. Never fabricate a solution or verdict.
- Run `collect` and `advance` when `next` directs you to, with the following live updates in between. Each surviving answer carries its latest revision into the next round. When resuming or recovering after compaction, use `status --dir <run path>` and `next --dir <run path>` to continue from existing outputs.

## Show the tournament as it runs

Post the actual stage content as user-facing Markdown in this chat's progress or commentary channel **before starting the next stage**. A tool's stdout, an artifact link on its own, or a message that only says the stage finished does not show the user what happened.

| When | Show in chat |
| --- | --- |
| As each draft wave returns, before the next wave or the first attack | Run `progress spawn --agent <id>` with one `--agent` for each newly completed draft. Show the draft text under each participant ID. |
| After the attack check succeeds and before any defense starts | Run `progress attack --round N`. Show who attacked whom and what they found. |
| After the defense check succeeds and before judging starts | Run `progress defend --round N`. Show the concessions or rebuttals. In full mode also show the revised answers. |
| After collecting the round's verdicts and before `advance` | Run `progress selection --round N`. Show the selected participant, scores, and why they advanced for each match. |

Pass `--detail full` to progress commands for full mode. Default to compact match summaries. If a stage is too long for the chat, still post its key points immediately and link the full stage Markdown from `progress <phase> --detail full --save` with the same round when applicable. For long drafts, show an excerpt per participant and link their original drafts or an unfiltered spawn snapshot. Avoid reposting the same material when a stage is retried or resumed.

## Deliver the result

After `next` reports DONE, use `winner` and `report --detail <summary|full> --save --dir <run path>`. The report command writes a Markdown file in the existing run without spawning agents.

- Start the chat response with the winning solution and link the report. Include the strategy card and the baseline scores when available. If live updates could not be displayed, include the participant drafts and group match details by round in the final response.
- In summary mode, use the compact match entries from the summary report. Also save a full report with `report --detail full --save` so the user can open the original text without rerunning. For long runs, show a brief excerpt per competitor and the deciding points per round in chat, then link the saved summary and full reports.
- In full mode, preserve the original text. Show the full report inline if it fits. For long reports, link the complete Markdown file and tell the user that the file contains all answers, attacks, defenses, revisions, and verdicts. Do not abbreviate an excerpt and call it the full report.

Keep project changes in the proposed answer unless the user also authorized applying the result.
