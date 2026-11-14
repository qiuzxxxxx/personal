"""Tests for the withdrawal scope of the context epoch.

Section 16.7 requires that a forgotten memory stops being injected into the
conversation that used it, while a chat that never enabled the knowledge
base or the personal memories must not lose its history.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase

from agent.models import Conversation, Message
from agent.views import _history_floor_epoch
from knowledge.memories import create_memory, current_floor_epoch, disable_memory


class WithdrawalScopeTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="withdraw", password="pw-withdraw-123456")
        self.plain = Conversation.objects.create(user=self.user, title="普通对话")
        self.informed = Conversation.objects.create(
            user=self.user, title="启用过知识库", context_injected=True
        )

    def test_plain_conversation_keeps_its_history(self):
        memory = create_memory(
            self.user, key="pref", content="偏好简体中文", status="active"
        )
        disable_memory(memory, expected_version=memory.version)
        self.assertGreater(current_floor_epoch(self.user), 1)
        # The conversation never received reference material, so its floor
        # stays at 1 and the history is not dropped.
        self.assertEqual(_history_floor_epoch(self.user, self.plain), 1)

    def test_informed_conversation_is_affected(self):
        memory = create_memory(
            self.user, key="pref", content="偏好简体中文", status="active"
        )
        disable_memory(memory, expected_version=memory.version)
        self.assertGreater(_history_floor_epoch(self.user, self.informed), 1)

    def test_floor_without_conversation_is_neutral(self):
        create_memory(self.user, key="pref", content="偏好", status="active")
        self.assertEqual(_history_floor_epoch(self.user), 1)

    def test_history_is_filtered_only_for_affected_conversations(self):
        from agent.llm import build_rich_messages

        memory = create_memory(
            self.user, key="pref", content="偏好简体中文", status="active"
        )
        Message.objects.create(
            conversation=self.plain, role="user", content="早于撤回", context_epoch=1
        )
        Message.objects.create(
            conversation=self.plain, role="assistant", content="早于撤回的回答", context_epoch=1
        )
        disable_memory(memory, expected_version=memory.version)

        current = Message.objects.create(
            conversation=self.plain, role="user", content="当前问题"
        )
        rich, _ = build_rich_messages(
            self.plain,
            current,
            [],
            "系统",
            history_floor_epoch=_history_floor_epoch(self.user, self.plain),
        )
        self.assertEqual(len(rich), 3)

        informed_current = Message.objects.create(
            conversation=self.informed, role="user", content="当前问题"
        )
        informed_rich, _ = build_rich_messages(
            self.informed,
            informed_current,
            [],
            "系统",
            history_floor_epoch=_history_floor_epoch(self.user, self.informed),
        )
        # The old turn is dropped from the model context of the affected chat.
        self.assertEqual(len(informed_rich), 1)
