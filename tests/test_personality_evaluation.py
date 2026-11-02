import unittest

from test_evaluation import fixture, raw_turns
from evaluation.judge import prepare_input, validate_result
from evaluation.personality import behavior_summary, validate_annotations


def annotation(category="affect", subtype="worry", quote="I am worried."):
    return {"category": category, "subtype": subtype, "evidence": [quote], "reason": "Added expression."}


def validate(entries, reply="I do not smoke. I am worried."):
    corrections, normalizations = [], []
    target = {"turn": 1, "patient_reply": reply,
              "expected_items": [{"statement": "I do not smoke."}]}
    result, complete = validate_annotations({"behaviors": entries, "other_observations": []},
                                           target, corrections, normalizations)
    return result, complete, corrections, normalizations


class BehaviorEvaluationTests(unittest.TestCase):
    def test_copy_layer_and_invention_boundaries(self):
        for quote, accepted in (("I do not smoke.", False), ("I am worried.", True),
                                ("I do not smoke. I am worried.", True)):
            with self.subTest(quote=quote):
                self.assertEqual(validate([annotation(quote=quote)])[1], accepted)
        invented = "My neighbour had this too."
        rows, complete, _, _ = validate([annotation("unasked_content", None, invented)], invented)
        self.assertTrue(complete)
        self.assertEqual(rows[0]["category"], "unasked_content")

    def test_invention_can_have_finding_and_behavior(self):
        data = prepare_input(fixture())
        target = data["turns"][0]
        target["patient_reply"] = "I do not smoke. I think it is an allergy."
        raw = raw_turns([target])[0]
        quote = "I think it is an allergy."
        raw["behaviors"] = [annotation("own_interpretation", None, quote)]
        raw["findings"] = [{"kind": "unsupported_addition", "medical": True,
            "severity": "could_change_interpretation", "contradicted_turn": None,
            "contradicted_item_id": None, "claim": quote, "explanation": "Unprovided hypothesis."}]
        result = {"turns": [raw]}
        validate_result(result, [target])
        self.assertEqual(len(result["turns"][0]["findings"]), 1)
        self.assertEqual(len(result["turns"][0]["annotations"]), 1)
        self.assertEqual(result["turns"][0]["factual_status"], "completed")

    def test_invalid_behavior_labels_are_rejected(self):
        for entry in (annotation(subtype="practical"), annotation(quote="invented quote")):
            self.assertFalse(validate([entry])[1])
        self.assertFalse(validate([annotation(), annotation()])[1])

    def test_overlapping_subtypes_count_each_turn_once(self):
        entries = [annotation(), annotation(subtype="embarrassment", quote="This is embarrassing.")]
        rows, complete, _, _ = validate(entries, "I am worried. This is embarrassing.")
        self.assertTrue(complete)
        summary = behavior_summary([{"turn": 1, "annotations_complete": True, "annotations": rows}], 16)
        affect = summary["behaviors"]["affect"]
        self.assertEqual(affect["count"], 1)
        self.assertEqual(affect["subtypes"]["worry"]["count"], 1)
        self.assertEqual(affect["subtypes"]["embarrassment"]["count"], 1)
        self.assertEqual(affect["unassessed_turns"], 15)
        empty = behavior_summary([], 16)
        self.assertIsNone(empty["behaviors"]["affect"]["count"])

    def test_contradiction_timing_uses_assigned_turns(self):
        from analyze_evaluations import contradiction_timing
        context = [{"turn": n, "expected_items": [{"item_id": "M1"}] if n in (2, 6) else
                    [{"item_id": "L0"}] if n == 8 else []} for n in range(1, 9)]
        def turn(number, item, status="completed"):
            return {"turn": number, "factual_status": status, "findings": [
                {"kind": "contradiction", "contradicted_item_id": item, "claim": "x"},
                {"kind": "unsupported_addition", "contradicted_item_id": None, "claim": "y"}]}
        document = {"report_context": context, "turns": [
            turn(1, "age"), turn(2, "M1"), turn(4, "M1"), turn(5, "L0"), turn(7, "M1", "needs_review")]}
        self.assertEqual([(r["turn"], r["fact_timing"]) for r in contradiction_timing(document)],
                         [(1, "identity"), (2, "current"), (4, "earlier"), (5, "future")])

        # checks annotation handling with a reviewed fixture; does not test live judge accuracy


if __name__ == "__main__":
    unittest.main()
