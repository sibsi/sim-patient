from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from evaluation.judge import evaluate, prepare_input, validate_result, parse_judge_json, REALISM_DIMENSIONS
from evaluation.reporting import linguistic_metrics, summarize
from persona_profile import TRAITS
import evaluate as command


def fixture():
    turns = [{"turn": n, "question_type": "focused", "tags": ["trap_binary"],
              "doctor_question": "Question?", "provided_ids": ["X0"] if n in (1, 12) else [],
              "provided_facts": [{"id": "X0", "statement": "I do not smoke.", "type": "medical"}] if n in (1, 12) else [],
              "patient_reply": "I do not smoke."} for n in range(1, 17)]
    return {"status": "completed", "metadata": {"experiment": "frozen_facts", "pair": "SECRET_PAIR",
        "speaker": {"model": "SECRET_MODEL"}, "personality_condition": "SECRET_PROFILE", "inputs": {
            "persona_profile": {"content": json.dumps({"name": "SECRET_PROFILE", "traits": {
                name: "high" if name == "neuroticism" else "moderate" for name in TRAITS}})},
            "case": {"content": json.dumps({"name": "Test", "age": 29, "sex": "M", "diagnosis": "SECRET_DIAGNOSIS",
                                           "shards": [{"shard_id": "M99", "statement": "SECRET_UNUSED"}]})},
            "speaker_prompt": {"content": "Saved patient instructions."}}}, "turns": turns}


def raw_turns(turns):
    return [{"turn": t["turn"], "findings": [], "disclosure": [
        {"item_id": item["item_id"], "evidence": "I do not smoke."}
        for item in t["expected_items"]], "behaviors": [], "other_observations": [],
        "local_realism": []} for t in turns]


class FakeJudge:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def generate(self, messages, **kwargs):
        self.calls.append((deepcopy(messages), kwargs))
        if len(self.calls) == self.fail:
            return "not json"
        turns = json.loads(messages[1]["content"])["target_turns"]
        if kwargs["stage"] == "judge_annotation":
            return json.dumps({"turns": raw_turns(turns)})
        return json.dumps({"realism": {k: {"score": 5, "turn": 16, "quote": "I do not smoke.",
            "context_turns": [16], "explanation": "No concrete weakness."} for k in REALISM_DIMENSIONS}})


