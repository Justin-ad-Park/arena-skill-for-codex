"""Tests for skills/arena/bracket.py. Standard library only.

    python3 -m unittest discover -s tests -v

The headline test drives a full 64-agent tournament through the real command
line with random winners and checks it ends with exactly one survivor.
"""
import collections
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKILL = os.path.join(REPO, "skills", "arena")
BRACKET = os.path.join(SKILL, "bracket.py")
sys.path.insert(0, SKILL)

import bracket as B  # noqa: E402

EM_DASH, EN_DASH = chr(0x2014), chr(0x2013)   # spelled as code points so this file stays clean


def cli(*args):
    return subprocess.run([sys.executable, BRACKET] + [str(a) for a in args],
                          capture_output=True, text=True)


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load(d):
    with open(os.path.join(d, "arena.json"), encoding="utf-8") as fh:
        return json.load(fh)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="arena-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ok(self, *args):
        r = cli(*args)
        self.assertEqual(r.returncode, 0, "bracket.py %s failed:\n%s%s" % (" ".join(map(str, args)), r.stdout, r.stderr))
        return r.stdout


class SimulatedTournament(TempDir):
    """Random winners, driven only through the CLI: init, pairings, record, advance, status, winner."""

    def run_tournament(self, n, seed):
        d = os.path.join(self.tmp, "run-%d" % n)
        self.ok("init", "--agents", n, "--seed", seed, "--task", "Simulated task.", "--dir", d)
        rng = random.Random(seed)
        alive_at_start = []
        while True:
            state = load(d)
            if state["champion"]:
                break
            rd = state["rounds"][-1]
            alive_at_start.append(len(rd["alive"]))
            out = self.ok("pairings", "--dir", d)
            self.assertIn("round %d:" % rd["n"], out)
            in_round = [x for m in rd["matches"] for x in (m["a"], m["b"])] + ([rd["bye"]] if rd["bye"] else [])
            self.assertEqual(sorted(in_round), sorted(rd["alive"]), "everyone alive plays once or gets the bye")
            self.assertEqual(len(in_round), len(set(in_round)))
            for m in rd["matches"]:
                self.ok("record", m["id"], rng.choice([m["a"], m["b"]]), "--reason", "simulated", "--dir", d)
            self.ok("advance", "--dir", d)
        alive_at_start.append(1)
        return d, load(d), alive_at_start

    def test_64_agents_reach_exactly_one_survivor(self):
        d, state, sizes = self.run_tournament(64, 7)
        self.assertEqual(sizes, [64, 32, 16, 8, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 6)
        alive = [a for a, v in state["agents"].items() if v["alive"]]
        self.assertEqual(alive, [state["champion"]])
        dead = [v for v in state["agents"].values() if not v["alive"]]
        self.assertEqual(len(dead), 63)
        self.assertTrue(all(v["eliminated_in"] and v["eliminated_by"] for v in dead))
        self.assertEqual(sum(len(rd["matches"]) for rd in state["rounds"]), 63)
        self.assertTrue(all(rd["bye"] is None for rd in state["rounds"]))
        status = self.ok("status", "--dir", d)
        self.assertIn("now: 1 alive, 63 eliminated, champion %s" % state["champion"], status)
        won = self.ok("winner", "--dir", d)
        self.assertIn("CHAMPION  %s" % state["champion"], won)
        self.assertIn("6 played, 64 agents in, 1 left", won)
        self.assertIn("last one standing", self.ok("pairings", "--dir", d))

    def test_16_agents(self):
        _, state, sizes = self.run_tournament(16, 3)
        self.assertEqual(sizes, [16, 8, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 4)
        self.assertTrue(all(rd["bye"] is None for rd in state["rounds"]))
        self.assertEqual(sum(v["alive"] for v in state["agents"].values()), 1)

    def test_7_agents_with_a_bye(self):
        _, state, sizes = self.run_tournament(7, 11)
        self.assertEqual(sizes, [7, 4, 2, 1])
        self.assertEqual(len(state["rounds"]), 3)
        self.assertIsNotNone(state["rounds"][0]["bye"])
        self.assertEqual(sum(v["alive"] for v in state["agents"].values()), 1)

    def test_many_sizes_and_seeds_always_end_with_one(self):
        data = B.load_strategies()
        for n in (2, 3, 5, 9, 16, 31, 64, 100, 101, 144, 250):
            for seed in range(3):
                st = B.new_state(n, seed, data, os.path.join(self.tmp, "api"))
                rng = random.Random(seed)
                sizes = []
                while not st["champion"]:
                    rd = B.current_round(st)
                    sizes.append(len(rd["alive"]))
                    for m in rd["matches"]:
                        B.record(st, m["id"], rng.choice([m["a"], m["b"]]))
                    B.advance(st)
                self.assertEqual(sizes + [1], B.bracket_sizes(n))
                self.assertEqual(len(B.alive_ids(st)), 1)


class Dealer(unittest.TestCase):
    def setUp(self):
        self.data = B.load_strategies()

    def test_card_count(self):
        self.assertEqual(len(self.data["reasoning"]), 15)
        self.assertEqual(len(self.data["workflows"]), 12)
        self.assertEqual(len(self.data["strategies"]), 12)
        self.assertEqual(B.combo_count(self.data), 2160)

    def check(self, n, seed):
        cards = B.deal(n, seed, self.data)
        self.assertEqual(len(cards), n)
        self.assertEqual(len(set(cards)), n, "no card is dealt twice")
        for dim, size in enumerate((15, 12, 12)):
            count = collections.Counter(c[dim] for c in cards)
            per = [count.get(i, 0) for i in range(size)]
            self.assertLessEqual(max(per) - min(per), 1, "balanced: n=%d seed=%d dim=%d %s" % (n, seed, dim, per))
        if n <= 144:
            for a, b in ((0, 1), (0, 2), (1, 2)):
                pairs = collections.Counter((c[a], c[b]) for c in cards)
                self.assertEqual(max(pairs.values()), 1, "two agents share two parts: n=%d seed=%d" % (n, seed))
        return cards

    def test_100_agents_unique_balanced_and_every_part_used(self):
        cards = self.check(100, 7)
        self.assertEqual(len({c[0] for c in cards}), 15)
        self.assertEqual(len({c[1] for c in cards}), 12)
        self.assertEqual(len({c[2] for c in cards}), 12)

    def test_guarantees_hold_across_sizes_and_seeds(self):
        for n in (1, 2, 7, 16, 32, 50, 99, 100, 101, 144):
            for seed in range(25):
                self.check(n, seed)
        for n in (145, 180, 500, 2160):
            self.check(n, 1)

    def test_deterministic_for_a_seed(self):
        self.assertEqual(B.deal(100, 42, self.data), B.deal(100, 42, self.data))
        self.assertNotEqual(B.deal(100, 42, self.data), B.deal(100, 43, self.data))

    def test_out_of_range(self):
        with self.assertRaises(B.ArenaError):
            B.deal(0, 1, self.data)
        with self.assertRaises(B.ArenaError):
            B.deal(2161, 1, self.data)

    def test_pairing_prefers_different_reasoning_modes(self):
        for seed in range(50):
            st = B.new_state(100, seed, self.data, "/tmp/unused")
            same = 0
            for m in st["rounds"][0]["matches"]:
                a, b = st["agents"][m["a"]], st["agents"][m["b"]]
                same += a["card"]["reasoning"]["id"] == b["card"]["reasoning"]["id"]
            self.assertLessEqual(same, 1, "at most one forced same-mode match in a 50-match round")


class Plan(unittest.TestCase):
    def test_numbers(self):
        for options, expected in (
            ([], (8, 3, 43, 17)),
            (["--quick"], (4, 2, 19, 8)),
            (["--agents", "64"], (64, 6, 379, 143)),
        ):
            with self.subTest(options=options):
                result = cli("plan", "--json", *options)
                self.assertEqual(result.returncode, 0, result.stderr)
                plan = json.loads(result.stdout)
                self.assertEqual(tuple(plan[key] for key in ("agents", "rounds", "calls", "waves")), expected)


class Verdicts(unittest.TestCase):
    def scores(self, c, m, s, r, cl, fatal=False):
        return {"correctness": c, "completeness": m, "specificity": s, "robustness": r, "clarity": cl, "fatal": fatal}

    def test_weights_match_the_rubric(self):
        with open(os.path.join(SKILL, "rubric.md"), encoding="utf-8") as fh:
            rows = re.findall(r"^\| (\w+) \| (\d+) \|", fh.read(), re.M)
        self.assertEqual([(k.lower(), int(w)) for k, w in rows], list(B.WEIGHTS))
        self.assertEqual(sum(w for _, w in B.WEIGHTS), 100)

    def test_total(self):
        self.assertEqual(B.weighted_total(self.scores(10, 10, 10, 10, 10)), 100.0)
        self.assertEqual(B.weighted_total(self.scores(8, 6, 7, 5, 9)), 68.5)   # (240 + 150 + 105 + 100 + 90) / 10
        self.assertIsNone(B.weighted_total({"correctness": 8}))

    def test_scores_beat_the_judges_pick(self):
        v = {"scores": {"a001": self.scores(5, 5, 5, 5, 5), "a002": self.scores(8, 8, 8, 8, 8)}, "winner": "a001"}
        w, totals, note = B.decide(v, "a001", "a002")
        self.assertEqual(w, "a002")
        self.assertIn("scores win", note)

    def test_fatal_rule(self):
        v = {"scores": {"a001": self.scores(9, 9, 9, 9, 9, fatal=True), "a002": self.scores(4, 4, 4, 4, 4)}}
        self.assertEqual(B.decide(v, "a001", "a002")[0], "a002")

    def test_tie_goes_to_fewer_standing_attacks(self):
        v = {"scores": {"a001": self.scores(7, 7, 7, 7, 7), "a002": self.scores(7, 7, 7, 7, 7)},
             "standing": {"a001": ["x", "y"], "a002": ["z"]}}
        self.assertEqual(B.decide(v, "a001", "a002")[0], "a002")

    def test_incomplete_scores_fall_back_to_the_pick(self):
        v = {"scores": {"a001": {"correctness": 3}}, "winner": "a001"}
        self.assertEqual(B.decide(v, "a001", "a002")[0], "a001")
        with self.assertRaises(B.ArenaError):
            B.decide({"scores": {}}, "a001", "a002")

    def test_json_inside_a_code_fence(self):
        self.assertEqual(B.extract_json('```json\n{"winner": "a001"}\n```'), {"winner": "a001"})
        self.assertIsNone(B.extract_json("no json here"))


class FullPipelineWithFakeAgents(TempDir):
    """Every phase, through the CLI, with fake sub-agents writing the files real ones would."""

    TASK = "Write a haiku about the sea.\nIt must mention salt.\nLiteral braces stay: {{name}} and {not_a_placeholder}."

    def fake_outputs(self, state, phase, jobs, rng):
        for j in jobs:
            for path in j["outputs"]:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            if phase == "spawn":
                body = "Salt on the wind, from %s." % j["agent"]
                write(j["outputs"][0], body)
            elif phase == "attack":
                write(j["outputs"][0], "ATTACK 1 [MINOR] too short\nWhere: line 1\nProblem: it is short.\n")
            elif phase == "defend":
                write(j["outputs"][0], "ATTACK 1: CONCEDE. Made it longer.\n")
                write(j["outputs"][1], "Salt on the long wind, revised by %s." % j["agent"])
            elif phase == "judge":
                a, b = j["a"], j["b"]
                s = lambda: {k: rng.randint(3, 10) for k, _ in B.WEIGHTS}
                v = {"match": j["match"], "scores": {a: s(), b: s()}, "winner": a, "reason": "fake",
                     "survived": ["too short"], "standing": {a: [], b: []}}
                write(j["outputs"][0], json.dumps(v))
            elif phase == "final":
                v = {"scores": {"X": {k: 8 for k, _ in B.WEIGHTS}, "Y": {k: 4 for k, _ in B.WEIGHTS}},
                     "winner": "X", "reason": "fake", "fixed": ["salt"]}
                write(j["outputs"][0], json.dumps(v))

    def test_every_phase_to_done(self):
        d = os.path.join(self.tmp, "run")
        task_file = os.path.join(self.tmp, "task.md")
        base_file = os.path.join(self.tmp, "baseline.md")
        write(task_file, self.TASK)
        write(base_file, "The sea is big.")
        self.ok("init", "--agents", 5, "--seed", 9, "--task-file", task_file, "--baseline-file", base_file, "--dir", d)
        self.assertTrue(os.path.isfile(os.path.join(d, "rubric.md")), "the run has its own rubric copy")
        rng = random.Random(9)
        seen = []
        for _ in range(200):
            out = self.ok("next", "--dir", d)
            phase = re.search(r"^(NEXT: (\w+)|DONE)", out, re.M)
            phase = "done" if phase.group(0) == "DONE" else phase.group(2)
            seen.append(phase)
            if phase == "done":
                break
            if phase in ("collect", "advance"):
                self.ok(phase, "--dir", d)
                continue
            listing = self.ok("prompts", phase, "--dir", d)
            state = load(d)
            jobs = B.phase_jobs(state, phase)
            for j in jobs:
                self.assertIn(j["prompt"], listing)
                with open(j["prompt"], encoding="utf-8") as fh:
                    brief = fh.read()
                self.assertNotIn("{{agent", brief)
                self.assertNotIn("{{out", brief)
                self.assertNotRegex(brief.replace("{{name}}", ""), r"\{\{\w+\}\}", "unfilled placeholder")
                if phase == "spawn":
                    task_block = brief.split("=== THE TASK (identical for every competitor) ===\n")[1]
                    task_block = task_block.split("\n=== END OF THE TASK ===")[0]
                    self.assertEqual(task_block, self.TASK)
                    card = state["agents"][j["agent"]]["card"]
                    self.assertIn("Reasoning mode: %s." % card["reasoning"]["name"], brief)
                    self.assertIn("NOT satisfied", brief)
                if phase == "judge":
                    self.assertNotIn("Reasoning mode", brief, "judges never see the cards")
                if phase == "final":
                    self.assertEqual(j["worker"], "baseline-judge")
            self.fake_outputs(state, phase, jobs, rng)
            self.ok("check", phase, "--dir", d)
        self.assertEqual(seen[-1], "done")
        self.assertIn("spawn", seen)
        self.assertIn("final", seen)
        self.assertEqual(seen.count("advance"), 3, "5 agents take 3 rounds")
        state = load(d)
        champ = state["agents"][state["champion"]]
        self.assertIn(".solution.md", champ["solution"], "the champion carries its revised solution")
        self.assertIn("revised by %s" % state["champion"], read(champ["solution"]))
        pair = {read(os.path.join(d, "final", "X.md")).strip(), read(os.path.join(d, "final", "Y.md")).strip()}
        self.assertIn("The sea is big.", pair)
        rep = json.loads(self.ok("winner", "--json", "--dir", d))
        self.assertEqual(rep["rounds"], 3)
        self.assertEqual(rep["final"]["better"], state["final"]["X"])
        self.assertTrue(rep["attacks_survived"])

        first_match = state["rounds"][0]["matches"][0]
        attack = B.attack_out(d, 1, first_match["id"], first_match["a"])
        marker = "Only the full report contains this third criticism."
        write(attack, "ATTACK 1 [MAJOR] First concern\nProblem: It is too vague.\n"
              "ATTACK 2 [MINOR] Second concern\n" + ("Long supporting detail. " * 15) +
              "\nATTACK 3 [MINOR] " + marker + "\n")
        summary = self.ok("report", "--dir", d)
        full_path = self.ok("report", "--detail", "full", "--save", "--dir", d).strip()
        full = read(full_path)
        for report in (summary, full):
            for aid in state["agents"]:
                self.assertIn("Salt on the wind, from %s." % aid, report)
            for round_number in range(1, 4):
                self.assertIn("## %d라운드\n" % round_number, report)
            self.assertIn("기존 답안과 비교", report)
            self.assertIn("First concern", report)
            self.assertIn("Made it longer.", report)
        self.assertIn("외 1건", summary)
        self.assertNotIn(marker, summary)
        self.assertIn(marker, full)
        self.assertIn("Long supporting detail. " * 15, full)
        self.assertIn("Salt on the long wind, revised by", full)
        self.assertIn(read(B.verdict_out(d, 1, first_match["id"])), full)
        self.assertIn(read(B.final_out(d)), full)

    def test_spawn_briefs_share_one_task_and_differ_in_card(self):
        d = os.path.join(self.tmp, "default run")
        out = self.ok("init", "--seed", 4, "--task", self.TASK, "--dir", d)
        self.assertIn("8 agents", out)
        self.ok("prompts", "spawn", "--dir", d)
        blocks, cards = set(), set()
        for name in sorted(os.listdir(os.path.join(d, "prompts", "r0"))):
            brief = read(os.path.join(d, "prompts", "r0", name))
            blocks.add(brief.split("=== THE TASK (identical for every competitor) ===\n")[1].split("\n=== END")[0])
            cards.add(brief.split("=== YOUR STRATEGY CARD ===")[1].split("=== END OF THE CARD ===")[0])
        self.assertEqual(len(os.listdir(os.path.join(d, "prompts", "r0"))), 8)
        self.assertEqual(blocks, {self.TASK}, "every competitor gets the exact same task text")
        self.assertEqual(len(cards), 8, "every competitor gets a different card")

    def test_progress_shows_only_finished_outputs_before_the_winner_exists(self):
        d = os.path.join(self.tmp, "progress")
        self.ok("init", "--agents", 2, "--task", self.TASK, "--dir", d)
        state = load(d)
        rng = random.Random(5)

        a, b = B.phase_jobs(state, "spawn")
        self.fake_outputs(state, "spawn", [a], rng)
        partial = self.ok("progress", "spawn", "--dir", d)
        self.assertIn("Salt on the wind, from a001.", partial)
        self.assertNotIn("a002", partial)
        self.fake_outputs(state, "spawn", [b], rng)
        second = self.ok("progress", "spawn", "--agent", "a002", "--dir", d)
        self.assertIn("Salt on the wind, from a002.", second)
        self.assertNotIn("a001", second)

        self.fake_outputs(state, "attack", B.phase_jobs(state, "attack"), rng)
        attacks = self.ok("progress", "attack", "--round", 1, "--dir", d)
        self.assertIn("too short", attacks)
        self.assertNotIn("**방어**", attacks)
        a, b = B.phase_jobs(state, "defend")
        write(a["outputs"][0], "ATTACK 1: CONCEDE. Made it longer.\n")
        self.assertNotIn("Made it longer.", self.ok("progress", "defend", "--dir", d))
        self.fake_outputs(state, "defend", [a, b], rng)
        defenses = self.ok("progress", "defend", "--detail", "full", "--dir", d)
        self.assertIn("Made it longer.", defenses)
        self.assertIn("Salt on the long wind, revised by", defenses)

        self.fake_outputs(state, "judge", B.phase_jobs(state, "judge"), rng)
        self.assertNotIn("진출", self.ok("progress", "selection", "--dir", d))
        self.ok("collect", "--dir", d)
        selected = self.ok("progress", "selection", "--dir", d)
        self.assertIn("진출", selected)
        self.assertIn("판정 이유", selected)
        self.assertIsNone(load(d)["champion"])
        path = self.ok("progress", "selection", "--detail", "full", "--save", "--dir", d).strip()
        self.assertIn("심판 판정 원문", read(path))

    def test_unreadable_verdict_is_set_aside_and_rerun(self):
        d = os.path.join(self.tmp, "bad")
        self.ok("init", "--agents", 2, "--seed", 1, "--task", "t", "--dir", d)
        state = load(d)
        m = state["rounds"][0]["matches"][0]
        path = B.verdict_out(d, 1, m["id"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write(path, "the judge rambled and wrote no json")
        r = cli("collect", "--dir", d)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unreadable", r.stdout)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(path + ".unreadable"))

    def test_four_competitors_finish_using_five_worker_handles(self):
        d = os.path.join(self.tmp, "limited")
        self.ok("init", "--agents", 4, "--task", self.TASK, "--dir", d)
        rng = random.Random(9)
        handles = {}
        dispatched = []

        for _ in range(19):
            out = self.ok("next", "--dir", d)
            if out.startswith("champion:") and "\nDONE." in out:
                break
            phase = re.search(r"^NEXT: (\w+)", out, re.M).group(1)
            if phase in ("collect", "advance"):
                self.ok(phase, "--dir", d)
                continue

            listing = json.loads(self.ok("prompts", phase, "--json", "--dir", d))
            wave = listing["waves"][0]
            if phase == "judge":
                self.assertEqual(len(wave), 1)
            for job in wave:
                role = job["worker"]
                expected = job["agent"] if phase != "judge" else "judge"
                self.assertEqual(role, expected)
                self.assertEqual(job["handle"], handles.get(role))
                if job["handle"] is None:
                    self.assertIn(phase, ("spawn", "judge"))
                    handle = "native-thread-%d" % len(handles)
                    handles[role] = handle
                    self.ok("worker", role, "--handle", handle, "--dir", d)
                dispatched.append(job["id"])
            self.fake_outputs(load(d), phase, wave, rng)
        else:
            self.fail("the bracket did not finish")

        self.assertEqual(len(set(dispatched)), 19)
        self.assertEqual(set(handles), {"a001", "a002", "a003", "a004", "judge"})
        self.assertEqual(json.loads(self.ok("worker", "--dir", d)), handles)
        self.assertEqual(json.loads(self.ok("winner", "--json", "--dir", d))["rounds"], 2)


class Guards(TempDir):
    def test_init_refuses_to_overwrite_and_bad_sizes(self):
        d = os.path.join(self.tmp, "run")
        self.ok("init", "--agents", 4, "--task", "t", "--dir", d)
        self.assertEqual(cli("init", "--agents", 4, "--task", "t", "--dir", d).returncode, 2)
        self.assertEqual(cli("init", "--agents", 0, "--task", "t", "--dir", d + "2").returncode, 2)
        self.assertEqual(cli("init", "--agents", 65, "--task", "t", "--dir", d + "3").returncode, 2)
        self.assertEqual(cli("init", "--quick", "--agents", 8, "--task", "t", "--dir", d + "4").returncode, 2)
        self.assertEqual(cli("init", "--agents", 4, "--task", "   ", "--dir", d + "5").returncode, 2)

    def test_plan_and_init_reject_invalid_options(self):
        for options in (("--agents", 1), ("--agents", 65), ("--wave", 0)):
            with self.subTest(options=options):
                d = os.path.join(self.tmp, "invalid")
                self.assertEqual(cli("plan", *options).returncode, 2)
                self.assertEqual(cli("init", *options, "--task", "t", "--dir", d).returncode, 2)
                self.assertFalse(os.path.exists(d))

    def test_quick_is_4(self):
        d = os.path.join(self.tmp, "quick")
        self.ok("init", "--quick", "--task", "t", "--dir", d)
        self.assertEqual(load(d)["agents_n"], 4)

    def test_record_rejects_an_outsider(self):
        d = os.path.join(self.tmp, "rec")
        self.ok("init", "--agents", 4, "--seed", 2, "--task", "t", "--dir", d)
        m = load(d)["rounds"][0]["matches"][0]
        outsider = next(a for a in load(d)["agents"] if a not in (m["a"], m["b"]))
        self.assertEqual(cli("record", m["id"], outsider, "--dir", d).returncode, 2)
        self.assertEqual(cli("advance", "--dir", d).returncode, 2, "cannot advance with open matches")

    def test_prompt_reference_contains_all_templates(self):
        self.assertEqual(sorted(B.load_templates()), sorted(B.TEMPLATES))

    def test_worker_binding_rejects_reusing_a_competitor_as_judge(self):
        d = os.path.join(self.tmp, "roles")
        self.ok("init", "--agents", 2, "--task", "t", "--dir", d)
        self.ok("worker", "a001", "--handle", "thread-1", "--dir", d)
        result = cli("worker", "judge", "--handle", "thread-1", "--dir", d)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(self.ok("worker", "--dir", d)), {"a001": "thread-1"})
        self.ok("worker", "a001", "--clear", "--dir", d)
        jobs = json.loads(self.ok("prompts", "spawn", "--json", "--dir", d))["waves"][0]
        self.assertIsNone(jobs[0]["handle"])

    def test_no_em_dashes_anywhere(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [x for x in dirs if x not in (".git", ".arena", "__pycache__")]
            for name in files:
                path = os.path.join(root, name)
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read()
                self.assertNotIn(EM_DASH, text, "em dash in %s" % os.path.relpath(path, REPO))
                self.assertNotIn(EN_DASH, text, "en dash in %s" % os.path.relpath(path, REPO))


if __name__ == "__main__":
    unittest.main(verbosity=2)
