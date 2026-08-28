"""The history-failure pilot session harness — validation and void behaviour.

Stdlib only, no network, no ``claude`` invocation. The subprocess boundary
(``cloner`` / ``agent_runner`` / ``check_runner``) is injected; validation logic
is exercised for real, never mocked.

Proves, per the parallel-work handoff:

- a valid 30-task manifest produces exactly 60 isolated arm plans;
- manifest and context SHA mismatches fail before launch;
- wrong strata, duplicate task IDs, incomplete pairs, missing treatment
  context, and any reviewer-only field fail closed;
- control and treatment prompts differ only by the registered context block;
- the frozen arm order is consumed exactly, not silently recomputed;
- output paths cannot sit inside the repo or collide across arms/reruns;
- the default CLI path never invokes the subprocess boundary;
- a dirty start, commit mismatch, missing transcript, or unwritable session
  voids the whole pair and preserves the invalid-run metadata.
"""

import importlib.util
import json
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "history_pilot_sessions",
    Path(__file__).resolve().parents[1] / "scripts" / "history_pilot_sessions.py",
)
hps = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hps)


def _manifest_and_packet(tmp):
    man = hps._fake_manifest()
    man_path = tmp / "manifest.json"
    man_path.write_text(json.dumps(man))
    man_sha = hps.sha256_file(man_path)
    manifest = hps.load_manifest(man_path, man_sha)
    pkt = hps._fake_packet(man_sha, man["tasks"])
    pkt_path = tmp / "packet.json"
    pkt_path.write_text(json.dumps(pkt))
    packet = hps.load_packet(pkt_path, hps.sha256_file(pkt_path), manifest)
    return man, man_path, man_sha, manifest, pkt_path, packet


class SelftestTests(unittest.TestCase):
    def test_module_selftest_passes(self):
        self.assertEqual(hps._selftest(), 0)


class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        (self.man, self.man_path, self.man_sha, self.manifest,
         self.pkt_path, self.packet) = _manifest_and_packet(self.tmp)

    def tearDown(self):
        self._dir.cleanup()

    def _reload(self, mutate):
        data = json.loads(self.man_path.read_text())
        mutate(data)
        path = self.tmp / "mutated.json"
        path.write_text(json.dumps(data))
        return hps.load_manifest(path, hps.sha256_file(path))

    def test_valid_manifest_yields_60_isolated_plans(self):
        plans = hps.build_plans(self.manifest, self.packet)
        self.assertEqual(len(plans), 60)
        self.assertEqual(len({p.out_subpath for p in plans}), 60)
        self.assertEqual(sum(p.arm == "control" for p in plans), 30)
        self.assertEqual(sum(p.arm == "treatment" for p in plans), 30)

    def test_manifest_sha_mismatch_fails_before_launch(self):
        with self.assertRaises(hps.HarnessError) as cm:
            hps.load_manifest(self.man_path, "0" * 64)
        self.assertIn("SHA-256 mismatch", str(cm.exception))

    def test_reviewer_only_field_is_rejected(self):
        for field in ("gold_landmine", "gold_refs", "failure_conditions",
                      "icarus_probe"):
            with self.assertRaises(hps.HarnessError):
                self._reload(lambda d, f=field: d["tasks"][0].__setitem__(f, "x"))

    def test_wrong_strata_counts_fail_closed(self):
        with self.assertRaises(hps.HarnessError):
            self._reload(lambda d: d["tasks"][0].__setitem__("stratum", "null"))

    def test_duplicate_task_id_fails_closed(self):
        with self.assertRaises(hps.HarnessError) as cm:
            self._reload(lambda d: d["tasks"][1].__setitem__(
                "task_id", d["tasks"][0]["task_id"]))
        self.assertIn("duplicate", str(cm.exception))

    def test_short_commit_sha_fails_closed(self):
        with self.assertRaises(hps.HarnessError):
            self._reload(lambda d: d["tasks"][0].__setitem__("commit", "abc123"))

    def test_frozen_arm_order_is_consumed_not_recomputed(self):
        # The manifest MUST carry arm_order; a missing one is an error, not a
        # silent recompute.
        with self.assertRaises(hps.HarnessError):
            self._reload(lambda d: d["tasks"][0].pop("arm_order"))
        # A tampered order that disagrees with the preregistered derivation is
        # rejected rather than trusted.
        first = self.man["tasks"][0]["task_id"]
        flipped = list(reversed(hps.derive_arm_order(first)))
        with self.assertRaises(hps.HarnessError) as cm:
            self._reload(lambda d: d["tasks"][0].__setitem__("arm_order", flipped))
        self.assertIn("arm_order", str(cm.exception))
        # And the plan order really follows the manifest field.
        plans = hps.build_plans(self.manifest, self.packet)
        for task in self.manifest["tasks"]:
            ordered = sorted((p for p in plans if p.task_id == task["task_id"]),
                             key=lambda p: p.order_index)
            self.assertEqual([p.arm for p in ordered], task["arm_order"])


class PacketValidationTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        (self.man, self.man_path, self.man_sha, self.manifest,
         self.pkt_path, self.packet) = _manifest_and_packet(self.tmp)

    def tearDown(self):
        self._dir.cleanup()

    def _load(self, pkt):
        path = self.tmp / "mutated_pkt.json"
        path.write_text(json.dumps(pkt))
        return hps.load_packet(path, hps.sha256_file(path), self.manifest)

    def test_context_sha_mismatch_fails_before_launch(self):
        with self.assertRaises(hps.HarnessError) as cm:
            hps.load_packet(self.pkt_path, "0" * 64, self.manifest)
        self.assertIn("SHA-256 mismatch", str(cm.exception))

    def test_packet_bound_to_wrong_manifest_fails(self):
        pkt = hps._fake_packet("f" * 64, self.man["tasks"])
        with self.assertRaises(hps.HarnessError) as cm:
            self._load(pkt)
        self.assertIn("manifest_sha256", str(cm.exception))

    def test_incomplete_pair_coverage_fails(self):
        pkt = hps._fake_packet(self.man_sha, self.man["tasks"])
        pkt["contexts"].pop(self.man["tasks"][2]["task_id"])
        with self.assertRaises(hps.HarnessError) as cm:
            self._load(pkt)
        self.assertIn("coverage is not exact", str(cm.exception))

    def test_extra_context_fails(self):
        pkt = hps._fake_packet(self.man_sha, self.man["tasks"])
        pkt["contexts"]["NOT-A-TASK"] = {
            "repo": "o/r", "commit": "0" * 40, "icarus_context": "x"}
        with self.assertRaises(hps.HarnessError):
            self._load(pkt)

    def test_wrong_repo_context_fails(self):
        pkt = hps._fake_packet(self.man_sha, self.man["tasks"])
        pkt["contexts"][self.man["tasks"][0]["task_id"]]["repo"] = "someone/else"
        with self.assertRaises(hps.HarnessError) as cm:
            self._load(pkt)
        self.assertIn("does not match the manifest", str(cm.exception))


class PromptShapeTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        (_, _, _, self.manifest, _, self.packet) = _manifest_and_packet(self.tmp)
        self.plans = hps.build_plans(self.manifest, self.packet)

    def tearDown(self):
        self._dir.cleanup()

    def test_control_and_treatment_differ_only_by_context_block(self):
        for task in self.manifest["tasks"]:
            c = next(p for p in self.plans
                     if p.task_id == task["task_id"] and p.arm == "control")
            t = next(p for p in self.plans
                     if p.task_id == task["task_id"] and p.arm == "treatment")
            ctx = self.packet["contexts"][task["task_id"]]["icarus_context"]
            expected = (c.prompt.rstrip() + "\n\n" + hps.CONTEXT_HEADER
                        + ctx.strip() + hps.CONTEXT_FOOTER)
            self.assertEqual(t.prompt, expected)
            self.assertEqual(c.context_sha256, "")
            self.assertTrue(t.context_sha256)
            self.assertNotIn("ICARUS", c.prompt)


class OutputPathTests(unittest.TestCase):
    def test_output_dir_cannot_be_inside_repo(self):
        with self.assertRaises(hps.HarnessError):
            hps.resolve_output_dir(hps.REPO_ROOT / "outputs" / "pilot")
        with self.assertRaises(hps.HarnessError):
            hps.resolve_output_dir(hps.REPO_ROOT)

    def test_reruns_never_overwrite_prior_attempts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (_, _, _, manifest, _, packet) = _manifest_and_packet(tmp)
            plans = [p for p in hps.build_plans(manifest, packet)
                     if p.task_id == "T01"]
            out = hps.resolve_output_dir(tmp / "runs")

            def cloner(repo, commit, dest):
                Path(dest).mkdir(parents=True)
                return hps.CloneState(str(dest), commit, "", "")

            def runner(plan, clone_dir):
                return hps.RunnerResult(
                    '{"result":"x"}', "x", "d", plan.commit, "", 0, 1.0,
                    "2.x", "m")

            hps.execute_pilot(plans, out, cloner=cloner, agent_runner=runner,
                              check_runner=lambda c, d: ("", 0))
            hps.execute_pilot(plans, out, cloner=cloner, agent_runner=runner,
                              check_runner=lambda c, d: ("", 0))
            for arm in ("control", "treatment"):
                names = sorted(p.name for p in (out / "T01" / arm).glob("attempt-*"))
                self.assertEqual(names, ["attempt-01", "attempt-02"])


class VoidBehaviourTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        (_, _, _, self.manifest, _, self.packet) = _manifest_and_packet(self.tmp)
        self.plans = hps.build_plans(self.manifest, self.packet)

    def tearDown(self):
        self._dir.cleanup()

    def _run(self, task_id, cloner, runner, name):
        out = hps.resolve_output_dir(self.tmp / name)
        plans = [p for p in self.plans if p.task_id == task_id]
        summary = hps.execute_pilot(plans, out, cloner=cloner, agent_runner=runner,
                                    check_runner=lambda c, d: ("", 0))
        return out, summary

    @staticmethod
    def _clean_cloner(repo, commit, dest):
        Path(dest).mkdir(parents=True)
        return hps.CloneState(str(dest), commit, "", "")

    @staticmethod
    def _ok_runner(plan, clone_dir):
        return hps.RunnerResult('{"result":"x"}', "x", "diff", plan.commit,
                                "", 0, 1.0, "2.x", "m")

    def test_dirty_start_voids_the_pair_and_keeps_metadata(self):
        def dirty(repo, commit, dest):
            Path(dest).mkdir(parents=True)
            return hps.CloneState(str(dest), commit, " M leftover.py", "")

        out, summary = self._run("T01", dirty, self._ok_runner, "dirty")
        self.assertFalse(summary[0]["pair_valid"])
        self.assertTrue((out / "T01" / "PAIR_VOID.json").is_file())
        void = json.loads(next((out / "T01").glob("*/attempt-*/VOID.json")).read_text())
        self.assertEqual(void["void_reason"], "dirty_start")

    def test_commit_mismatch_voids_the_pair(self):
        def wrong(repo, commit, dest):
            Path(dest).mkdir(parents=True)
            return hps.CloneState(str(dest), "0" * 40, "", "")

        _, summary = self._run("T01", wrong, self._ok_runner, "commit")
        self.assertFalse(summary[0]["pair_valid"])

    def test_popped_stash_voids_the_pair(self):
        def stashed(repo, commit, dest):
            Path(dest).mkdir(parents=True)
            return hps.CloneState(str(dest), commit, "", "stash@{0}: WIP")

        _, summary = self._run("T01", stashed, self._ok_runner, "stash")
        self.assertFalse(summary[0]["pair_valid"])

    def test_missing_transcript_voids_the_pair(self):
        def silent(plan, clone_dir):
            r = self._ok_runner(plan, clone_dir)
            r.transcript_text = "   "
            return r

        _, summary = self._run("T01", self._clean_cloner, silent, "silent")
        self.assertFalse(summary[0]["pair_valid"])

    def test_unwritable_session_voids_not_scored_as_failure(self):
        def blocked(plan, clone_dir):
            r = self._ok_runner(plan, clone_dir)
            r.permission_blocked = True
            return r

        out, summary = self._run("T01", self._clean_cloner, blocked, "blocked")
        self.assertFalse(summary[0]["pair_valid"])
        void = json.loads(next((out / "T01").glob("*/attempt-*/VOID.json")).read_text())
        self.assertEqual(void["void_reason"], "unwritable_session")

    def test_icarus_tool_call_in_either_arm_voids(self):
        def used(plan, clone_dir):
            r = self._ok_runner(plan, clone_dir)
            r.icarus_tool_calls = 2
            return r

        _, summary = self._run("T01", self._clean_cloner, used, "icarususe")
        self.assertFalse(summary[0]["pair_valid"])

    def test_gold_leak_voids_before_any_clone(self):
        leak_manifest = dict(self.manifest)
        leak_manifest["tasks"] = [dict(t) for t in self.manifest["tasks"]]
        leak_manifest["tasks"][0]["prompt"] = "work SECRET-LANDMINE"
        plans = [p for p in hps.build_plans(leak_manifest, self.packet)
                 if p.task_id == "T01"]
        out = hps.resolve_output_dir(self.tmp / "leak")
        clones = []

        def cloner(repo, commit, dest):
            clones.append(dest)
            return self._clean_cloner(repo, commit, dest)

        summary = hps.execute_pilot(plans, out, cloner=cloner,
                                    agent_runner=self._ok_runner,
                                    check_runner=lambda c, d: ("", 0),
                                    forbidden_strings=["SECRET-LANDMINE"])
        self.assertFalse(summary[0]["pair_valid"])
        self.assertEqual(clones, [])

    def test_healthy_pair_is_valid_and_writes_all_artifacts(self):
        out, summary = self._run("T01", self._clean_cloner, self._ok_runner, "ok")
        self.assertTrue(summary[0]["pair_valid"])
        for arm in ("control", "treatment"):
            attempt = next((out / "T01" / arm).glob("attempt-*"))
            for name in ("plan.json", "result.json", "hashes.json",
                         "transcript.jsonl", "patch.diff", "tree_start.json"):
                self.assertTrue((attempt / name).is_file(), name)
            hashes = json.loads((attempt / "hashes.json").read_text())
            self.assertIn("result.json", hashes)


