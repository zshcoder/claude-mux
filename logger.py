"""
structlog 日志配置模块

提供结构化日志功能，支持：
- JSON 格式输出（生产环境）
- Console 格式输出（开发环境）
- 上下文绑定
- 请求日志记录
- 调用位置信息（函数名、行号、线程号）
- 中英文日志消息切换
- Request ID 追踪（集成自 request_id_logging.py）
"""

import logging
import re
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

# 从 request_id_logging 导入 Request ID 相关组件
from request_id_logging import (
    RequestIDRenderer as _RequestIDRenderer,
    ConsoleRendererWithRequestID,
)


# 日志消息中英文映射表
# 格式: "event_name": (中文, 英文)
_LOG_MESSAGES = {
    # main.py
    "application_starting": ("服务启动中", "Application starting"),
    "application_started": ("服务已启动", "Application started"),
    "application_shutdown": ("服务关闭中", "Application shutdown"),
    "invalid_json_body": ("无效的 JSON 请求体", "Invalid JSON body"),
    "missing_model_field": ("缺少 model 字段", "Missing model field"),
    "request_received": ("收到请求", "Request received"),
    "routing_request": ("正在路由请求", "Routing request"),
    "forwarding_request": ("正在转发请求到上游", "Forwarding request to upstream"),
    "upstream_connection_error": ("上游连接错误", "Upstream connection error"),

    # client.py
    "upstream_client_initialized": ("上游客户端已初始化", "Upstream client initialized"),
    "upstream_response_received": ("收到上游响应", "Upstream response received"),
    "upstream_error_response": ("上游返回错误响应", "Upstream error response"),
    "streaming_response": ("正在流式传输响应", "Streaming response"),
    "upstream_timeout": ("上游请求超时", "Upstream timeout"),
    "upstream_connection_failed": ("上游连接失败", "Upstream connection failed"),
    "upstream_http_error": ("上游 HTTP 错误", "Upstream HTTP error"),
    "upstream_client_closed": ("上游客户端已关闭", "Upstream client closed"),

    # auth.py
    "auth_failed": ("认证失败", "Authentication failed"),

    # router.py
    "router_initialized": ("路由器已初始化", "Router initialized"),
    "route_matched": ("路由匹配成功", "Route matched"),
    "api_key_found": ("找到 API 密钥", "API key found"),
    "api_key_not_found": ("未找到 API 密钥", "API key not found"),
    "route_added": ("路由已添加", "Route added"),

    # logger.py 函数
    "request_processed": ("请求已处理", "Request processed"),
    "error_occurred": ("发生错误", "Error occurred"),
}


class MessageTranslateProcessor:
    """
    日志消息翻译处理器

    根据 lang 上下文变量，在渲染时将英文事件名翻译为中文或英文。
    """

    def __call__(self, logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        event = event_dict.get("event")
        if event and event in _LOG_MESSAGES:
            lang = event_dict.get("lang", "zh")
            zh_msg, en_msg = _LOG_MESSAGES[event]
            event_dict["event"] = zh_msg if lang == "zh" else en_msg
        return event_dict


def setup_logging(level: str = "INFO", json_format: bool = False, lang: str = "zh", utc: bool = False, request_id_prefix: bool = False):
    """
    配置 structlog 日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        json_format: 是否使用 JSON 格式输出（生产环境推荐）
        lang: 日志语言 ("zh" 中文, "en" 英文)，默认中文
        request_id_prefix: 是否在日志中显示 request_id= 前缀，默认否

    Returns:
        配置好的 structlog logger 实例

    Example:
        >>> logger = setup_logging("INFO", json_format=True)
        >>> logger.info("request_received", model="claude-3-opus", path="/v1/messages")
    """
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    # 配置标准库 logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # 调用位置参数：函数名、行号、线程名
    callsite_params = [
        CallsiteParameter.FUNC_NAME,
        CallsiteParameter.LINENO,
        CallsiteParameter.THREAD,
    ]

    # 配置 structlog 处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=utc),
        _RequestIDRenderer(),  # 将 request_id 渲染到日志级别旁边（必须在 TimeStamper 之后）
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        CallsiteParameterAdder(parameters=callsite_params),  # 添加函数名、行号、线程名
        MessageTranslateProcessor(),  # 翻译日志消息
    ]

    # 设置 request_id 前缀显示
    _RequestIDRenderer.show_prefix = request_id_prefix

    # 绑定语言设置到上下文
    structlog.contextvars.bind_contextvars(lang=lang)

    if json_format:
        # JSON 格式（生产环境）
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console 格式（开发环境）
        # 使用自定义 renderer 实现 request_id 紧跟日志级别
        processors = shared_processors + [
            ConsoleRendererWithRequestID(colors=True)
        ]

    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    获取 logger 实例

    Args:
        name: logger 名称

    Returns:
        structlog logger 实例
    """
    return structlog.get_logger(name)


def log_request(
    logger,
    model: str,
    upstream_url: str,
    status_code: int,
    duration: float,
    **kwargs: Any
) -> None:
    """
    记录请求处理信息

    Args:
        logger: structlog logger 实例
        model: 模型名称
        upstream_url: 上游 URL
        status_code: HTTP 状态码
        duration: 处理时长（秒）
        **kwargs: 额外的上下文信息

    Example:
        >>> log_request(
        ...     logger,
        ...     model="claude-3-opus",
        ...     upstream_url="https://api.anthropic.com",
        ...     status_code=200,
        ...     duration=1.23,
        ...     request_id="abc-123"
        ... )
    """
    # 根据状态码选择日志级别
    if status_code >= 500:
        log_method = logger.error
    elif status_code >= 400:
        log_method = logger.warning
    else:
        log_method = logger.info

    log_method(
        "request_processed",
        model=model,
        upstream_url=upstream_url,
        **({} if status_code == 200 else {"status_code": status_code}),
        duration_seconds=round(duration, 3),
        **kwargs
    )


def log_error(
    logger,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any
) -> None:
    """
    记录错误信息

    Args:
        logger: structlog logger 实例
        error: 异常对象
        context: 上下文信息（可选）
        **kwargs: 额外的上下文信息

    Example:
        >>> try:
        ...     # some operation
        ...     pass
        ... except Exception as e:
        ...     log_error(logger, e, model="claude-3-opus")
    """
    context = context or {}
    logger.error(
        "error_occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        **context,
        **kwargs
    )


def bind_context(**kwargs: Any) -> None:
    """
    绑定上下文变量到日志

    绑定后，所有后续的日志记录都会自动包含这些变量。

    Args:
        **kwargs: 要绑定的上下文变量

    Example:
        >>> bind_context(request_id="abc-123", user_id="user-456")
        >>> logger.info("processing_request")  # 会自动包含 request_id 和 user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    解绑上下文变量

    Args:
        *keys: 要解绑的变量名

    Example:
        >>> unbind_context("request_id", "user_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """
    清除所有上下文变量

    Example:
        >>> clear_context()
    """
    structlog.contextvars.clear_contextvars()
