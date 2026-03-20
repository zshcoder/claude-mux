"""
Request ID 日志增强模块

功能：
- 自动为每个请求生成唯一 request_id
- 绑定到 structlog 上下文，所有日志自动携带
- request_id 紧跟在日志级别后面显示，便于追踪
- 支持命令行参数控制显示格式

使用方法：
1. 复制本文件到项目根目录
2. 在 main.py 中:
   - from request_id_logging import setup_request_id_logging
   - setup_request_id_logging(...)  # 在 structlog 配置之前调用
3. 添加命令行参数 --request-id-prefix
4. 添加中间件: app.add_middleware(RequestIDMiddleware)

Author: Claude
"""

import re
import uuid
from typing import Any, Dict

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# ============================================================================
# 配置项（可按需修改）
# ============================================================================

# request_id 标签的前缀显示（默认关闭，显示如 [abc123]）
REQUEST_ID_PREFIX: bool = False

# request_id 颜色 (ANSI 转义序列)
# 常见颜色: 31=红, 32=绿, 33=黄, 34=蓝, 35=洋红, 36=青, 37=白
REQUEST_ID_COLOR: str = "\x1b[33m"  # 黄色
REQUEST_ID_RESET: str = "\x1b[0m"

# 快捷配置函数
def enable_prefix():
    """启用 request_id= 前缀显示"""
    global REQUEST_ID_PREFIX
    REQUEST_ID_PREFIX = True


def set_color(color_code: int):
    """设置 request_id 颜色

    Args:
        color_code: ANSI 颜色代码 (31-37)
    """
    global REQUEST_ID_COLOR
    REQUEST_ID_COLOR = f"\x1b[{color_code}m"


# ============================================================================
# 中间件
# ============================================================================

def bind_context(**kwargs) -> None:
    """绑定上下文变量到日志"""
    structlog.contextvars.bind_contextvars(**kwargs)


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


# ============================================================================
# 日志渲染器
# ============================================================================

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')


class RequestIDRenderer:
    """
    请求ID渲染处理器

    将 request_id 从 context 中提取并渲染到日志级别旁边，
    使其紧跟在 [level] 之后，形成 [level][request_id=xxx] 的视觉效果。
    """

    def __call__(self, logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        request_id = event_dict.pop("request_id", None)
        if request_id:
            if REQUEST_ID_PREFIX:
                event_dict["_request_id"] = f"[request_id={request_id}]"
            else:
                event_dict["_request_id"] = f"[{request_id}]"
        return event_dict


class ConsoleRendererWithRequestID:
    """
    自定义 Console Renderer

    将 _request_id 字段的内容直接拼接到日志级别后面，
    实现 [info][request_id=xxx] 的效果。
    """

    def __init__(self, colors: bool = True, **kwargs):
        self.colors = colors
        self._default_renderer = structlog.dev.ConsoleRenderer(colors=colors, **kwargs)

    def __call__(self, logger, method_name: str, event_dict: Dict[str, Any]):
        # 提取 _request_id 字段
        request_id_tag = event_dict.pop("_request_id", None)

        # 如果有 request_id，添加颜色（只给内容染色，括号保持默认颜色）
        if request_id_tag and self.colors:
            if request_id_tag.startswith("[request_id="):
                content = request_id_tag[12:-1]
                request_id_tag = f"[request_id={REQUEST_ID_COLOR}{content}{REQUEST_ID_RESET}]"
            elif request_id_tag.startswith("["):
                content = request_id_tag[1:-1]
                request_id_tag = f"[{REQUEST_ID_COLOR}{content}{REQUEST_ID_RESET}]"

        # 调用默认渲染器获取基础输出
        output = self._default_renderer(logger, method_name, event_dict)

        # 如果有 request_id，插入到级别后面
        if request_id_tag and isinstance(output, str):
            clean_output = ANSI_ESCAPE.sub('', output)
            match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+ \[)(\w+)(\s*\])', clean_output)
            if match:
                # 找到 ] 在原始输出中的位置
                bracket_pos = match.end()
                raw_pos = 0
                clean_pos = 0
                while clean_pos < bracket_pos and raw_pos < len(output):
                    if output[raw_pos] == '\x1b':
                        match_escape = re.match(r'\x1b\[[0-9;]*m', output[raw_pos:])
                        if match_escape:
                            raw_pos += len(match_escape.group())
                        else:
                            raw_pos += 1
                    else:
                        raw_pos += 1
                        clean_pos += 1
                prefix = output[:raw_pos]
                remainder = output[raw_pos:]
                output = prefix + request_id_tag + remainder

        return output


# ============================================================================
# 集成函数
# ============================================================================

def setup_request_id_logging(
    level: str = "INFO",
    json_format: bool = False,
    lang: str = "zh",
    utc: bool = False,
    show_request_id_prefix: bool = False,
):
    """
    配置 structlog 日志系统（带 request_id 支持）

    Args:
        level: 日志级别
        json_format: 是否使用 JSON 格式
        lang: 日志语言
        utc: 是否使用 UTC 时间
        show_request_id_prefix: 是否显示 request_id= 前缀
    """
    import logging
    import sys
    from structlog.processors import CallsiteParameter, CallsiteParameterAdder

    # 设置全局配置
    global REQUEST_ID_PREFIX
    REQUEST_ID_PREFIX = show_request_id_prefix

    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    callsite_params = [
        CallsiteParameter.FUNC_NAME,
        CallsiteParameter.LINENO,
        CallsiteParameter.THREAD,
    ]

    _LOG_MESSAGES = {
        "application_starting": ("服务启动中", "Application starting"),
        "application_started": ("服务已启动", "Application started"),
        "application_shutdown": ("服务关闭中", "Application shutdown"),
        "request_received": ("收到请求", "Request received"),
    }

    class MessageTranslateProcessor:
        def __call__(self, logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
            event = event_dict.get("event")
            if event and event in _LOG_MESSAGES:
                msg_lang = event_dict.get("lang", "zh")
                zh_msg, en_msg = _LOG_MESSAGES[event]
                event_dict["event"] = zh_msg if msg_lang == "zh" else en_msg
            return event_dict

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=utc),
        RequestIDRenderer(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        CallsiteParameterAdder(parameters=callsite_params),
        MessageTranslateProcessor(),
    ]

    structlog.contextvars.bind_contextvars(lang=lang)

    if json_format:
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [ConsoleRendererWithRequestID(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
