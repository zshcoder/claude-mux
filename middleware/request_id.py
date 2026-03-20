"""
请求ID中间件

自动为每个请求生成唯一ID，绑定到日志上下文，便于追踪。
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from logger import bind_context


class RequestIDMiddleware(BaseHTTPMiddleware):
    """自动生成请求ID并绑定到日志上下文"""

    async def dispatch(self, request: Request, call_next):
        # 1. 优先使用客户端传入的 x-request-id
        request_id = request.headers.get("x-request-id")
        if not request_id:
            # 2. 没有则自动生成 UUID（截取8位，更简洁）
            request_id = str(uuid.uuid4())[:8]

        # 3. 绑定到 structlog 上下文
        bind_context(request_id=request_id)

        # 4. 放入 request.state 供后续使用
        request.state.request_id = request_id

        response = await call_next(request)

        # 5. 添加到响应头返回给客户端
        response.headers["X-Request-ID"] = request_id
        return response