class EvaluationTests(unittest.TestCase):
    def test_json_normalization_preserves_strings_and_rejects_missing_values(self):
        expected = {"quote": 'Literal ,} and ,] and escaped "quote" and \\ path', "items": [1]}
        valid = json.dumps(expected)
        notes = []
        self.assertEqual(parse_judge_json(valid, notes), expected)
        self.assertEqual(notes, [])
        raw = "```json\n" + valid.replace('[1]', '[1,]')[:-1] + ",}\n```"
        self.assertEqual(parse_judge_json(raw, notes), expected)
        self.assertTrue(notes)
        for invalid in ('[,]', '{"x":,}', '[1,,]', '{"x": 1', 'Here is JSON: {}', '```json\n{}\n```\nExtra'):
            with self.subTest(invalid=invalid), self.assertRaises(json.JSONDecodeError):
                parse_judge_json(invalid, [])

    def test_word_counts_and_lexical_diversity(self):
        self.assertAlmostEqual(linguistic_metrics([
            {"patient_reply": "same " * 50}])["mattr"], 0.02)
        self.assertEqual(linguistic_metrics([
            {"patient_reply": " ".join(str(i) for i in range(50))}])["mattr"], 1.0)
        # two windows spanning replies: 49 unique words, then 50 unique words
        metrics = linguistic_metrics([
            {"patient_reply": "0"},
            {"patient_reply": " ".join(str(i) for i in range(50))}])
        self.assertAlmostEqual(metrics["mattr"], 0.99)
        self.assertEqual(metrics["mean_words_per_turn"], 25.5)
        self.assertIsNone(linguistic_metrics([{"patient_reply": "Too short."}])["mattr"])

    def test_batches_blinding_and_saved_metadata(self):
        backend = FakeJudge()
        result = evaluate(fixture(), backend)
        self.assertEqual(result["status"], "completed")
        self.assertEqual([c["target_turns"] for c in result["calls"]],
                         [list(range(1, 5)), list(range(5, 9)), list(range(9, 13)),
                          list(range(13, 17))] + [list(range(1, 17))])
        self.assertEqual(len(result["turns"]), 16)
        for index, (messages, _) in enumerate(backend.calls):
            self.assertNotIn("SECRET", json.dumps(messages))
            payload = json.loads(messages[1]["content"])
            if index < 4:
                self.assertEqual(len(payload["earlier_history_context_only"]), index * 4)
                self.assertEqual(payload["script_facts"][0]["assigned_turns"], [1, 12])
                self.assertEqual(len(payload["script_facts"]), 1)
            else:
                self.assertEqual(set(payload), {"target_turns", "local_observations"})
                self.assertEqual(set(payload["target_turns"][0]), {"turn", "doctor_question", "patient_reply"})
        other = FakeJudge()
        evaluate(fixture(), other)
        self.assertEqual([c[1]["seed"] for c in backend.calls], [c[1]["seed"] for c in other.calls])

    def test_failed_batch_remains_unassessed(self):
        result = evaluate(fixture(), FakeJudge(fail=4))
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(summarize(result)["unassessed_turns"], list(range(13, 17)))
        self.assertEqual(len(result["calls"]), 5)

    def test_invalid_disclosure_and_findings_are_local(self):
        data = prepare_input(fixture())
        rows = raw_turns(data["turns"][:5])
        rows[0]["disclosure"][0]["evidence"] = "invented quote"
        finding = {"kind": "unsupported_addition", "medical": True, "severity": "minor_context",
                   "contradicted_turn": None, "contradicted_item_id": None,
                   "claim": "I do not smoke.", "explanation": "Example."}
        rows[1]["findings"] = [finding, {**finding, "claim": "invented quote"}]
        response = {"turns": rows}
        corrections = []
        validate_result(response, data["turns"][:5], corrections=corrections)
        self.assertEqual(response["turns"][0]["disclosure"][0]["status"], "unassessed")
        self.assertEqual(response["turns"][1]["findings"], [finding])
        self.assertEqual(len(corrections), 2)

    def test_sparse_disclosure_distinguishes_absence_from_invalid_assessment(self):
        data = prepare_input(fixture())
        for problem in ("empty", "missing", "bad_quote"):
            with self.subTest(problem=problem):
                rows = raw_turns(data["turns"][:4])
                row = rows[0]
                if problem == "empty": row["disclosure"] = []
                if problem == "missing": del row["disclosure"]
                if problem == "bad_quote": row["disclosure"][0]["evidence"] = "invented"
                output = {"turns": rows}
                validate_result(output, data["turns"][:4])
                item = output["turns"][0]["disclosure"][0]
                if problem == "empty":
                    self.assertIs(item["disclosed"], False)
                else:
                    self.assertEqual(item["status"], "unassessed")

    def test_command_preserves_patient_run_and_writes_evaluation(self):
        class Client(FakeJudge):
            api_key = "ollama"
            def __init__(self, *args, **kwargs):
                super().__init__()
                self.unloaded = False
            def check_available(self): pass
            def prepare_local_model(self): pass
            def metadata(self): return {"model_name": "test-judge"}
            def unload(self): self.unloaded = True
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            source = json.dumps(fixture())
            (run / "conversation.json").write_text(source, encoding="utf-8")
            with patch.object(command, "LLMBackend", return_value=client), patch.object(command, "environment_info", return_value={}):
                self.assertEqual(command.main([str(run), "--model", "test-judge"]), 0)
            reports = list((run / "evaluations").glob("*/evaluation.json"))
            self.assertEqual(len(reports), 1)
            self.assertEqual(json.loads(reports[0].read_text(encoding="utf-8"))["status"], "completed")
            self.assertEqual((run / "conversation.json").read_text(encoding="utf-8"), source)
            self.assertTrue(client.unloaded)

