"""
错误定义模块

定义代理路由器中使用的所有自定义异常类。
"""

import json
from typing import Any, Dict, Optional


# 错误类型常量
class ErrorType:
    """错误类型枚举"""
    PROXY = "proxy_error"
    CONFIG = "config_error"
    UPSTREAM = "upstream_error"
    ROUTING = "routing_error"
    VALIDATION = "validation_error"


class ProxyError(Exception):
    """
    代理错误基类

    所有代理相关的错误都应继承此类。
    统一返回 JSON 格式的错误响应。
    """

    # 子类应覆盖此属性
    error_type: str = ErrorType.PROXY

    def __init__(self, message: str, status_code: int = 500, **extra: Any):
        """
        初始化代理错误

        Args:
            message: 错误消息
            status_code: HTTP 状态码
            **extra: 额外的错误信息（如 upstream_url）
        """
        self.message = message
        self.status_code = status_code
        self.extra = extra
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            错误信息的字典表示
        """
        error_obj = {
            "type": self.error_type,
            "message": self.message,
        }
        # 添加额外信息
        if self.extra:
            error_obj.update(self.extra)
        return {"error": error_obj}

    def to_json(self) -> str:
        """
        转换为 JSON 字符串

        Returns:
            JSON 格式的错误响应
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ConfigError(ProxyError):
    """
    配置错误

    当配置文件格式错误、缺少必需字段或配置无效时抛出。
    """

    error_type = ErrorType.CONFIG

    def __init__(self, message: str, **extra: Any):
        """
        初始化配置错误

        Args:
            message: 错误消息
            **extra: 额外的错误信息
        """
        super().__init__(message, status_code=500, **extra)


class UpstreamError(ProxyError):
    """
    上游服务器错误

    当与上游服务器通信失败时抛出，包括连接失败、超时、上游返回错误等。
    """

    error_type = ErrorType.UPSTREAM

    def __init__(self, message: str, status_code: int = 502, upstream_url: Optional[str] = None):
        """
        初始化上游错误

        Args:
            message: 错误消息
            status_code: HTTP 状态码（默认 502 Bad Gateway）
            upstream_url: 上游服务器 URL（可选，用于日志记录和错误响应）
        """
        extra = {"upstream_url": upstream_url} if upstream_url else {}
        super().__init__(message, status_code, **extra)
        self.upstream_url = upstream_url


class RoutingError(ProxyError):
    """
    路由错误

    当路由匹配失败或路由配置有问题时抛出。
    """

    error_type = ErrorType.ROUTING

    def __init__(self, message: str, status_code: int = 400, **extra: Any):
        """
        初始化路由错误

        Args:
            message: 错误消息
            status_code: HTTP 状态码（默认 400 Bad Request）
            **extra: 额外的错误信息
        """
        super().__init__(message, status_code, **extra)


class RequestValidationError(ProxyError):
    """
    请求验证错误

    当请求格式无效或缺少必需字段时抛出。
    """

    error_type = ErrorType.VALIDATION

    def __init__(self, message: str, **extra: Any):
        """
        初始化请求验证错误

        Args:
            message: 错误消息
            **extra: 额外的错误信息
        """
        super().__init__(message, status_code=400, **extra)
