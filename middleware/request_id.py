"""
请求ID中间件

自动为每个请求生成唯一ID，绑定到日志上下文，便于追踪。
"""

# 从 request_id_logging 导入（保持接口兼容）
from request_id_logging import RequestIDMiddleware

__all__ = ["RequestIDMiddleware"]
