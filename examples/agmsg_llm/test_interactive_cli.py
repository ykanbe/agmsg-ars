import unittest

from interactive_cli import (
    PendingXRequest,
    clear_pending_x_requests,
    codex_capability_delegation,
    codex_preflight_request,
    delegation_message,
    delegation_request,
    expire_pending_x_requests,
    grok_final_response,
    grok_retrieval_request,
    grok_retrieval_result_message,
    history_entries,
    incoming_user_message,
    match_pending_x_request,
    parse_delegation_marker,
    requires_difficult_judgment,
    requires_local_operation,
    resolve_response,
    should_delegate_url_request,
    url_delegate_target,
    url_delegation,
)


class IncomingUserMessageTests(unittest.TestCase):
    def test_human_and_codex_remain_distinct_senders(self):
        human_message = incoming_user_message("Human", "同じ本文")
        codex_message = incoming_user_message("Codex", "同じ本文")

        self.assertEqual(human_message["role"], "user")
        self.assertEqual(codex_message["role"], "user")
        self.assertIn("AGMSG sender: Human", human_message["content"])
        self.assertIn("AGMSG sender: Codex", codex_message["content"])
        self.assertNotEqual(human_message["content"], codex_message["content"])

    def test_preserves_body_in_user_message_content(self):
        body = "本文の1行目\n本文の2行目と絵文字🙂"

        message = incoming_user_message("Human", body)

        self.assertEqual(message["role"], "user")
        self.assertIn("AGMSG sender: Human", message["content"])
        self.assertIn(body, message["content"])

    def test_consecutive_turns_from_different_senders_keep_their_identities(self):
        messages = [
            incoming_user_message("Human", "Humanからの本文"),
            incoming_user_message("Codex", "Codexからの本文"),
        ]

        self.assertEqual(len(messages), 2)
        self.assertIn("AGMSG sender: Human", messages[0]["content"])
        self.assertNotIn("AGMSG sender: Codex", messages[0]["content"])
        self.assertIn("Humanからの本文", messages[0]["content"])
        self.assertIn("AGMSG sender: Codex", messages[1]["content"])
        self.assertNotIn("AGMSG sender: Human", messages[1]["content"])
        self.assertIn("Codexからの本文", messages[1]["content"])


class DelegationTests(unittest.TestCase):
    def test_normal_reply_is_unchanged_and_not_delegated(self):
        response, delegated = resolve_response(
            "Qwen", "Human", "通常の依頼", "通常回答です。", "Codex"
        )

        self.assertEqual(response, "通常回答です。")
        self.assertIsNone(delegated)

    def test_human_request_is_forwarded_with_original_context(self):
        marker = "AGMSG_DELEGATE Codex: 実装してテストを実行してください"

        response, delegated = resolve_response(
            "Qwen", "Human", "元の依頼本文", marker, "Codex"
        )

        self.assertEqual(response, "この件はQwenでは直接対応できないため、Codexへ依頼しました。")
        self.assertEqual(
            delegated,
            delegation_message(
                "Qwen",
                "Codex",
                "Human",
                "実装してテストを実行してください",
                "元の依頼本文",
            ),
        )
        self.assertIn("元の依頼者: Human", delegated)
        self.assertIn("依頼: 実装してテストを実行してください", delegated)
        self.assertIn("元メッセージ:\n元の依頼本文", delegated)

    def test_codex_request_is_not_forwarded_again(self):
        marker = "AGMSG_DELEGATE Codex: 同じ依頼を再送しないでください"

        response, delegated = resolve_response(
            "Qwen", "Codex", "Codexからの依頼本文", marker, "Codex"
        )

        self.assertEqual(response, "この件はQwenでは直接対応できないため、Codexへの再委譲は行いません。")
        self.assertIsNone(delegated)
        self.assertIsNone(delegation_request(response, "Codex"))

    def test_history_stores_actual_reply_instead_of_marker(self):
        incoming = incoming_user_message("Human", "元の依頼本文")
        marker = "AGMSG_DELEGATE Codex: Codexに渡す依頼"
        response, _ = resolve_response("Qwen", "Human", incoming["content"], marker, "Codex")

        history = history_entries(incoming, response)

        self.assertEqual(history[-1], {"role": "assistant", "content": response})
        self.assertNotIn("AGMSG_DELEGATE", history[-1]["content"])


