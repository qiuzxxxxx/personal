"""Unified keyword search over knowledge chunks.

The first release uses a deterministic, dependency-free Chinese keyword
scorer: CJK runs are cut into bigrams, latin words are normalised to lower
case. Retrieval is always restricted in the database to the owner, the
requested scope, non-deleted documents and the current ready revision before
any ranking happens.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from django.db.models import Q

from .models import KnowledgeChunk, KnowledgeDocument

MAX_QUERY_CHARS = 200
MAX_TERMS = 24
MAX_CANDIDATES = 800
DEFAULT_LIMIT = 6
MAX_PER_DOCUMENT = 3

CJK_RANGE = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_TOKEN_RE = re.compile(rf"[{CJK_RANGE}]+|[A-Za-z0-9_]+")


@dataclass
class SearchHit:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    reason: str
    matched_terms: list[str] = field(default_factory=list)

    @property
    def document_id(self) -> str:
        return str(self.document.id)

    @property
    def chunk_id(self) -> str:
        return str(self.chunk.id)

    def as_dict(self) -> dict:
        return {
            "source_id": "",
            "document_id": self.document_id,
            "title": self.document.title,
            "collection_id": str(self.document.collection_id or ""),
            "revision_no": self.document.current_revision.revision_no
            if self.document.current_revision_id
            else 0,
            "heading_path": self.chunk.heading_path,
            "page_start": self.chunk.page_start,
            "page_end": self.chunk.page_end,
            "char_start": self.chunk.char_start,
            "char_end": self.chunk.char_end,
            "score": round(self.score, 3),
            "reason": self.reason,
            "matched_terms": self.matched_terms,
            "text": self.chunk.text,
        }


def _is_cjk(char: str) -> bool:
    return "\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def tokenize(query: str) -> list[str]:
    """Split a query into CJK bigrams, single CJK characters and latin words.

    A CJK run of two or more characters is cut into bigrams only. Single
    characters are far too noisy on their own, so they are only used when the
    whole query is one character.
    """
    strong: list[str] = []
    for match in _TOKEN_RE.findall(query or ""):
        if _is_cjk(match[0]):
            if len(match) == 1:
                strong.append(match)
                continue
            for index in range(len(match) - 1):
                strong.append(match[index : index + 2])
        else:
            strong.append(match.lower())
    return _unique(strong)[:MAX_TERMS]


def score_text(text: str, terms: list[str]) -> tuple[float, list[str]]:
    """Score a body against the query terms."""
    if not text:
        return 0.0, []
    lowered = text.lower()
    score = 0.0
    matched: list[str] = []
    for term in terms:
        count = lowered.count(term)
        if not count:
            continue
        matched.append(term)
        weight = 2.0 if len(term) >= 2 else 0.6
        score += weight * (1 + min(count, 5) * 0.2)
    return score, matched


def scope_queryset(owner, *, collection_ids=None, scope: str = "all", for_ai: bool = False):
    """Documents the owner may read, restricted to the requested scope.

    A document whose source has been deleted or withdrawn stops being
    retrievable immediately (section 16.4): the derived copy must not
    outlive the original.
    """
    queryset = KnowledgeDocument.objects.filter(
        owner=owner, deleted_at__isnull=True
    ).select_related("current_revision", "collection")
    if scope == "collections" and collection_ids:
        queryset = queryset.filter(collection_id__in=list(collection_ids))
    elif scope == "collections":
        queryset = queryset.none()
    if for_ai:
        queryset = queryset.filter(ai_enabled=True)
    # A derived document whose source is gone (deleted, withdrawn or removed)
    # must not be retrievable any more.
    return queryset.exclude(
        Q(source_type="material", source_material__isnull=True)
        | Q(source_type="journal_entry", source_entry__isnull=True)
        | Q(source_type="ai_message", source_message__isnull=True)
        | Q(source_type="material", source_material__deleted_at__isnull=False)
        | Q(source_type="journal_entry", source_entry__deleted_at__isnull=False)
    )


def search(
    owner,
    query: str,
    *,
    collection_ids=None,
    scope: str = "all",
    limit: int = DEFAULT_LIMIT,
    for_ai: bool = False,
) -> tuple[list[SearchHit], list[str]]:
    """Return ranked hits plus the effective scope description."""
    query = (query or "").strip()[:MAX_QUERY_CHARS]
    documents = scope_queryset(
        owner, collection_ids=collection_ids, scope=scope, for_ai=for_ai
    )
    document_ids = list(documents.values_list("id", flat=True))
    effective_scope = {
        "collections": [str(item) for item in (collection_ids or [])],
        "all": "all",
    }[scope]
    if not query or not document_ids:
        return [], effective_scope

    terms = tokenize(query)
    if not terms:
        return [], effective_scope

    revision_ids = [
        revision_id
        for revision_id in documents.values_list("current_revision_id", flat=True)
        if revision_id
    ]
    if not revision_ids:
        return [], effective_scope

    # Narrow in the database first: owner + ready revision + term filters.
    candidates = KnowledgeChunk.objects.filter(
        owner=owner,
        revision_id__in=revision_ids,
        document_id__in=document_ids,
    )
    condition = Q()
    for term in terms:
        condition |= Q(text__icontains=term)
    candidates = candidates.filter(condition).select_related("document")[:MAX_CANDIDATES]

    document_map = {str(item.id): item for item in documents}
    hits: list[SearchHit] = []
    for chunk in candidates:
        document = document_map.get(str(chunk.document_id))
        if document is None:
            continue
        body_score, matched = score_text(chunk.text, terms)
        title_score, title_matched = score_text(document.title, terms)
        heading_score, _ = score_text(chunk.heading_path, terms)
        if not matched and not title_matched:
            continue
        score = body_score + title_score * 2.0 + heading_score * 1.2
        reason = "正文命中" if matched else "标题命中"
        hits.append(
            SearchHit(
                chunk=chunk,
                document=document,
                score=score,
                reason=reason,
                matched_terms=sorted(set(matched + title_matched)),
            )
        )

    hits.sort(key=lambda item: (-item.score, str(item.chunk.id)))
    limited = _limit_per_document(hits, limit)
    return limited, effective_scope


def _limit_per_document(hits: list[SearchHit], limit: int) -> list[SearchHit]:
    per_document: dict[str, int] = {}
    selected: list[SearchHit] = []
    for hit in hits:
        key = hit.document_id
        if per_document.get(key, 0) >= MAX_PER_DOCUMENT:
            continue
        per_document[key] = per_document.get(key, 0) + 1
        selected.append(hit)
        if len(selected) >= limit:
            break
    return selected
