import tempfile
import time
import unittest
from pathlib import Path

from api_bridge import add_request_id as add_reply_request_id
from ask_llm import add_request_id, approval_result, bridge_is_running


class ApprovalGateTests(unittest.TestCase):
    def test_request_id_uses_one_line_break_for_request_and_reply(self):
        expected = "本文\n<!-- agmsg-request-id:abc123 -->"
        self.assertEqual(add_request_id("本文", "abc123"), expected)
        self.assertEqual(add_reply_request_id("本文", "abc123"), expected)

    def test_accepts_explicit_approval(self):
        self.assertTrue(approval_result("判定: 許可"))
        self.assertTrue(approval_result("判定: 注意して許可"))
        self.assertTrue(approval_result("問題なし"))

    def test_rejects_denial_before_matching_approval_word(self):
        self.assertFalse(approval_result("判定: 不許可"))
        self.assertFalse(approval_result("中止してください"))

    def test_rejects_ambiguous_reply(self):
        self.assertIsNone(approval_result("確認しました"))

    def test_ignores_warning_words_after_approval_line(self):
        self.assertTrue(approval_result("判定: 注意して許可\n理由: Sol子agent禁止の強制を確認"))

    def test_bridge_heartbeat_must_be_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            heartbeat = Path(directory) / "bridge.heartbeat"
            self.assertFalse(bridge_is_running(heartbeat, 15))
            heartbeat.touch()
            self.assertTrue(bridge_is_running(heartbeat, 15))
            old = time.time() - 30
            heartbeat.touch()
            heartbeat.chmod(0o600)
            import os
            os.utime(heartbeat, (old, old))
            self.assertFalse(bridge_is_running(heartbeat, 15))


if __name__ == "__main__":
    unittest.main()
