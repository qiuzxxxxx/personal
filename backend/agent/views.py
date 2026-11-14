from __future__ import annotations

import json
import logging
from time import monotonic

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from config.streaming import stream_chunks

from .access import (
    assign_owner,
    attachments_for,
    conversation_for,
    conversations_for,
)
from accounts.logging import record as audit_log
from .crypto import decrypt_secret, encrypt_secret
from .endpoints import LLMError, model_url, origin
from .llm import check_model_connection, provider_family, stream_completion
from .models import AgentAttachment, Conversation, Message, UserApiConfig
from .parsing import MAX_ATTACHMENT_BYTES, AttachmentError, parse_attachment
from .permissions import CanUseAgent
from .serializers import (
    AgentAttachmentSerializer,
    ChatRequestSerializer,
    ConnectionTestSerializer,
    ConversationDetailSerializer,
    ConversationSummarySerializer,
    MessageSerializer,
    UserApiConfigSerializer,
    attachment_ref,
)

logger = logging.getLogger(__name__)

# 内置默认模型接口：未在设置中保存自己的 Key 时，服务端使用该 Key 调用
# DeepSeek 原生多模态模型（deepseek-flash = DeepSeek-V4.1-Flash，支持图像输入）。
BUILTIN_LLM_BASE_URL = "https://api.deepseek.com"
BUILTIN_LLM_MODEL = "deepseek-flash"


def _sse(event: str, payload: dict) -> str:
    data = json.dumps({"type": event, **payload}, ensure_ascii=False)
    return f"data: {data}\n\n"


@api_view(["GET", "POST"])
@permission_classes([CanUseAgent])
def conversations(request):
    if request.method == "GET":
        queryset = conversations_for(request).prefetch_related("messages")
        return Response(ConversationSummarySerializer(queryset, many=True).data)

    conversation = assign_owner(
        Conversation(title=str(request.data.get("title") or "新对话")[:120]),
        request,
    )
    conversation.save()
    return Response(
        ConversationSummarySerializer(conversation).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "DELETE"])
