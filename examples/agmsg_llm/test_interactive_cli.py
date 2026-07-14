import unittest

from interactive_cli import incoming_user_message


class IncomingUserMessageTests(unittest.TestCase):
    def test_ars_and_codex_remain_distinct_senders(self):
        ars_message = incoming_user_message("ARS", "同じ本文")
        codex_message = incoming_user_message("Codex", "同じ本文")

        self.assertEqual(ars_message["role"], "user")
        self.assertEqual(codex_message["role"], "user")
        self.assertIn("AGMSG sender: ARS", ars_message["content"])
        self.assertIn("AGMSG sender: Codex", codex_message["content"])
        self.assertNotEqual(ars_message["content"], codex_message["content"])

    def test_preserves_body_in_user_message_content(self):
        body = "本文の1行目\n本文の2行目と絵文字🙂"

        message = incoming_user_message("ARS", body)

        self.assertEqual(message["role"], "user")
        self.assertIn("AGMSG sender: ARS", message["content"])
        self.assertIn(body, message["content"])

    def test_consecutive_turns_from_different_senders_keep_their_identities(self):
        messages = [
            incoming_user_message("ARS", "ARSからの本文"),
            incoming_user_message("Codex", "Codexからの本文"),
        ]

        self.assertEqual(len(messages), 2)
        self.assertIn("AGMSG sender: ARS", messages[0]["content"])
        self.assertNotIn("AGMSG sender: Codex", messages[0]["content"])
        self.assertIn("ARSからの本文", messages[0]["content"])
        self.assertIn("AGMSG sender: Codex", messages[1]["content"])
        self.assertNotIn("AGMSG sender: ARS", messages[1]["content"])
        self.assertIn("Codexからの本文", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
