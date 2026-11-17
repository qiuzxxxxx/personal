from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import AccountProfile
from .models import Conversation, Message
from .retention import purge_expired_agent_history


class AgentRetentionTests(TestCase):
    def test_admins_are_permanent_and_members_keep_one_day(self):
        qzx = User.objects.create_user("qzx")
        sqx = User.objects.create_user("sqx")
        member = User.objects.create_user("member")
        AccountProfile.objects.create(user=sqx, access_level=AccountProfile.ADMIN)
        AccountProfile.objects.create(user=member, access_level=AccountProfile.MEMBER)
        admin_conversation = Conversation.objects.create(user=qzx, title="永久")
        second_admin_conversation = Conversation.objects.create(user=sqx, title="也永久")
        regular_conversation = Conversation.objects.create(user=member, title="一天")
        admin_message = Message.objects.create(
            conversation=admin_conversation, role="user", content="保留"
        )
        regular_message = Message.objects.create(
            conversation=regular_conversation, role="user", content="到期"
        )
        second_admin_message = Message.objects.create(
            conversation=second_admin_conversation, role="user", content="保留"
        )
        old = timezone.now() - timedelta(days=2)
        Message.objects.filter(
            pk__in=[admin_message.pk, second_admin_message.pk, regular_message.pk]
        ).update(
            created_at=old
        )

        result = purge_expired_agent_history()

        self.assertEqual(result["messages"], 1)
        self.assertTrue(Message.objects.filter(pk=admin_message.pk).exists())
        self.assertTrue(Message.objects.filter(pk=second_admin_message.pk).exists())
        self.assertFalse(Message.objects.filter(pk=regular_message.pk).exists())
