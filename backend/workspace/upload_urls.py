from django.urls import path

from . import upload_views

urlpatterns = [
    path("sessions/", upload_views.session_create, name="upload-session-create"),
    path("sessions/<uuid:session_id>/", upload_views.session_status, name="upload-session-status"),
    path(
        "sessions/<uuid:session_id>/revoke/",
        upload_views.session_revoke,
        name="upload-session-revoke",
    ),
    path("phone/session/", upload_views.session_info, name="upload-phone-session"),
    path("phone/receipts/", upload_views.receipt_prepare, name="upload-phone-receipt-prepare"),
    path(
        "phone/receipts/<uuid:receipt_id>/",
        upload_views.receipt_status,
        name="upload-phone-receipt-status",
    ),
    path(
        "phone/receipts/<uuid:receipt_id>/content/",
        upload_views.receipt_content,
        name="upload-phone-receipt-content",
    ),
]
