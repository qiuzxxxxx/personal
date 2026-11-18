from django.urls import path

from . import views

urlpatterns = [
    path("knowledge/collections/", views.collection_list, name="knowledge-collection-list"),
    path(
        "knowledge/collections/<uuid:collection_id>/",
        views.collection_detail,
        name="knowledge-collection-detail",
    ),
    path("knowledge/documents/", views.document_list, name="knowledge-document-list"),
    path("knowledge/documents/import/", views.document_import, name="knowledge-document-import"),
    path(
        "knowledge/documents/<uuid:document_id>/",
        views.document_detail,
        name="knowledge-document-detail",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/reindex/",
        views.document_reindex,
        name="knowledge-document-reindex",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/restore/",
        views.document_restore,
        name="knowledge-document-restore",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/purge/",
        views.document_purge,
        name="knowledge-document-purge",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/status/",
        views.document_status,
        name="knowledge-document-status",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/source/",
        views.document_source,
        name="knowledge-document-source",
    ),
    path("knowledge/search/", views.search_view, name="knowledge-search"),
    path("knowledge/memories/", views.memory_list, name="knowledge-memory-list"),
    path(
        "knowledge/memories/<uuid:memory_id>/",
        views.memory_detail,
        name="knowledge-memory-detail",
    ),
    path(
        "knowledge/memories/<uuid:memory_id>/accept/",
        views.memory_accept,
        name="knowledge-memory-accept",
    ),
    path(
        "knowledge/memories/<uuid:memory_id>/disable/",
        views.memory_disable,
        name="knowledge-memory-disable",
    ),
    path(
        "knowledge/memories/<uuid:memory_id>/forget/",
        views.memory_forget,
        name="knowledge-memory-forget",
    ),
    path("knowledge/reviews/", views.review_list, name="knowledge-review-list"),
    path(
        "knowledge/reviews/<uuid:card_id>/grade/",
        views.review_grade,
        name="knowledge-review-grade",
    ),
    path("knowledge/write-intents/", views.write_intent, name="knowledge-write-intent"),
    path("knowledge/citations/<uuid:citation_id>/", views.citation_detail, name="knowledge-citation"),
    path("knowledge/export/", views.export_view, name="knowledge-export"),
]
