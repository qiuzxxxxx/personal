from __future__ import annotations

import json
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .models import ChatMessage
from .serializers import ChatMessageSerializer
from .permissions import can_chat_with, is_chat_user
from accounts.permissions import is_super_admin

CHAT_PROTOCOL = "zixxx.chat"
TOKEN_PROTOCOL = re.compile(r"token\.([0-9a-f]{40})")
MAX_FRAME_BYTES = 32 * 1024


def _partner_for(user: User, username: str | None) -> User | None:
    if is_super_admin(user):
        partner = User.objects.filter(username=username, is_active=True).first() if username else None
    else:
        partner = User.objects.filter(username="qzx", is_active=True).first()
    return partner if partner and can_chat_with(user, partner) else None


@database_sync_to_async
def user_from_token(token: str):
    if not token:
        return None
    record = Token.objects.select_related("user").filter(key=token).first()
    if record is None or not record.user.is_active or not is_chat_user(record.user):
        return None
    return record.user


@database_sync_to_async
def create_text_message(user: User, partner_name: str, content: str):
    partner = _partner_for(user, partner_name)
    if partner is None:
        return None
    message = ChatMessage.objects.create(
        sender=user,
        recipient=partner,
        message_type="text",
        content=content,
    )
    return ChatMessageSerializer(message).data


@database_sync_to_async
def partner_id_for(user: User, partner_name: str) -> int | None:
    partner = _partner_for(user, partner_name)
    return partner.pk if partner else None


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        protocols = self.scope.get("subprotocols", [])
        match = TOKEN_PROTOCOL.fullmatch(protocols[1]) if len(protocols) == 2 else None
        if not match or protocols[0] != CHAT_PROTOCOL:
            await self.close(code=4401)
            return
        self.token = match[1]
        self.user = await user_from_token(self.token)
        if self.user is None:
            await self.close(code=4401)
            return
        self.group_name = f"chat_user_{self.user.pk}"
        partner_name = self.scope.get("query_string", b"").decode("utf-8")
        from urllib.parse import parse_qs
        self.partner_name = parse_qs(partner_name).get("with", [""])[0]
        if self.partner_name and await self.partner_valid() is False:
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept(subprotocol=CHAT_PROTOCOL)
        await self.send_json(
            {
                "type": "connected",
                "username": self.user.username,
                "partner": self.partner_name,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

    async def session_valid(self):
        user = await user_from_token(self.token)
        if user is not None and user.pk == self.user.pk:
            return True
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        await self.close(code=4401)
        return False

    @database_sync_to_async
    def partner_valid(self):
        partner = _partner_for(self.user, self.partner_name)
        return partner is not None

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if text_data is None or len(text_data.encode("utf-8")) > MAX_FRAME_BYTES:
            await self.close(code=1009)
            return
        try:
            content = json.loads(text_data)
        except (ValueError, RecursionError):
            await self.send_json({"type": "error", "message": "消息格式无效。"})
            return
        await self.receive_json(content)

    async def receive_json(self, content, **kwargs):
        if not await self.session_valid():
            return
        if not isinstance(content, dict):
            return
        action = content.get("type")
        if action in ("message.send", "message"):
            raw = content.get("content")
            text = raw.strip() if isinstance(raw, str) else ""
            if not text:
                await self.send_json(
                    {"type": "error", "message": "留言不能为空。"}
                )
                return
            if len(text) > 5000:
                await self.send_json(
                    {"type": "error", "message": "留言不能超过 5000 个字符。"}
                )
                return
            payload = await create_text_message(self.user, self.partner_name, text)
            if payload is None:
                await self.send_json(
                    {"type": "error", "message": "对方账号尚未初始化。"}
                )
                return
            recipient_id = await partner_id_for(self.user, self.partner_name)
            if recipient_id is None:
                await self.send_json({"type": "error", "message": "聊天对象不可用。"})
                return
            await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "message": payload})
            await self.channel_layer.group_send(f"chat_user_{recipient_id}", {"type": "chat.message", "message": payload})
        elif action == "typing":
            partner_id = await partner_id_for(self.user, self.partner_name)
            if partner_id is None:
                return
            await self.channel_layer.group_send(
                f"chat_user_{partner_id}",
                {
                    "type": "chat.typing",
                    "username": self.user.username,
                    "is_typing": bool(content.get("is_typing")),
                },
            )
        elif action == "ping":
            await self.send_json({"type": "pong"})
        else:
            await self.send_json(
                {"type": "error", "message": "无法识别的消息类型。"}
            )

    async def chat_message(self, event):
        if await self.session_valid():
            await self.send_json({"type": "message", "message": event["message"]})

    async def chat_deleted(self, event):
        if await self.session_valid():
            await self.send_json(
                {"type": "message.deleted", "message_id": event["message_id"]}
            )

    async def chat_cleared(self, event):
        if await self.session_valid():
            await self.send_json(
                {"type": "conversation.cleared", "partner": event["partner"]}
            )

    async def chat_typing(self, event):
        if not await self.session_valid():
            return
        await self.send_json(
            {
                "type": "typing",
                "username": event["username"],
                "is_typing": event["is_typing"],
            }
        )
