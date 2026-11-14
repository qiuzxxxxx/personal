"""Authentication for phone upload sessions.

An upload credential is delivery only: it never grants access to the account,
to the library or to any other session.
"""
from __future__ import annotations

import hashlib

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import UploadSession


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class UploadPrincipal:
    """Minimal principal: the phone only acts on behalf of one session."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, session: UploadSession):
        self.session = session
        self.id = session.owner_id
        self.username = session.owner.username

    def __str__(self) -> str:  # pragma: no cover
        return f"upload:{self.username}"


class UploadSessionAuthentication(BaseAuthentication):
    keyword = "Upload"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != self.keyword.lower().encode():
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("上传凭证格式无效。")
        try:
            raw_token = parts[1].decode("ascii")
        except UnicodeDecodeError:
            raise AuthenticationFailed("上传凭证格式无效。") from None

        session = (
            UploadSession.objects.select_related("owner")
            .filter(token_digest=token_digest(raw_token))
            .first()
        )
        if session is None:
            raise AuthenticationFailed("上传凭证无效。")
        if session.state != "active":
            raise AuthenticationFailed("上传会话已结束。")
        if session.expires_at <= timezone.now():
            raise AuthenticationFailed("上传会话已过期。")
        request.upload_session = session
        return UploadPrincipal(session), raw_token

    def authenticate_header(self, request) -> str:
        return self.keyword
