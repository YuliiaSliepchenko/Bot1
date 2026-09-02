import unittest

from trial_chat import handle_chat


class TrialChatTests(unittest.TestCase):
    def test_booking_request_variants_start_registration(self):
        for message in [
            "можна записатись на пробне",
            "допомогти з записом",
            "допомогти із записом",
            "запис на пробне",
        ]:
            response = handle_chat("test-session", message)
            self.assertIn("Як звати дитину", response["response"])

    def test_gibberish_message_is_not_treated_as_valid_booking(self):
        response = handle_chat(
            "test-session",
            "e xfnf ytvf' ryjgjr yfcnegyjuj gbnfyyz oj, dsd lj ghjlf;sd",
        )
        self.assertNotIn("Як звати дитину", response["response"])
        self.assertIn("Можу розповісти", response["response"])


if __name__ == "__main__":
    unittest.main()
