"""Server-side encryption for user model API keys.

Keys are encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256) and are
never returned to the browser in plaintext after being saved. The master key
lives outside the database and the repository:

1. ``NEXUS_MASTER_KEY`` environment variable (preferred in production), or
2. ``backend/.master.key`` (auto-generated once, chmod 600, git-ignored).
"""
from __future__ import annotations

import os
import stat
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

MASTER_KEY_ENV = "NEXUS_MASTER_KEY"
KEY_FILE = settings.BASE_DIR / ".master.key"


def _valid_fernet(raw: str) -> bool:
    try:
        Fernet(raw.encode("utf-8"))
        return True
    except Exception:  # noqa: BLE001 - any malformed key falls through
        return False


@lru_cache(maxsize=1)
def get_master_key() -> bytes:
    from_env = os.environ.get(MASTER_KEY_ENV, "").strip()
    if from_env:
        if not _valid_fernet(from_env):
            raise RuntimeError(
                f"{MASTER_KEY_ENV} 不是有效的 Fernet 密钥，请用 "
                '`python -c "from cryptography.fernet import Fernet;'
                'print(Fernet.generate_key().decode())"` 生成。'
            )
        return from_env.encode("utf-8")

    if KEY_FILE.exists():
        try:
            stored = KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            stored = ""
        if stored and _valid_fernet(stored):
            return stored.encode("utf-8")
        if getattr(settings, "IS_PRODUCTION", False):
            raise RuntimeError(
                f"{KEY_FILE} 存在但不是有效的 Fernet 密钥。"
                f"已有密文将无法解密，请恢复原密钥或设置 {MASTER_KEY_ENV}。"
            )

    if getattr(settings, "IS_PRODUCTION", False):
        # A temporary key would make every stored secret unreadable after the
        # next restart, so production must provide the key explicitly.
        raise RuntimeError(
            f"生产环境缺少主密钥。请设置 {MASTER_KEY_ENV} 环境变量，"
            f"或放置 {KEY_FILE} 文件。"
        )

    generated = Fernet.generate_key().decode("ascii")
    try:
        # O_EXCL makes the creation atomic: a concurrent worker that loses the
        # race re-reads the file instead of writing a second key.
        descriptor = os.open(
            KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR
        )
        try:
            os.write(descriptor, generated.encode("ascii"))
        finally:
            os.close(descriptor)
    except FileExistsError:
        try:
            stored = KEY_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            stored = ""
        if stored and _valid_fernet(stored):
            return stored.encode("utf-8")
    except OSError:
        # A read-only filesystem still allows in-process encryption for this
        # run; the key simply will not survive a restart.
        pass
    return generated.encode("utf-8")


def encrypt_secret(plaintext: str) -> str:
    if not plaintext:
        return ""
    return Fernet(get_master_key()).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return Fernet(get_master_key()).decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_secret(plaintext: str) -> str:
    """A display-only hint; never reveals enough to reconstruct the key."""
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "*" * len(plaintext)
    return f"{plaintext[:3]}…{plaintext[-4:]}"