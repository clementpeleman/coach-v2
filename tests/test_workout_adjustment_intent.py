"""Regression tests for chat-driven workout draft adjustments."""
import unittest

from app.tools.training_recommendation_engine import adjust_recommendation


BASE_DRAFT = {
    "id": "draft-1",
    "status": "draft",
    "source": "backend",
    "type": "THRESHOLD",
    "sportType": "RUNNING",
    "durationMin": 55,
    "intensityPct": 100,
    "blocks": [],
}


class WorkoutAdjustmentIntentTests(unittest.TestCase):
    def test_informational_questions_do_not_change_the_draft(self):
        questions = [
            "Waarom is deze training 60 min?",
            "Wat is het verschil tussen interval en tempo?",
            "Ik liep gisteren 75 min; heeft dat invloed op mijn herstel?",
            "Is een duurloop beter voor mijn conditie?",
            "Waarom staan er 6x3 min intervallen?",
            "Kan je uitleggen waarom deze training zo lang is?",
        ]

        for question in questions:
            with self.subTest(question=question):
                adjusted = adjust_recommendation(BASE_DRAFT, question)
                self.assertFalse(adjusted["changedByInstruction"])
                self.assertEqual(adjusted["type"], BASE_DRAFT["type"])
                self.assertEqual(adjusted["sportType"], BASE_DRAFT["sportType"])
                self.assertEqual(adjusted["durationMin"], BASE_DRAFT["durationMin"])
                self.assertEqual(adjusted["intensityPct"], BASE_DRAFT["intensityPct"])

    def test_explicit_adjustment_requests_change_the_draft(self):
        cases = [
            ("Maak hem korter", {"durationMin": 45}),
            ("Kan je de training rustiger maken?", {"intensityPct": 95}),
            ("Liever fietsen", {"sportType": "CYCLING"}),
            ("Verander de training naar 60 min", {"durationMin": 60}),
            ("Doe maar 6x3 min VO2-intervallen", {"type": "VO2MAX"}),
        ]

        for instruction, expected in cases:
            with self.subTest(instruction=instruction):
                adjusted = adjust_recommendation(BASE_DRAFT, instruction)
                self.assertTrue(adjusted["changedByInstruction"])
                for key, value in expected.items():
                    self.assertEqual(adjusted[key], value)

    def test_response_style_request_does_not_change_workout_duration(self):
        adjusted = adjust_recommendation(BASE_DRAFT, "Maak je antwoord korter")

        self.assertFalse(adjusted["changedByInstruction"])
        self.assertEqual(adjusted["durationMin"], BASE_DRAFT["durationMin"])


if __name__ == "__main__":
    unittest.main()
