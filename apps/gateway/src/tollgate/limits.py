"""Bound request bodies before JSON parsing, including chunked uploads."""

import asyncio

from fastapi.responses import JSONResponse


class IngressLimits:
    def __init__(self, app, max_bytes=300000):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            try:
                message = await asyncio.wait_for(receive(), timeout=15)
            except TimeoutError:
                return await JSONResponse({"detail": "Request body timeout"}, status_code=408)(
                    scope, receive, send
                )
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                response = JSONResponse({"detail": "Request too large"}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(message)
            if not message.get("more_body"):
                break
        iterator = iter(chunks)

        async def buffered():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        await self.app(scope, buffered, send)
