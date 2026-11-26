---
name: arena
description: Run a Codex subagent tournament when the user asks for Arena or wants independent agents to compete over the same task. Give each competitor a distinct strategy card, then use peer critiques, revisions, and independent judges to select a winner.
---

# Arena

You coordinate the tournament. Each competitor writes an independent answer to a single shared task. In every match, both competitors critique and revise, and a fresh judge scores both revisions without seeing strategy cards. The Python bracket engine applies the rubric and advances winners.

## Prepare the run

1. Read the options from the request. `--agents N` selects 2 to 64 competitors (default 8). `--quick` selects 4 and is mutually exclusive with `--agents`. `--seed S` fixes cards and pairing randomness. `--wave W` caps simultaneous jobs (default 4). Use the smaller of the requested wave and the host's available slots. A natural-language request for a competitor count is equivalent to `--agents N`. Report out-of-range sizes before spawning anything.
2. Locate `bracket.py` beside this `SKILL.md` and run it using its absolute path and Python 3.8 or newer. Run `plan` with the chosen size and wave, and tell the user the round count and expected calls before starting. A baseline comparison adds one judge call. An explicit request to use Arena authorizes the tournament. If the user hasn't asked for a tournament or delegation, ask before launching agents.
3. Check that this Codex session exposes native subagent spawning and completion tools and that its agents can read and write the same workspace. If this session cannot do that, explain the requirement. Do not simulate a tournament in the parent or launch an alternate runtime.
4. To resume an existing run, use `status --dir <run path>` then continue at `next` with that run path. Skip initialization. For a new run, write a task brief with a unique filename inside `.arena/` under the user's working directory. Preserve the user's wording, requirements and relevant paths. When invoked without a task, use the most recent relevant user request. Keep your own favored solution out of the brief. If the user wants to beat an earlier answer, or invokes Arena without a task after rejecting the previous answer, save that answer separately as the baseline.
5. Run `init --task-file <task> [--agents N | --quick] [--wave W] [--seed S] [--baseline-file <file>]`. Save the absolute path printed after `arena ready:`. Pass `--dir <run path>` on every remaining command so concurrent runs don't get mixed up.

## Run the bracket

- Drive the run with `next`. For `spawn`, `attack`, `defend`, `judge`, and `final`, run `prompts <phase>` to produce briefs and list the pending jobs. The engine uses [the prompt templates](references/prompts.md) and [the scoring rubric](rubric.md).
- Spawn a fresh native Codex subagent per pending job using the general-purpose role (usually `default`). Use the session's spawn tool and give it only the job ID and absolute brief path, such as `Arena job <id>. Read <absolute path> and complete that brief. Write only its assigned output and scratch files in the shared workspace. Reply with a short receipt. Do not delegate.` Use a clean context when the host offers that option. Judges must not receive strategies, other job prompts, who wrote the answers, or the orchestrator's preference. Keep the same role and model for every competitor unless the user requests otherwise. Use a shared workspace so later jobs can read earlier outputs.
- Launch up to the available slot limit, wait for that group to finish using the host's wait or completion mechanism, and release finished slots (close or archive when the host provides that tool). If capacity is lower than the listed wave size, split the wave without dropping jobs. When a spawn fails because slots are full, let running jobs finish and retry the unscheduled job in the next group.
- Use `check <phase>` and `next` after each phase. Retry only jobs with missing output, once in a fresh subagent. For judging, run `collect` when directed. An unreadable verdict is set aside and becomes a pending job again. Give a failing judge at most two retries. If output is still missing or invalid, report the phase and pending job IDs with the run path so the user can resume. Never fabricate a solution or verdict.
- Run `collect` and `advance` when `next` directs you to. Report each completed round and how many competitors remain. Each surviving answer carries its latest revision into the next round. When resuming or recovering after compaction, use `status --dir <run path>` and `next --dir <run path>` to continue from existing outputs.

## Deliver the result

After `next` reports DONE, use `winner` and read the winning solution it points to. Return the solution, its strategy card, the strongest critiques it addressed, the round count, and the run path. If there was a baseline, report both scores and identify which answer scored higher. Keep project changes in the proposed answer unless the user also authorized applying the result.
