from django.core.management.base import BaseCommand

from agent.retention import purge_expired_agent_history


class Command(BaseCommand):
    help = "清理非管理员账号超过 24 小时的 AI 聊天记录与无引用附件。"

    def handle(self, *args, **options):
        agent_counts = purge_expired_agent_history()
        self.stdout.write(
            self.style.SUCCESS(
                "清理完成：AI 消息 {messages} 条，AI 会话 {conversations} 个，"
                "AI 附件 {attachments} 个。".format(**agent_counts)
            )
        )
