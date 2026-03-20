"""
structlog 日志配置模块

提供结构化日志功能，支持：
- JSON 格式输出（生产环境）
- Console 格式输出（开发环境）
- 上下文绑定
- 请求日志记录
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog


def setup_logging(level: str = "INFO", json_format: bool = False):
    """
    配置 structlog 日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        json_format: 是否使用 JSON 格式输出（生产环境推荐）
    
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
    
    # 配置 structlog 处理器
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        # JSON 格式（生产环境）
        processors = shared_processors + [
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console 格式（开发环境）
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True)
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
        status_code=status_code,
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