@permission_classes([CanUseAgent])
def conversation_detail(request, conversation_id):
    conversation = conversation_for(request, conversation_id)
    if conversation is None:
        return Response({"detail": "对话不存在。"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        conversation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(ConversationDetailSerializer(conversation).data)


@api_view(["GET"])
@permission_classes([CanUseAgent])
def conversation_messages(request, conversation_id):
    conversation = conversation_for(request, conversation_id)
    if conversation is None:
        return Response({"detail": "对话不存在。"}, status=status.HTTP_404_NOT_FOUND)
    messages = conversation.messages.all()
    return Response(MessageSerializer(messages, many=True).data)


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([CanUseAgent])
def upload_attachment(request):
    upload = request.FILES.get("file")
    if upload is None:
        return Response({"detail": "请选择要上传的文件。"}, status=400)
    if upload.size > MAX_ATTACHMENT_BYTES:
        return Response({"detail": "文件超过 25 MB，请压缩后重试。"}, status=413)

    try:
        raw = upload.read()
        metadata = parse_attachment(upload.name or "file", upload.content_type or "", raw)
    except AttachmentError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    attachment = AgentAttachment(
        original_name=metadata["original_name"],
        mime_type=metadata["mime_type"],
        file_size=metadata["file_size"],
        extracted_text=metadata["extracted_text"],
        is_image=metadata["is_image"],
    )
    assign_owner(attachment, request)
    attachment.file.save(metadata["original_name"], ContentFile(raw), save=False)
    attachment.save()
    return Response(
        AgentAttachmentSerializer(attachment).data,
        status=status.HTTP_201_CREATED,
    )


def _friendly_stream_error(exc: Exception) -> str:
    if isinstance(exc, LLMError):
        return str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "模型响应超时，请稍后重试或更换接口地址。"
    if isinstance(exc, httpx.RequestError):
        return "无法连接到模型接口，请检查 Base URL 和网络后重试。"
    return "生成回复时出现意外错误，请稍后重试。"


@api_view(["GET", "PUT"])
@permission_classes([CanUseAgent])
def api_config_view(request):
    """Read / save the caller's model endpoint config.

    GET returns only masked metadata (has_key + key_hint). PUT encrypts a
    newly supplied key server-side; an empty api_key keeps the stored one,
    and clear_key removes it. The plaintext key never leaves this process.
    """
    config = UserApiConfig.objects.filter(user=request.user).first()

    if request.method == "GET":
        if config is None:
            response = Response(
                {
                    "provider": "deepseek",
                    "base_url": BUILTIN_LLM_BASE_URL,
                    "model": BUILTIN_LLM_MODEL,
                    "system_prompt": "",
                    "has_key": False,
                    "key_hint": "",
                    "updated_at": None,
                }
            )
        else:
            response = Response(UserApiConfigSerializer(config).data)
        response["Cache-Control"] = "no-store"
        return response

    data = request.data or {}
    base_url = str(data.get("base_url") or "").strip()
    model = str(data.get("model") or "").strip()
    if not base_url or not model:
        return Response(
            {"detail": "请填写 Base URL 与模型名称。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        next_origin = origin(model_url(base_url))
    except LLMError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if len(base_url) > 500:
        return Response(
            {"detail": "Base URL 不能超过 500 个字符。"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_key = str(data.get("api_key") or "").strip()
    clear_key = data.get("clear_key") is True
    if config and config.api_key_cipher and not (new_key or clear_key):
        try:
            same_origin = origin(model_url(config.base_url)) == next_origin
        except LLMError:
            same_origin = False
        if not same_origin:
            return Response(
                {"detail": "更换模型接口来源时，请填写新密钥或清除已保存的密钥。"},
                status=400,
            )

    if config is None:
        config = UserApiConfig(user=request.user)
    config.provider = str(data.get("provider") or config.provider or "custom")[:32]
    config.base_url = base_url
    config.model = model[:200]
    config.system_prompt = str(data.get("system_prompt") or "")[:12000]

    if clear_key:
        config.api_key_cipher = ""
    elif new_key:
        config.api_key_cipher = encrypt_secret(new_key)
    config.save()
    audit_log(
        request,
        "agent_config_saved",
        user=request.user,
        detail=(
            "key_cleared" if clear_key else "key_updated" if new_key else "fields_only"
        ),
    )

    response = Response(UserApiConfigSerializer(config).data)
    response["Cache-Control"] = "no-store"
    return response


def _merge_saved_config(
    request, api_config: dict, *, ignore_saved_key: bool = False
) -> tuple[dict, str | None]:
    """Inject the server-side decrypted key; returns (config, error)."""
    api_config.pop("use_saved", None)
    saved = UserApiConfig.objects.filter(user=request.user).first()

    api_config["base_url"] = (
        str(api_config.get("base_url") or "").strip()
        or (saved.base_url if saved else "")
        or BUILTIN_LLM_BASE_URL
    )
    api_config["model"] = (
        str(api_config.get("model") or "").strip()
        or (saved.model if saved else "")
        or BUILTIN_LLM_MODEL
    )
    if not api_config.get("provider") and saved:
        api_config["provider"] = saved.provider
    if not api_config.get("system_prompt") and saved and saved.system_prompt:
        api_config["system_prompt"] = saved.system_prompt

    try:
        url = model_url(api_config["base_url"])
        if not str(api_config.get("api_key") or "").strip():
            if (
                not ignore_saved_key
                and saved
                and saved.api_key_cipher
                and origin(model_url(saved.base_url)) == origin(url)
            ):
                api_config["api_key"] = decrypt_secret(saved.api_key_cipher)
                if not api_config["api_key"]:
                    return api_config, "无法读取已保存的模型密钥，请在设置中重新填写。"
            elif (
                url == model_url(BUILTIN_LLM_BASE_URL)
                and provider_family(str(api_config.get("provider") or "")) == "openai"
            ):
                api_config["api_key"] = settings.NEXUS_BUILTIN_LLM_API_KEY
    except LLMError as exc:
        return api_config, str(exc)
    return api_config, None


class ConnectionTestThrottle(UserRateThrottle):
    scope = "agent_connection_test"
    rate = "12/min"


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([CanUseAgent])
@throttle_classes([ConnectionTestThrottle])
def test_connection(request):
    serializer = ConnectionTestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    config = dict(serializer.validated_data)
    ignore_saved_key = config.pop("clear_key")
    config, error = _merge_saved_config(request, config, ignore_saved_key=ignore_saved_key)
    if error:
        return Response({"detail": error}, status=400)

    started = monotonic()
    try:
        check_model_connection(config)
    except httpx.TimeoutException as exc:
        return Response({"detail": _friendly_stream_error(exc)}, status=504)
    except (LLMError, httpx.HTTPError) as exc:
        return Response({"detail": _friendly_stream_error(exc)}, status=502)
    except (ValueError, TypeError, AttributeError, IndexError):
        return Response({"detail": "接口返回的格式无效，请检查所选服务商与 Base URL。"}, status=502)

    return Response(
        {"latency_ms": round((monotonic() - started) * 1000)},
        headers={"Cache-Control": "no-store"},
    )


@api_view(["POST"])
@parser_classes([JSONParser])
@permission_classes([CanUseAgent])
def chat(request):
    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data
    content = str(payload.get("message") or "").strip()
    attachment_ids = [str(item) for item in payload.get("attachment_ids", [])]
    api_config, config_error = _merge_saved_config(
        request, dict(payload["api_config"])
    )
    if config_error:
        return Response({"detail": config_error}, status=status.HTTP_400_BAD_REQUEST)

    conversation = None
    if payload.get("conversation_id"):
        conversation = conversation_for(request, payload["conversation_id"])
        if conversation is None:
            return Response({"detail": "对话不存在。"}, status=status.HTTP_404_NOT_FOUND)
    if conversation is None:
        conversation = assign_owner(Conversation(title="新对话"), request)
        conversation.save()

    attachments_queryset = attachments_for(request).filter(id__in=attachment_ids)
    attachment_map = {str(item.id): item for item in attachments_queryset}
    if len(attachment_map) != len(set(attachment_ids)):
        return Response(
            {"detail": "有附件已失效，请重新上传。"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    current_attachments = [
        attachment_map[item] for item in attachment_ids if item in attachment_map
    ]

    if not content and not current_attachments:
        return Response({"detail": "请输入消息或选择附件。"}, status=400)

    attachment_refs = [attachment_ref(item) for item in current_attachments]
    user_message = Message.objects.create(
        conversation=conversation,
        role="user",
        content=content,
        attachments=attachment_refs,
    )

    if not conversation.title or conversation.title == "新对话":
        title_source = content or (
            current_attachments[0].original_name if current_attachments else "新对话"
        )
        conversation.title = title_source.replace("\n", " ").strip()[:42] or "新对话"
    conversation.save()

    conversation_id = str(conversation.id)
    user_payload = MessageSerializer(user_message).data
    title = conversation.title

    def event_stream():
        close_old_connections()
        yield _sse(
            "meta",
            {
                "conversation_id": conversation_id,
                "title": title,
                "user_message": user_payload,
                "provider": provider_family(str(api_config.get("provider", ""))),
            },
        )

        parts: list[str] = []
        assistant_message = None
        error_message = None
        try:
            for delta in stream_completion(
                api_config,
                conversation,
                user_message,
                current_attachments,
            ):
                if not delta:
                    continue
                parts.append(delta)
                yield _sse("delta", {"content": delta})

            answer = "".join(parts).strip()
            if not answer:
                raise LLMError("模型没有返回任何内容，请检查接口与模型名称。")
            assistant_message = Message.objects.create(
                conversation=conversation,
                role="assistant",
                content=answer,
            )
            conversation.save(update_fields=["updated_at"])
            yield _sse(
                "done",
                {"message": MessageSerializer(assistant_message).data},
            )
        except GeneratorExit:
            raise
        except Exception as exc:  # noqa: BLE001 - converted into a safe SSE error
            error_message = _friendly_stream_error(exc)
            if isinstance(exc, (LLMError, httpx.HTTPError)):
                logger.warning("Agent stream failed (%s)", type(exc).__name__)
            else:
                logger.error("Agent stream crashed (%s)", type(exc).__name__)
            partial = "".join(parts).strip()
            if partial:
                assistant_message = Message.objects.create(
                    conversation=conversation,
                    role="assistant",
                    content=partial,
                )
                conversation.save(update_fields=["updated_at"])
            yield _sse(
                "error",
                {
                    "message": error_message,
                    "partial_message": (
                        MessageSerializer(assistant_message).data
                        if assistant_message
                        else None
                    ),
                },
            )
        finally:
            close_old_connections()

    response = StreamingHttpResponse(
        stream_chunks(request, event_stream()), content_type="text/event-stream; charset=utf-8"
    )
    response["Cache-Control"] = "no-store, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