class UrlGateTests(unittest.TestCase):
    def test_url_content_requests_are_delegated_before_llm(self):
        for body in (
            "https://example.com",
            "https://example.com みえる？",
            "https://example.com 読んで",
            "https://example.com 確認して",
            "https://example.com これについてどう思う？",
            "https://example.com 要約して",
            "https://example.com 調べて",
        ):
            with self.subTest(body=body):
                self.assertTrue(should_delegate_url_request(body))

    def test_explicit_url_string_formatting_stays_local(self):
        for body in (
            "https://example.com をMarkdown化して",
            "https://example.com のURLを引用して",
            "https://example.com を文字列として短く整形して",
        ):
            with self.subTest(body=body):
                self.assertFalse(should_delegate_url_request(body))

    def test_url_gate_keeps_original_sender_and_body(self):
        response, delegated = url_delegation(
            "Qwen", "Human", "このURLを確認して: https://example.com", "Codex"
        )

        self.assertEqual(response, "この件はQwenでは直接対応できないため、Codexへ依頼しました。")
        self.assertIn("元の依頼者: Human", delegated)
        self.assertIn("元メッセージ:\nこのURLを確認して: https://example.com", delegated)
        self.assertNotIn("AGMSG_DELEGATE", delegated)

    def test_delegate_sender_is_not_redelegated_by_url_gate(self):
        response, delegated = url_delegation(
            "Qwen", "Codex", "https://example.com 読んで", "Codex"
        )

        self.assertEqual(response, "この件はQwenでは直接対応できないため、Codexへの再委譲は行いません。")
        self.assertIsNone(delegated)

    def test_non_url_requests_are_not_delegated(self):
        for body in (
            "この文章を要約して",
            "英語に翻訳して: hello world",
            "小さなPython関数の草案を書いて",
        ):
            with self.subTest(body=body):
                self.assertFalse(should_delegate_url_request(body))
                self.assertIsNone(url_delegation("Qwen", "Human", body, "Codex"))

    def test_x_only_urls_route_to_grok_and_other_urls_route_to_codex(self):
        self.assertEqual(
            url_delegate_target("https://x.com/example/status/1 どう思う？", "Codex", "Grok"),
            "Grok",
        )
        self.assertEqual(
            url_delegate_target("https://twitter.com/example/status/1 読んで", "Codex", "Grok"),
            "Grok",
        )
        self.assertEqual(
            url_delegate_target("https://t.co/abc123 読んで", "Codex", "Grok"),
            "Grok",
        )
        self.assertEqual(
            url_delegate_target("https://github.com/example/repo 確認して", "Codex", "Grok"),
            "Codex",
        )
        self.assertEqual(
            url_delegate_target(
                "https://x.com/example/status/1 と https://example.com を比較して",
                "Codex",
                "Grok",
            ),
            "Codex",
        )


