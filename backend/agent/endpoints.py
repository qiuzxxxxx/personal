"""Validate model destinations and connect to the address that was checked."""
import ipaddress
import socket

import httpx
from django.conf import settings

IPV6_TRANSLATION_NETWORKS = (
    ipaddress.IPv6Network("64:ff9b::/96"),
    ipaddress.IPv6Network("64:ff9b:1::/48"),
)


class LLMError(RuntimeError):
    """A safe, user-facing model provider error."""


def model_url(value: str) -> httpx.URL:
    try:
        url = httpx.URL(value)
    except (httpx.InvalidURL, ValueError):
        raise LLMError("模型 Base URL 无效。") from None
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or "%" in url.host
        or url.userinfo
        or url.fragment
        or url.port == 0
    ):
        raise LLMError("模型 Base URL 必须是有效的 HTTP(S) 地址，且不含账号信息或片段。")
    if url.scheme == "http":
        host = url.host.lower().strip("[]")
        loopback = host == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        # Clear-text HTTP can expose both the model API key and private user
        # content. Permit it only for loopback development or an exact,
        # operator-configured private service origin.
        if not loopback and not _http_origin_is_allowlisted(url):
            raise LLMError("公网模型接口必须使用 HTTPS；HTTP 仅允许本机或已配置的内网接口。")
    return url


def _http_origin_is_allowlisted(url: httpx.URL) -> bool:
    for value in settings.NEXUS_LLM_PRIVATE_ORIGINS:
        try:
            allowed = httpx.URL(value)
        except (httpx.InvalidURL, ValueError):
            continue
        if (
            allowed.scheme == "http"
            and allowed.host
            and not allowed.userinfo
            and not allowed.fragment
            and allowed.path == "/"
            and not allowed.query
            and allowed.port != 0
            and origin(allowed) == origin(url)
        ):
            return True
    return False


def origin(url: httpx.URL) -> tuple[str, str, int]:
    port = url.port or (443 if url.scheme == "https" else 80)
    return url.scheme, url.raw_host.decode("ascii"), port


def _allow_private(url: httpx.URL) -> bool:
    for value in settings.NEXUS_LLM_PRIVATE_ORIGINS:
        allowed = model_url(value)
        if allowed.path == "/" and not allowed.query and origin(allowed) == origin(url):
            return True
    return False


def _checked_addresses(url: httpx.URL) -> list[str]:
    _, host, port = origin(url)
    try:
        results = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise LLMError("无法解析模型接口地址。") from None

    allow_private = _allow_private(url)
    addresses = []
    for _, _, _, _, sockaddr in results:
        if "%" in sockaddr[0] or (len(sockaddr) == 4 and sockaddr[3]):
            continue
        address = ipaddress.ip_address(sockaddr[0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if address.is_unspecified or address.is_multicast:
            continue
        translated = isinstance(address, ipaddress.IPv6Address) and (
            address.sixtofour is not None
            or address.teredo is not None
            or address.is_site_local
            or any(address in network for network in IPV6_TRANSLATION_NETWORKS)
        )
        if allow_private or (address.is_global and not address.is_reserved and not translated):
            addresses.append(str(address))

    if not addresses:
        raise LLMError("模型接口解析到了受限的网络地址。")
    return list(dict.fromkeys(addresses))


class ModelTransport(httpx.HTTPTransport):
    def __init__(self, endpoint: str):
        super().__init__(trust_env=False)
        self.endpoint = model_url(endpoint)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if origin(request.url) != origin(self.endpoint):
            raise LLMError("模型接口重定向到了另一个来源，请直接配置目标地址。")
        last_error = LLMError("无法连接到模型接口。")
        for address in _checked_addresses(request.url):
            # Keep the original HTTP Host and TLS hostname while connecting to
            # the checked numeric address, so there is no second DNS lookup.
            pinned = httpx.Request(
                request.method,
                request.url.copy_with(host=address),
                headers=request.headers,
                stream=request.stream,
                extensions={
                    **request.extensions,
                    "sni_hostname": origin(request.url)[1],
                },
            )
            try:
                return super().handle_request(pinned)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = exc
        raise last_error
