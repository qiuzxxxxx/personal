from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest


async def _async_chunks(chunks):
    iterator = iter(chunks)
    end = object()
    read = sync_to_async(next)
    try:
        while (chunk := await read(iterator, end)) is not end:
            yield chunk
    finally:
        close = getattr(iterator, "close", None)
        if close is not None:
            await sync_to_async(close)()


def stream_chunks(request, chunks):
    """Keep sync iterators lazy under both WSGI and ASGI."""
    django_request = getattr(request, "_request", request)
    if isinstance(django_request, ASGIRequest):
        return _async_chunks(chunks)
    return chunks