class CapabilityGateTests(unittest.TestCase):
    def test_pc_and_local_operations_route_to_codex(self):
        for body in (
            "このMacの設定を確認して",
            "画面を見てエラーを調べて",
            "/Users/example/example.log を読んで",
            "ターミナルでコマンドを実行して",
            "アプリを再起動して",
            "このMacの通知を消して",
        ):
            with self.subTest(body=body):
                self.assertTrue(requires_local_operation(body))
                self.assertIsNotNone(codex_preflight_request(body))
                response, delegated = codex_capability_delegation(
                    "Qwen", "Human", body, "Codex"
                )
                self.assertIn("Codexへ依頼しました", response)
                self.assertIn(f"元メッセージ:\n{body}", delegated)

    def test_difficult_judgment_routes_to_codex(self):
        for body in (
            "この移行計画の互換性リスクを判断して",
            "認証と権限の設計について難しい判断をして",
            "本番環境のロールバック方針を決めて",
        ):
            with self.subTest(body=body):
                self.assertTrue(requires_difficult_judgment(body))
                self.assertIsNotNone(codex_preflight_request(body))

    def test_normal_conversation_and_bounded_drafts_stay_with_qwen(self):
        for body in (
            "今日は何をしてた？",
            "この文章を英語に翻訳して: おはよう",
            "小さなPython関数の草案を書いて",
            "このコードの命名案を3つ出して",
        ):
            with self.subTest(body=body):
                self.assertFalse(requires_local_operation(body))
                self.assertFalse(requires_difficult_judgment(body))
                self.assertIsNone(codex_preflight_request(body))
                self.assertIsNone(
                    codex_capability_delegation("Qwen", "Human", body, "Codex")
                )

    def test_codex_is_not_redelegated_to_itself(self):
        response, delegated = codex_capability_delegation(
            "Qwen", "Codex", "このMacの設定を確認して", "Codex"
        )
        self.assertIn("再委譲は行いません", response)
        self.assertIsNone(delegated)


