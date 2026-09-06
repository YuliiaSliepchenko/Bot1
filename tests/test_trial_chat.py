import os
import tempfile
import unittest
from uuid import uuid4

import db
from trial_chat import handle_chat


class TrialChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(cls.temp_dir.name, "test-school.db")
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def session(self, prefix="test"):
        return f"{prefix}-{uuid4()}"

    def test_booking_request_variants_start_registration(self):
        for message in [
            "можна записатись на пробне",
            "допомогти з записом",
            "допомогти із записом",
            "запис на пробне",
        ]:
            response = handle_chat(self.session("booking"), message)
            self.assertEqual("ASKING_CHILD_NAME", response["state"])
            self.assertIn("Як звати дитину", response["response"])
            self.assertFalse(response.get("needs_ai", False))

    def test_complete_trial_funnel_creates_lead_without_ai(self):
        session_id = self.session("funnel")
        steps = [
            ("trial", "ASKING_CHILD_NAME"),
            ("Марія", "ASKING_CHILD_AGE"),
            ("age:10", "ASKING_COURSE"),
            ("photoshop", "ASKING_DATE"),
            ("date:П’ятниця", "ASKING_TIME"),
            ("time:15:00–18:00", "ASKING_PHONE"),
            ("093 148 03 43", "CONFIRMING_APPLICATION"),
            ("confirm", "APPLICATION_CREATED"),
        ]
        response = None
        for message, expected_state in steps:
            response = handle_chat(session_id, message)
            self.assertEqual(expected_state, response["state"])
            self.assertFalse(response.get("needs_ai", False))
        self.assertTrue(response["lead_id"].startswith("IT-"))

    def test_common_faq_does_not_call_ai(self):
        session_id = self.session("faq")
        handle_chat(session_id, "other_questions")
        response = handle_chat(session_id, "Пробний урок безкоштовний?")
        self.assertIn("безкоштовний", response["response"])
        self.assertFalse(response.get("needs_ai", False))
        self.assertFalse(response["used_ai"])

    def test_trial_information_question_does_not_start_funnel(self):
        response = handle_chat(self.session("trial-faq"), "Пробне заняття безкоштовне?")
        self.assertNotEqual("ASKING_CHILD_NAME", response["state"])
        self.assertIn("безкоштовний", response["response"])
        self.assertFalse(response.get("needs_ai", False))

    def test_unknown_school_question_uses_ai_only_in_ai_mode(self):
        session_id = self.session("ai")
        handle_chat(session_id, "other_questions")
        response = handle_chat(session_id, "Розкажіть докладніше про навчання")
        self.assertTrue(response["needs_ai"])

    def test_game_and_web_courses_are_available(self):
        session_id = self.session("directions")
        handle_chat(session_id, "course_selection")
        response = handle_chat(session_id, "10")
        button_ids = {item["id"] for item in response["buttons"]}
        self.assertIn("game_development", button_ids)
        self.assertIn("web", button_ids)
        self.assertIn("menu", button_ids)

    def test_video_interest_recommends_blogging_and_editing(self):
        session_id = self.session("video")
        handle_chat(session_id, "course_selection")
        handle_chat(session_id, "10")
        response = handle_chat(session_id, "blogging_video")
        self.assertEqual("OFFERING_TRIAL", response["state"])
        self.assertIn("Блогінг + Відеомонтаж", response["response"])

    def test_manager_button_bypasses_ai_mode(self):
        session_id = self.session("ai-manager")
        handle_chat(session_id, "other_questions")
        response = handle_chat(session_id, "manager")
        self.assertEqual("MANAGER_REQUEST", response["state"])
        self.assertFalse(response.get("needs_ai", False))

    def test_manager_callback_can_be_cancelled(self):
        session_id = self.session("manager")
        response = handle_chat(session_id, "manager")
        self.assertEqual("MANAGER_REQUEST", response["state"])
        self.assertTrue(any(item["id"].startswith("tel:") for item in response["buttons"]))
        response = handle_chat(session_id, "leave_phone")
        self.assertEqual("ASKING_CALLBACK_PHONE", response["state"])
        response = handle_chat(session_id, "093 148 03 43")
        self.assertEqual("CONFIRMING_CALLBACK", response["state"])
        response = handle_chat(session_id, "cancel_callback")
        self.assertEqual("IDLE", response["state"])
        self.assertIn("номер не передаємо", response["response"])

    def test_gibberish_message_is_not_treated_as_booking(self):
        response = handle_chat(
            self.session("gibberish"),
            "e xfnf ytvf' ryjgjr yfcnegyjuj gbnfyyz oj, dsd lj ghjlf;sd",
        )
        self.assertNotEqual("ASKING_CHILD_NAME", response["state"])
        self.assertFalse(response.get("needs_ai", False))


if __name__ == "__main__":
    unittest.main()
