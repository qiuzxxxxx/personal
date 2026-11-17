from django.urls import path

from . import views

urlpatterns = [
    # 旧聊天接口（保留兼容）
    path("contacts/", views.contacts, name="chat-contacts"),
    path("messages/", views.messages, name="chat-messages"),
    path("messages/clear/", views.clear_messages, name="chat-clear-messages"),
    path("messages/<uuid:message_id>/", views.message_detail, name="chat-message-detail"),
    path("unread/", views.unread, name="chat-unread"),
    path("read/", views.mark_read, name="chat-mark-read"),
    path("files/", views.upload_file, name="chat-file-upload"),
    path(
        "files/<uuid:message_id>/download/",
        views.download_file,
        name="chat-file-download",
    ),
    # 留言板（贴吧式）
    path("bbs/posts/", views.bbs_posts, name="bbs-posts"),
    path(
        "bbs/posts/<uuid:post_id>/",
        views.bbs_post_detail,
        name="bbs-post-detail",
    ),
    path(
        "bbs/posts/<uuid:post_id>/replies/",
        views.bbs_post_replies,
        name="bbs-post-replies",
    ),
    path(
        "bbs/posts/<uuid:post_id>/replies/<uuid:reply_id>/",
        views.bbs_reply_detail,
        name="bbs-reply-detail",
    ),
    path(
        "bbs/posts/<uuid:post_id>/file/",
        views.bbs_post_download_file,
        name="bbs-post-file",
    ),
    path(
        "bbs/replies/<uuid:reply_id>/file/",
        views.bbs_reply_download_file,
        name="bbs-reply-file",
    ),
]