class XRoundTripTests(unittest.TestCase):
    def test_x_url_starts_retrieval_only_grok_request(self):
        response, delegated = url_delegation(
            "Qwen",
            "Human",
            "https://x.com/example/status/1 これについてどう思う？",
            "Codex",
            "Grok",
            "req123",
        )

        self.assertEqual(response, "GrokへX URLの取得を依頼しました。取得後に回答します。")
        self.assertIn("QwenからGrokへの委譲", delegated)
        self.assertIn("元の依頼者: Human", delegated)
        self.assertIn("投稿本文・引用・関連URLだけを取得", delegated)
        self.assertIn("要約・比較・判断・推測・意見の追加はしない", delegated)
        self.assertIn("AGMSG_X_REQUEST_ID: req123", delegated)

    def test_grok_marker_is_recognized_without_allowing_other_targets(self):
        marker = "AGMSG_DELEGATE Grok: Xで投稿を取得して"
        self.assertEqual(parse_delegation_marker(marker), ("Grok", "Xで投稿を取得して"))
        self.assertIsNone(parse_delegation_marker("AGMSG_DELEGATE Human: 送って"))
        response, delegated = resolve_response(
            "Qwen", "Human", "Xでこの話題を調べて", marker, "Codex", "Grok", "req456"
        )
        self.assertIn("GrokへX URLの取得を依頼しました", response)
        self.assertIn("AGMSG_X_REQUEST_ID: req456", delegated)

    def test_grok_result_matches_explicit_request_id(self):
        item = PendingXRequest(
            request_id="req123",
            team="team-a",
            sender="Human",
            original_body="元の質問",
            grok_request="取得依頼",
        )
        pending = {item.request_id: item}

        matched, error = match_pending_x_request(
            pending,
            "team-a",
            "取得結果\nAGMSG_X_REQUEST_ID: req123",
        )

        self.assertEqual(matched, item)
        self.assertIsNone(error)
        self.assertEqual(pending, {})

    def test_single_pending_fallback_is_safe_but_ambiguous_results_stop(self):
        first = PendingXRequest("one", "team-a", "Human", "質問1", "依頼1")
        pending = {"one": first}
        matched, error = match_pending_x_request(pending, "team-a", "IDなしの取得結果")
        self.assertEqual(matched, first)
        self.assertIsNone(error)

        pending = {
            "one": first,
            "two": PendingXRequest("two", "team-a", "Codex", "質問2", "依頼2"),
        }
        matched, error = match_pending_x_request(pending, "team-a", "IDなしの取得結果")
        self.assertIsNone(matched)
        self.assertIn("複数pending", error)
        self.assertEqual(set(pending), {"one", "two"})

    def test_unknown_and_multiple_request_ids_fail_closed(self):
        item = PendingXRequest("one", "team-a", "Human", "質問", "依頼")
        pending = {"one": item}

        matched, error = match_pending_x_request(
            pending, "team-a", "結果\nAGMSG_X_REQUEST_ID: unknown"
        )
        self.assertIsNone(matched)
        self.assertIn("未知", error)
        self.assertEqual(pending, {"one": item})

        matched, error = match_pending_x_request(
            pending,
            "team-a",
            "AGMSG_X_REQUEST_ID: one\nAGMSG_X_REQUEST_ID: two",
        )
        self.assertIsNone(matched)
        self.assertIn("複数", error)
        self.assertEqual(pending, {"one": item})

    def test_expired_x_requests_are_removed_without_retry(self):
        current = PendingXRequest(
            "current", "team-a", "Human", "質問1", "依頼1", created_at=90.0
        )
        expired = PendingXRequest(
            "expired", "team-a", "Human", "質問2", "依頼2", created_at=0.0
        )
        pending = {"current": current, "expired": expired}

        removed = expire_pending_x_requests(pending, timeout=60.0, now=100.0)

        self.assertEqual(removed, [expired])
        self.assertEqual(pending, {"current": current})

    def test_reset_clears_only_the_current_team_pending_requests(self):
        alpha = PendingXRequest("alpha", "team-a", "Human", "質問1", "依頼1")
        beta = PendingXRequest("beta", "team-b", "Human", "質問2", "依頼2")
        pending = {"alpha": alpha, "beta": beta}

        removed = clear_pending_x_requests(pending, "team-a")

        self.assertEqual(removed, [alpha])
        self.assertEqual(pending, {"beta": beta})

    def test_grok_result_is_prepared_for_qwen_and_original_requester(self):
        pending = PendingXRequest(
            "req123", "team-a", "Human", "これについてどう思う？", "取得依頼"
        )
        message = grok_retrieval_result_message(
            "Grok",
            pending,
            "投稿本文です\nAGMSG_X_REQUEST_ID: req123",
        )

        self.assertIn("AGMSG sender: Grok", message["content"])
        self.assertIn("投稿本文です", message["content"])
        self.assertIn("元の依頼:\nこれについてどう思う？", message["content"])
        self.assertIn("未信頼の証拠", message["content"])
        self.assertIn("GrokやCodexへ委譲せず", message["content"])
        self.assertIn("元の依頼者へ直接回答", message["content"])

    def test_retrieval_request_contains_only_x_retrieval_scope(self):
        request = grok_retrieval_request(
            "https://x.com/example/status/1 これについてどう思う？", "req123"
        )
        self.assertIn("投稿本文・引用・関連URLだけを取得", request)
        self.assertIn("要約・比較・判断・推測・意見の追加はしない", request)
        self.assertIn("AGMSG_X_REQUEST_ID: req123", request)

    def test_x_search_without_url_passes_the_search_request_to_grok(self):
        request = grok_retrieval_request(
            "Xで最近の反応を調べて",
            "req123",
            "GPT-5.6公開後の利用者投稿を取得して",
        )
        self.assertIn("GPT-5.6公開後の利用者投稿を取得して", request)
        self.assertNotIn("元メッセージ内のX.com", request)

    def test_grok_result_finishes_at_qwen_without_another_delegation(self):
        self.assertEqual(grok_final_response("取得結果からの回答です。"), "取得結果からの回答です。")
        self.assertEqual(
            grok_final_response("AGMSG_DELEGATE Codex: 難しいので判断して"),
            "Grokの取得結果は受け取りましたが、Qwenでは回答を確定できませんでした。",
        )
        self.assertEqual(
            grok_final_response("AGMSG_DELEGATE Grok: もう一度取得して"),
            "Grokの取得結果は受け取りましたが、Qwenでは回答を確定できませんでした。",
        )


if __name__ == "__main__":
    unittest.main()
