"""Knowledge base APIs: collections, documents, search and personal memories.

Every endpoint is owner scoped. The owner always comes from the request token;
clients can never choose it, and a guest account (yk) has no access.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from agent.permissions import CanUseAgent
from config.http import BadRequest, error, no_store, paginate, parse_int

from agent.models import Conversation, Message

from workspace.models import DailyEntry, Material, Project

from .context import build_context
from .ingestion import IngestionError, create_document, next_revision_no
from .jobs import reindex_document
from .memories import (
    MemoryError,
    accept_memory,
    create_memory,
    current_epoch,
    disable_memory,
    export_memories,
    forget_memory,
    update_memory,
)
from .models import (
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeIndexJob,
    KnowledgeRevision,
    KnowledgeWriteIntent,
    MessageCitation,
    PersonalMemory,
)
from .search import search
from .serializers import (
    KnowledgeCollectionSerializer,
    KnowledgeDocumentPatchSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeDocumentWriteSerializer,
    KnowledgeImportSerializer,
    KnowledgeRevisionSerializer,
    MemoryPatchSerializer,
    MemorySerializer,
    MemoryWriteSerializer,
)


def serializer_error(serializer) -> Response:
    detail = serializer.errors
    first = ""
    if isinstance(detail, dict):
        for key, value in detail.items():
            if isinstance(value, (list, tuple)) and value:
                first = f"{key}: {value[0]}"
                break
            first = str(value)
            break
    elif isinstance(detail, (list, tuple)) and detail:
        first = str(detail[0])
    return error(first or "请求参数无效。", 400, code="invalid_payload")


def collection_queryset(request):
    queryset = KnowledgeCollection.objects.filter(owner=request.user)
    raw = request.query_params.get("deleted", "")
    if str(raw).lower() in {"1", "true", "yes"}:
        return queryset.filter(deleted_at__isnull=False)
    return queryset.filter(deleted_at__isnull=True)


def document_queryset(request):
    queryset = KnowledgeDocument.objects.filter(owner=request.user)
    raw = request.query_params.get("deleted", "")
    if str(raw).lower() in {"1", "true", "yes"}:
        return queryset.filter(deleted_at__isnull=False)
    return queryset.filter(deleted_at__isnull=True)


def resolve_collection(owner, collection_id):
    if not collection_id:
        return None
    collection = KnowledgeCollection.objects.filter(
        pk=collection_id, owner=owner, deleted_at__isnull=True
    ).first()
    if collection is None:
        raise BadRequest("知识集合不存在或不属于当前账号。")
    return collection


def resolve_project(owner, project_id):
    if not project_id:
        return None
    project = Project.objects.filter(pk=project_id, owner=owner).first()
    if project is None:
        raise BadRequest("项目不存在或不属于当前账号。")
    return project


# --------------------------------------------------------------------------- #
# collections
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseAgent])
def collection_list(request):
    if request.method == "GET":
        queryset = collection_queryset(request).annotate(
            document_count=Count(
                "documents", filter=Q(documents__deleted_at__isnull=True), distinct=True
            )
        ).order_by("created_at")
        return no_store(Response(paginate(queryset, request, KnowledgeCollectionSerializer)))

    name = str(request.data.get("name") or "").strip()
    if not name:
        return error("集合名称不能为空。", 400, code="invalid_payload")
    try:
        project = resolve_project(request.user, request.data.get("project"))
    except BadRequest as exc:
        return error(str(exc), 400, code="invalid_payload")
    collection = KnowledgeCollection.objects.create(
        owner=request.user,
        name=name[:120],
        description=str(request.data.get("description") or "")[:2000],
        project=project,
    )
    return Response(KnowledgeCollectionSerializer(collection).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseAgent])
def collection_detail(request, collection_id):
    collection = KnowledgeCollection.objects.filter(pk=collection_id, owner=request.user).first()
    if collection is None:
        return error("知识集合不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(KnowledgeCollectionSerializer(collection).data))

    if request.method == "DELETE":
        # The collection is emptied explicitly; documents are moved to the
        # trash so the original files are never touched.
        now = timezone.now()
        with transaction.atomic():
            KnowledgeDocument.objects.filter(
                owner=request.user, collection=collection, deleted_at__isnull=True
            ).update(deleted_at=now, updated_at=now)
            KnowledgeCollection.objects.filter(pk=collection.pk).update(
                deleted_at=now, version=collection.version + 1, updated_at=now
            )
        collection.refresh_from_db()
        return no_store(Response(KnowledgeCollectionSerializer(collection).data))

    version = request.data.get("version")
    if version is None:
        return error("更新集合必须提交 version。", 400, code="version_required")
    fields: dict = {}
    if "name" in request.data:
        name = str(request.data.get("name") or "").strip()
        if not name:
            return error("集合名称不能为空。", 400, code="invalid_payload")
        fields["name"] = name[:120]
    if "description" in request.data:
        fields["description"] = str(request.data.get("description") or "")[:2000]
    if "project" in request.data:
        try:
            fields["project"] = resolve_project(request.user, request.data.get("project"))
        except BadRequest as exc:
            return error(str(exc), 400, code="invalid_payload")

    updated = KnowledgeCollection.objects.filter(
        pk=collection.pk, owner=request.user, version=version, deleted_at__isnull=True
    ).update(version=version + 1, updated_at=timezone.now(), **fields)
    if not updated:
        current = KnowledgeCollection.objects.filter(
            pk=collection.pk, owner=request.user
        ).first()
        return error(
            "知识集合已被其他设备修改，请刷新后重试。",
            409,
            code="version_conflict",
            current_version=current.version if current else None,
        )
    collection.refresh_from_db()
    return no_store(Response(KnowledgeCollectionSerializer(collection).data))


# --------------------------------------------------------------------------- #
# documents
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseAgent])
def document_list(request):
    if request.method == "GET":
        queryset = document_queryset(request).select_related(
            "collection", "current_revision"
        )
        collection = request.query_params.get("collection")
        if collection:
            queryset = queryset.filter(collection_id=collection)
        keyword = (request.query_params.get("q") or "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(title__icontains=keyword) | Q(manual_body__icontains=keyword)
            )
        source_type = request.query_params.get("source_type")
        if source_type:
            queryset = queryset.filter(source_type=source_type)
        queryset = queryset.annotate(
            chunk_count=Count(
                "chunks", filter=Q(chunks__revision=F("current_revision")), distinct=True
            )
        ).order_by("-updated_at")
        return no_store(Response(paginate(queryset, request, KnowledgeDocumentSerializer)))

    serializer = KnowledgeDocumentWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error(serializer)
    payload = serializer.validated_data
    try:
        collection = resolve_collection(request.user, payload.get("collection"))
    except BadRequest as exc:
        return error(str(exc), 400, code="invalid_payload")

    document = create_document(
        owner=request.user,
        title=payload["title"],
        collection=collection,
        source_type="manual",
        manual_body=payload.get("manual_body") or "",
        content_origin="user_authored",
        ai_enabled=payload.get("ai_enabled", False),
    )
    return Response(KnowledgeDocumentSerializer(document).data, status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([CanUseAgent])
def document_detail(request, document_id):
    document = KnowledgeDocument.objects.filter(
        pk=document_id, owner=request.user
    ).select_related("collection", "current_revision").first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")

    if request.method == "GET":
        return no_store(Response(KnowledgeDocumentSerializer(document).data))

    if request.method == "DELETE":
        if document.deleted_at is None:
            KnowledgeDocument.objects.filter(pk=document.pk).update(
                deleted_at=timezone.now(),
                version=document.version + 1,
                updated_at=timezone.now(),
            )
            document.refresh_from_db()
        return no_store(Response(KnowledgeDocumentSerializer(document).data))

    serializer = KnowledgeDocumentPatchSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error(serializer)
    payload = serializer.validated_data
    version = payload.get("version")
    if version is None:
        return error("更新知识条目必须提交 version。", 400, code="version_required")

    fields: dict = {}
    reindex = False
    if "title" in payload:
        fields["title"] = payload["title"][:200]
    if "collection" in payload:
        try:
            fields["collection"] = resolve_collection(request.user, payload.get("collection"))
        except BadRequest as exc:
            return error(str(exc), 400, code="invalid_payload")
    if "ai_enabled" in payload and payload["ai_enabled"] is not None:
        fields["ai_enabled"] = bool(payload["ai_enabled"])
    if payload.get("manual_body") is not None and document.source_type == "manual":
        fields["manual_body"] = payload["manual_body"]
        reindex = True

    with transaction.atomic():
        updated = KnowledgeDocument.objects.filter(
            pk=document.pk, owner=request.user, version=version, deleted_at__isnull=True
        ).update(version=version + 1, updated_at=timezone.now(), **fields)
        if not updated:
            current = KnowledgeDocument.objects.filter(
                pk=document.pk, owner=request.user
            ).first()
            return error(
                "知识条目已被其他设备修改，请刷新后重试。",
                409,
                code="version_conflict",
                current_version=current.version if current else None,
            )
    document.refresh_from_db()
    if reindex:
        revision = reindex_document(document)
        document.current_revision = revision
    return no_store(Response(KnowledgeDocumentSerializer(document).data))


@api_view(["POST"])
@permission_classes([CanUseAgent])
def document_import(request):
    """Import one own material / journal entry / message as knowledge."""
    serializer = KnowledgeImportSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error(serializer)
    payload = serializer.validated_data

    # Idempotency is keyed on the imported material itself: one material can
    # only produce one active knowledge document.
    material_id = payload.get("material")
    entry_id = payload.get("entry")
    message_id = payload.get("message")
    provided = [item for item in (material_id, entry_id, message_id) if item]
    if len(provided) != 1:
        return error("请指定且只指定一个来源（资料、每日记录或消息）。", 400, code="invalid_payload")

    try:
        collection = resolve_collection(request.user, payload.get("collection"))
    except BadRequest as exc:
        return error(str(exc), 400, code="invalid_payload")

    if material_id:
        material = Material.objects.filter(pk=material_id, owner=request.user).first()
        if material is None:
            return error("资料不存在或不属于当前账号。", 404, code="not_found")
        if material.deleted_at is not None:
            return error("资料已移入回收站，无法加入知识库。", 400, code="source_deleted")
        if KnowledgeDocument.objects.filter(
            owner=request.user, source_material=material, deleted_at__isnull=True
        ).exists():
            return error("该资料已经加入知识库。", 400, code="duplicate_document")
        document = create_document(
            owner=request.user,
            title=str(payload.get("title") or material.original_name)[:200],
            collection=collection,
            source_type="material",
            content_origin="source_snapshot",
            ai_enabled=payload.get("ai_enabled", False),
            source_material=material,
            source_version=material.version,
            source_title=material.original_name,
        )
        return Response(KnowledgeDocumentSerializer(document).data, status=201)

    if entry_id:
        entry = DailyEntry.objects.filter(pk=entry_id, owner=request.user).first()
        if entry is None:
            return error("每日记录不存在或不属于当前账号。", 404, code="not_found")
        document = create_document(
            owner=request.user,
            title=str(payload.get("title") or f"每日记录 {entry.date.isoformat()}")[:200],
            collection=collection,
            source_type="journal_entry",
            content_origin="source_snapshot",
            ai_enabled=payload.get("ai_enabled", False),
            source_entry=entry,
            source_version=entry.version,
            source_date=entry.date,
        )
        return Response(KnowledgeDocumentSerializer(document).data, status=201)

    message = Message.objects.filter(
        pk=message_id, conversation__user=request.user
    ).first()
    if message is None:
        return error("消息不存在或不属于当前账号。", 404, code="not_found")
    document = create_document(
        owner=request.user,
        title=str(payload.get("title") or message.content[:60])[:200],
        collection=collection,
        source_type="ai_message",
        content_origin="ai_generated",
        ai_enabled=payload.get("ai_enabled", False),
        source_message=message,
        source_version=1,
        source_title=message.content[:120],
    )
    return Response(KnowledgeDocumentSerializer(document).data, status=201)


@api_view(["POST"])
@permission_classes([CanUseAgent])
def document_reindex(request, document_id):
    document = KnowledgeDocument.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")
    revision = reindex_document(document)
    document.refresh_from_db()
    return Response(
        {
            "document": KnowledgeDocumentSerializer(document).data,
            "revision": KnowledgeRevisionSerializer(revision).data,
        }
    )


@api_view(["POST"])
@permission_classes([CanUseAgent])
def document_restore(request, document_id):
    document = KnowledgeDocument.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")
    if document.deleted_at is None:
        return no_store(Response(KnowledgeDocumentSerializer(document).data))
    KnowledgeDocument.objects.filter(pk=document.pk).update(
        deleted_at=None, version=document.version + 1, updated_at=timezone.now()
    )
    document.refresh_from_db()
    return no_store(Response(KnowledgeDocumentSerializer(document).data))


@api_view(["POST"])
@permission_classes([CanUseAgent])
def document_purge(request, document_id):
    """Permanently remove the knowledge copy. The source file is untouched."""
    document = KnowledgeDocument.objects.filter(pk=document_id, owner=request.user).first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")
    KnowledgeChunk.objects.filter(document=document).delete()
    KnowledgeIndexJob.objects.filter(document=document).delete()
    KnowledgeRevision.objects.filter(document=document).delete()
    document.delete()
    return no_store(Response({"purged": True, "id": str(document_id)}))


@api_view(["GET"])
@permission_classes([CanUseAgent])
def document_status(request, document_id):
    document = KnowledgeDocument.objects.filter(
        pk=document_id, owner=request.user
    ).select_related("current_revision").first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")
    revision = document.current_revision
    job = (
        KnowledgeIndexJob.objects.filter(document=document)
        .order_by("-created_at")
        .first()
    )
    return no_store(
        Response(
            {
                "id": str(document.id),
                "index_status": document.index_status,
                "ai_enabled": document.ai_enabled,
                "revision": KnowledgeRevisionSerializer(revision).data if revision else None,
                "job": {
                    "status": job.status,
                    "attempts": job.attempts,
                    "last_error": job.last_error,
                }
                if job
                else None,
            }
        )
    )


@api_view(["GET"])
@permission_classes([CanUseAgent])
def document_source(request, document_id):
    """Return the located source text of the current revision."""
    document = KnowledgeDocument.objects.filter(
        pk=document_id, owner=request.user
    ).select_related("current_revision").first()
    if document is None:
        return error("知识条目不存在。", 404, code="not_found")
    revision = document.current_revision
    body = revision.body if revision else ""
    return no_store(
        Response(
            {
                "id": str(document.id),
                "title": document.title,
                "source_type": document.source_type,
                "source_title": document.source_title,
                "revision_no": revision.revision_no if revision else 0,
                "index_status": document.index_status,
                "body": body[:200000],
            }
        )
    )


# --------------------------------------------------------------------------- #
# search
# --------------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([CanUseAgent])
def search_view(request):
    payload = request.data if isinstance(request.data, dict) else {}
    query = str(payload.get("query") or "").strip()
    scope = str(payload.get("scope") or "all")
    collection_ids = payload.get("collection_ids") or []
    if not isinstance(collection_ids, list):
        return error("collection_ids 必须是数组。", 400, code="invalid_payload")
    if scope not in {"all", "collections"}:
        return error("scope 只能是 all 或 collections。", 400, code="invalid_payload")
    limit = parse_int(payload.get("limit") or 6, "limit", 1, 20)

    owned = set(
        str(item)
        for item in KnowledgeCollection.objects.filter(
            owner=request.user, deleted_at__isnull=True
        ).values_list("id", flat=True)
    )
    for collection_id in collection_ids:
        if str(collection_id) not in owned:
            return error("知识集合不存在或不属于当前账号。", 400, code="invalid_scope")

    hits, effective_scope = search(
        request.user,
        query,
        collection_ids=[str(item) for item in collection_ids],
        scope=scope,
        limit=limit,
        for_ai=False,
    )
    matches = []
    for index, hit in enumerate(hits, start=1):
        item = hit.as_dict()
        item["source_id"] = f"S{index}"
        matches.append(item)
    return no_store(
        Response(
            {
                "matches": matches,
                "source_refs": [item["source_id"] for item in matches],
                "index_warnings": [],
                "scope": effective_scope,
                "count": len(matches),
            }
        )
    )


# --------------------------------------------------------------------------- #
# personal memories
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([CanUseAgent])
def memory_list(request):
    if request.method == "GET":
        queryset = PersonalMemory.objects.filter(owner=request.user)
        raw = request.query_params.get("deleted", "")
        if str(raw).lower() in {"1", "true", "yes"}:
            queryset = queryset.filter(deleted_at__isnull=False)
        else:
            queryset = queryset.filter(deleted_at__isnull=True)
        status = request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        queryset = queryset.select_related("project").order_by("-updated_at")
        return no_store(Response(paginate(queryset, request, MemorySerializer)))

    serializer = MemoryWriteSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error(serializer)
    payload = serializer.validated_data
    try:
        project = resolve_project(request.user, payload.get("project"))
        memory = create_memory(
            request.user,
            key=payload["key"],
            content=payload["content"],
            kind=payload["kind"],
            scope_type=payload["scope_type"],
            project=project,
            evidence_type=payload["evidence_type"],
            source_ref=payload.get("source_ref") or "",
            status="active",
        )
    except MemoryError as exc:
        return error(exc.detail, 400, code=exc.code)
    return Response(MemorySerializer(memory).data, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([CanUseAgent])
def memory_detail(request, memory_id):
    memory = PersonalMemory.objects.filter(
        pk=memory_id, owner=request.user
    ).select_related("project").first()
    if memory is None:
        return error("记忆不存在。", 404, code="not_found")
    if request.method == "GET":
        return no_store(Response(MemorySerializer(memory).data))

    serializer = MemoryPatchSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_error(serializer)
    payload = serializer.validated_data
    changes = {key: value for key, value in payload.items() if key != "version"}
    if "project" in changes:
        try:
            changes["project"] = resolve_project(request.user, changes["project"])
        except BadRequest as exc:
            return error(str(exc), 400, code="invalid_payload")
    try:
        memory = update_memory(
            memory, expected_version=payload["version"], changes=changes
        )
    except MemoryError as exc:
        status = 409 if exc.code == "version_conflict" else 400
        return error(exc.detail, status, code=exc.code)
    return no_store(Response(MemorySerializer(memory).data))


def _memory_action(request, memory_id, action: str):
    memory = PersonalMemory.objects.filter(pk=memory_id, owner=request.user).first()
    if memory is None:
        return error("记忆不存在。", 404, code="not_found")
    version = request.data.get("version") if isinstance(request.data, dict) else None
    if version is None:
        return error("该操作必须提交 version。", 400, code="version_required")
    try:
        if action == "accept":
            memory = accept_memory(memory, expected_version=int(version))
        elif action == "disable":
            memory = disable_memory(memory, expected_version=int(version))
        else:
            memory = forget_memory(memory, expected_version=int(version))
    except MemoryError as exc:
        status = 409 if exc.code == "version_conflict" else 400
        return error(exc.detail, status, code=exc.code)
    return no_store(Response(MemorySerializer(memory).data))


@api_view(["POST"])
@permission_classes([CanUseAgent])
def memory_accept(request, memory_id):
    return _memory_action(request, memory_id, "accept")


@api_view(["POST"])
@permission_classes([CanUseAgent])
def memory_disable(request, memory_id):
    return _memory_action(request, memory_id, "disable")


@api_view(["POST"])
@permission_classes([CanUseAgent])
def memory_forget(request, memory_id):
    return _memory_action(request, memory_id, "forget")


# --------------------------------------------------------------------------- #
# write intents, citations and export
# --------------------------------------------------------------------------- #
@api_view(["POST"])
@permission_classes([CanUseAgent])
def write_intent(request):
    """Create a limited, user triggered write permission."""
    payload = request.data if isinstance(request.data, dict) else {}
    target = str(payload.get("target") or "").strip()
    if target not in {"memory", "note"}:
        return error("target 只能是 memory 或 note。", 400, code="invalid_payload")
    idempotency_key = str(payload.get("idempotency_key") or "").strip()
    if not idempotency_key:
        return error("缺少 idempotency_key。", 400, code="invalid_payload")
    existing = KnowledgeWriteIntent.objects.filter(
        owner=request.user, idempotency_key=idempotency_key
    ).first()
    if existing is not None:
        return Response(
            {
                "id": str(existing.id),
                "target": existing.target,
                "expires_at": existing.expires_at.isoformat(),
                "payload": existing.payload,
            }
        )

    # The conversation must be a real conversation of the current account.
    conversation = None
    raw_conversation = payload.get("conversation")
    if raw_conversation:
        try:
            conversation = Conversation.objects.filter(
                pk=raw_conversation, user=request.user
            ).first()
        except (ValueError, TypeError, DjangoValidationError):
            return error("conversation 不是合法的会话标识。", 400, code="invalid_payload")
        if conversation is None:
            return error("会话不存在或不属于当前账号。", 400, code="invalid_conversation")

    intent = KnowledgeWriteIntent.objects.create(
        owner=request.user,
        conversation=conversation,
        target=target,
        payload=payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
        expires_at=timezone.now() + timezone.timedelta(minutes=10),
        idempotency_key=idempotency_key[:64],
    )
    return Response(
        {
            "id": str(intent.id),
            "target": intent.target,
            "expires_at": intent.expires_at.isoformat(),
            "payload": intent.payload,
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([CanUseAgent])
def citation_detail(request, citation_id):
    citation = MessageCitation.objects.filter(
        pk=citation_id, owner=request.user
    ).select_related("document", "revision", "chunk").first()
    if citation is None:
        return error("引用不存在或不属于当前账号。", 404, code="not_found")
    if citation.source_type == "workspace":
        # A task citation is a snapshot of the moment the question was asked.
        return no_store(
            Response(
                {
                    "id": str(citation.id),
                    "status": "snapshot",
                    "source_id": citation.source_id,
                    "source_type": citation.source_type,
                    "title": citation.locator.get("title", ""),
                    "text": citation.snapshot_text,
                    "detail": "这是查询当时的任务快照，任务当前状态请以工作台为准。",
                }
            )
        )
    document = citation.document
    if document is None or document.deleted_at is not None:
        return no_store(
            Response(
                {
                    "id": str(citation.id),
                    "status": "unavailable",
                    "source_id": citation.source_id,
                    "detail": "来源已不可用。",
                }
            )
        )
    revision = citation.revision
    current = document.current_revision
    status = "available"
    detail = ""
    if current is None or revision is None or current.pk != revision.pk:
        status = "source_updated"
        detail = "来源已更新，以下为当时的片段。"
    return no_store(
        Response(
            {
                "id": str(citation.id),
                "status": status,
                "source_id": citation.source_id,
                "source_type": citation.source_type,
                "title": document.title,
                "document_id": str(document.id),
                "revision_no": revision.revision_no if revision else 0,
                "heading_path": citation.locator.get("heading_path", ""),
                "page_start": citation.locator.get("page_start"),
                "page_end": citation.locator.get("page_end"),
                "text": citation.chunk.text if citation.chunk_id else citation.snapshot_text,
                "detail": detail,
            }
        )
    )


@api_view(["GET"])
@permission_classes([CanUseAgent])
def export_view(request):
    """Export the owner's notes, memories and source list."""
    documents = KnowledgeDocument.objects.filter(
        owner=request.user, deleted_at__isnull=True
    ).select_related("collection", "current_revision")
    payload = {
        "exported_at": timezone.now().isoformat(),
        "context_epoch": current_epoch(request.user),
        "collections": [
            {"id": str(item.id), "name": item.name}
            for item in KnowledgeCollection.objects.filter(
                owner=request.user, deleted_at__isnull=True
            )
        ],
        "documents": [
            {
                "id": str(item.id),
                "title": item.title,
                "collection": str(item.collection_id or ""),
                "source_type": item.source_type,
                "ai_enabled": item.ai_enabled,
                "index_status": item.index_status,
                # Imported sources keep their body in the parsed revision.
                "body": item.manual_body
                or (item.current_revision.body if item.current_revision_id else ""),
                "updated_at": item.updated_at.isoformat(),
            }
            for item in documents
        ],
        "memories": export_memories(request.user),
    }
    return no_store(Response(payload))