class CliTests(unittest.TestCase):
    def test_default_is_dry_run_and_never_touches_the_boundary(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = hps._fake_manifest()
            man_path = tmp / "m.json"
            man_path.write_text(json.dumps(man))
            man_sha = hps.sha256_file(man_path)
            pkt_path = tmp / "p.json"
            pkt_path.write_text(json.dumps(hps._fake_packet(man_sha, man["tasks"])))
            pkt_sha = hps.sha256_file(pkt_path)
            out = tmp / "runs"

            called = []
            original = hps.git_clone_at_commit
            hps.git_clone_at_commit = lambda *a, **k: called.append(a)
            try:
                rc = hps.main([
                    "--manifest", str(man_path), "--manifest-sha256", man_sha,
                    "--context-packet", str(pkt_path), "--context-sha256", pkt_sha,
                    "--output-dir", str(out),
                ])
            finally:
                hps.git_clone_at_commit = original

            self.assertEqual(rc, 0)
            self.assertEqual(called, [])
            plans = json.loads((out / "plans.json").read_text())["plans"]
            self.assertEqual(len(plans), 60)

    def test_bad_manifest_hash_exits_2(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            man = hps._fake_manifest()
            man_path = tmp / "m.json"
            man_path.write_text(json.dumps(man))
            pkt_path = tmp / "p.json"
            pkt_path.write_text(json.dumps(
                hps._fake_packet(hps.sha256_file(man_path), man["tasks"])))
            rc = hps.main([
                "--manifest", str(man_path), "--manifest-sha256", "0" * 64,
                "--context-packet", str(pkt_path), "--context-sha256", "0" * 64,
                "--output-dir", str(tmp / "runs"),
            ])
            self.assertEqual(rc, 2)


class ParseTranscriptTests(unittest.TestCase):
    """`claude -p --output-format json --verbose` emits a LIST whose LAST event
    is the result. An earlier version assumed a dict with a top-level `result`
    key, so `final_response.txt` came out EMPTY for every arm while the run
    looked successful -- the most damaging silent failure available here, since
    the final response is the main artifact a reviewer scores. Found by a live
    one-arm smoke on 2026-08-28, before the batch ran."""

    def test_list_shape_extracts_result_and_summary(self):
        payload = [
            {"type": "system"},
            {"type": "assistant", "message": {}},
            {"type": "result", "subtype": "success", "is_error": False,
             "result": "Created SMOKE.txt.", "num_turns": 2,
             "duration_ms": 5227, "total_cost_usd": 0.105754,
             "usage": {"output_tokens": 139},
             "permission_denials": [], "stop_reason": "end_turn"},
        ]
        final, summary = hps.parse_cli_transcript(json.dumps(payload))
        self.assertEqual(final, "Created SMOKE.txt.")
        self.assertEqual(summary["total_cost_usd"], 0.105754)
        self.assertEqual(summary["num_turns"], 2)
        self.assertFalse(summary["is_error"])

    def test_dict_shape_still_tolerated(self):
        final, _ = hps.parse_cli_transcript(
            json.dumps({"type": "result", "result": "done"}))
        self.assertEqual(final, "done")

    def test_no_result_event_yields_empty_not_crash(self):
        self.assertEqual(
            hps.parse_cli_transcript(json.dumps([{"type": "system"}])), ("", {}))

    def test_garbage_yields_empty_not_crash(self):
        self.assertEqual(hps.parse_cli_transcript("not json"), ("", {}))
        self.assertEqual(hps.parse_cli_transcript(""), ("", {}))

    def test_permission_denial_is_visible_to_the_void_check(self):
        payload = [{"type": "result", "result": "x",
                    "permission_denials": [{"tool_name": "Write"}]}]
        _, summary = hps.parse_cli_transcript(json.dumps(payload))
        self.assertTrue(summary["permission_denials"])


if __name__ == "__main__":
    unittest.main()
