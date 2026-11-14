"""Contract tests for the three outbound model protocols.

Section 16.9 requires that all three providers keep working when the
knowledge context is enabled. Anthropic in particular rejects consecutive
messages with the same role, so the reference material must never become an
extra user turn.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from agent.llm import (
    _claude_payload,
    _gemini_payload,
    _openai_payload,
    build_rich_messages,
)
from agent.models import Conversation, Message

CONTEXT = "【资料片段】[S1] 内容：示例片段。\n\n【个人记忆】[M1] 偏好简体中文。"


def roles_alternate(messages: list[dict]) -> bool:
    """No two consecutive messages may share the same role."""
    for previous, current in zip(messages, messages[1:]):
        if previous["role"] == current["role"]:
            return False
    return True


class PayloadContractTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="payload", password="pw-payload-123456")
        self.conversation = Conversation.objects.create(user=self.user, title="t")

    def build(self, context_text: str = CONTEXT, with_history: bool = True):
        if with_history:
            Message.objects.create(
                conversation=self.conversation, role="user", content="第一轮问题"
            )
            Message.objects.create(
                conversation=self.conversation, role="assistant", content="第一轮回答"
            )
        current = Message.objects.create(
            conversation=self.conversation, role="user", content="本轮问题"
        )
        return build_rich_messages(
            self.conversation,
            current,
            [],
            "系统提示",
            context_text=context_text,
        )

    def test_context_does_not_create_an_extra_user_turn(self):
        rich, _ = self.build()
        self.assertEqual([item.role for item in rich], ["user", "assistant", "user"])
        self.assertTrue(roles_alternate([{"role": item.role} for item in rich]))

    def test_context_is_attached_to_the_current_question(self):
        rich, _ = self.build()
        last = rich[-1]
        self.assertEqual(last.role, "user")
        self.assertIn(CONTEXT, last.text)
        self.assertIn("本轮问题", last.text)
        # The context must sit next to the question, not far away.
        self.assertLess(
            abs(last.text.index(CONTEXT) - last.text.index("本轮问题")),
            len(CONTEXT) + 40,
        )

    def test_no_context_keeps_the_message_list_unchanged(self):
        rich, _ = self.build(context_text="")
        self.assertEqual([item.role for item in rich], ["user", "assistant", "user"])
        self.assertNotIn("资料片段", rich[-1].text)

    def test_openai_payload_is_valid_with_context(self):
        rich, system = self.build()
        payload = _openai_payload({"model": "m"}, rich, system)
        self.assertEqual(payload[0]["role"], "system")
        body = payload[1:]
        self.assertTrue(roles_alternate(body))
        self.assertIn("资料片段", payload[-1]["content"])

    def test_claude_payload_alternates_roles_with_context(self):
        rich, system = self.build()
        payload = _claude_payload({"model": "m"}, rich, system)
        messages = payload["messages"]
        self.assertTrue(roles_alternate(messages))
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[-1]["role"], "user")
        self.assertIn("资料片段", messages[-1]["content"][0]["text"])

    def test_gemini_payload_is_valid_with_context(self):
        rich, system = self.build()
        payload = _gemini_payload(rich, system)
        contents = payload["contents"]
        self.assertTrue(roles_alternate(contents))
        self.assertIn("资料片段", contents[-1]["parts"][0]["text"])

    def test_context_survives_a_conversation_without_history(self):
        rich, _ = self.build(with_history=False)
        self.assertEqual([item.role for item in rich], ["user"])
        self.assertIn(CONTEXT, rich[0].text)
        messages = _claude_payload({"model": "m"}, rich, "s")["messages"]
        self.assertTrue(roles_alternate(messages))
        self.assertEqual(len(messages), 1)

    def test_strict_sources_extends_the_system_prompt(self):
        rich, system = self.build()
        self.assertNotIn("严格来源模式", system)
        _, strict_system = build_rich_messages(
            self.conversation,
            self.conversation.messages.order_by("-created_at").first(),
            [],
            "系统提示",
            context_text=CONTEXT,
            strict_sources=True,
        )
        self.assertIn("严格来源模式", strict_system)
        self.assertIn("来源编号", strict_system)
