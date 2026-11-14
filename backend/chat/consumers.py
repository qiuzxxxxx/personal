from __future__ import annotations

import json
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .models import CHAT_USERNAMES, ChatMessage
from .serializers import ChatMessageSerializer

GROUP_NAME = "chat_pair"
CHAT_PROTOCOL = "zixxx.chat"
TOKEN_PROTOCOL = re.compile(r"token\.([0-9a-f]{40})")
MAX_FRAME_BYTES = 32 * 1024


def _partner_for(user: User) -> User | None:
    other = "sqx" if user.username == "qzx" else "qzx"
    return User.objects.filter(username=other, is_active=True).first()


@database_sync_to_async
def user_from_token(token: str):
    if not token:
        return None
    record = Token.objects.select_related("user").filter(key=token).first()
    if record is None or not record.user.is_active:
        return None
    if record.user.username not in CHAT_USERNAMES:
        return None
    return record.user


@database_sync_to_async
def create_text_message(user: User, content: str):
    partner = _partner_for(user)
    if partner is None:
        return None
    message = ChatMessage.objects.create(
        sender=user,
        recipient=partner,
        message_type="text",
        content=content,
    )
    return ChatMessageSerializer(message).data


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
        self.group_name = GROUP_NAME
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept(subprotocol=CHAT_PROTOCOL)
        await self.send_json(
            {
                "type": "connected",
                "username": self.user.username,
                "partner": (
                    "sqx" if self.user.username == "qzx" else "qzx"
                ),
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
                    {"type": "error", "message": "消息不能为空。"}
                )
                return
            if len(text) > 5000:
                await self.send_json(
                    {"type": "error", "message": "消息不能超过 5000 个字符。"}
                )
                return
            payload = await create_text_message(self.user, text)
            if payload is None:
                await self.send_json(
                    {"type": "error", "message": "对方账号尚未初始化。"}
                )
                return
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "chat.message", "message": payload},
            )
        elif action == "typing":
            await self.channel_layer.group_send(
                self.group_name,
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
