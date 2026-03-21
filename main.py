"""
Claude 代理路由器 - 主应用

基于 FastAPI 的智能代理路由器，根据 Claude 模型类型将请求路由到不同的上游服务器。
支持 SSE 流式响应和 API 密钥管理。
"""

import asyncio
import json
import sys
import time
import httpx
from contextlib import asynccontextmanager
from typing import Any, Dict

import structlog
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import create_auth_dependency
from client import UpstreamClient
from config import Config, load_env_file
from middleware.request_id import RequestIDMiddleware
from errors import (
    ConfigError,
    ProxyError,
    RequestValidationError,
    RoutingError,
    UpstreamError,
)
from logger import bind_context, clear_context, get_logger, log_error, log_request, setup_logging
from router import ModelRouter

# 全局变量
config: Config | None = None
router: ModelRouter | None = None
client: UpstreamClient | None = None


def _get_log_lang() -> str:
    """获取日志语言设置，优先从环境变量读取"""
    import os
    return os.environ.get("LOG_LANG", "zh")


def _get_log_utc() -> bool:
    """获取日志时区设置，优先从环境变量读取"""
    import os
    return os.environ.get("LOG_UTC", "false").lower() == "true"


def _get_request_id_prefix() -> bool:
    """获取 request_id 前缀显示设置，优先从环境变量读取"""
    import os
    return os.environ.get("REQUEST_ID_PREFIX", "false").lower() == "true"


logger: structlog.BoundLogger | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    在启动时初始化配置、路由器和客户端，
    在关闭时清理资源。
    """
    global config, router, client, logger

    # 启动时初始化
    try:
        # 加载配置（从 .env 环境变量）
        config = Config.from_env()

        # 初始化日志
        setup_logging(
            level=config.logging.level,
            json_format=(config.logging.format == "json"),
            lang=_get_log_lang(),
            utc=_get_log_utc(),
            request_id_prefix=_get_request_id_prefix()
        )

        logger = get_logger(__name__)

        logger.info(
            "application_starting",
            port=config.server.port,
            log_level=config.logging.level
        )

        # 初始化路由器
        router = ModelRouter(config)

        # 初始化上游客户端
        client = UpstreamClient()

        # 创建认证依赖
        app.state.verify_token = create_auth_dependency(config.auth_token)

        logger.info(
            "application_started",
            routes_count=len(config.routes),
            cors_origins=config.server.cors_origins
        )

        yield

    except ConfigError as e:
        print(f"配置错误: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"启动失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 关闭时清理
    finally:
        if client:
            await client.close()
        if logger:
            logger.info("application_shutdown")


# 创建 FastAPI 应用
app = FastAPI(
    title="Claude Proxy Router",
    description="智能代理路由器，根据模型类型路由到不同的上游服务器",
    version="1.0.0",
    lifespan=lifespan
)


def configure_app(log_user_agent: bool = False) -> None:
    """
    配置应用（必须在应用创建后、启动前调用）

    由于中间件必须在应用启动前添加，因此将此逻辑从 lifespan 移出。
    首次调用时会初始化配置和中间件，后续调用直接返回。

    Args:
        log_user_agent: 是否在日志中显示 User-Agent
    """
    global config

    # 如果已经配置过，直接返回
    if config is not None and hasattr(app.state, '_cors_configured'):
        return

    # 确保配置已加载
    if config is None:
        try:
            config = Config.from_env()
        except ConfigError as e:
            print(f"配置错误: {e.message}", file=sys.stderr)
            sys.exit(1)

    # 添加 CORS 中间件（使用配置的 origins）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 添加请求ID中间件（自动生成/透传请求ID并绑定到日志上下文）
    app.add_middleware(RequestIDMiddleware)

    # 保存日志配置
    app.state.log_user_agent = log_user_agent or config.logging.log_user_agent

    # 标记已配置
    app.state._cors_configured = True


@app.post("/{path:path}")
async def proxy_request(path: str, request: Request) -> Response:
    """
    拦截所有 POST 请求并转发到相应的上游服务器
    """
    start_time = time.time()

    # 绑定请求上下文
    bind_context(request_path=path)

    # 提取客户端信息
    client_host = request.client.host if request.client else None
    # 优先获取代理转发的原始 IP，其次获取直接连接的 IP
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = client_host
    # 过滤本地回环地址
    if client_ip in ("127.0.0.1", "::1", "localhost"):
        client_ip = None
    user_agent = request.headers.get("user-agent", "unknown")

    # 读取请求体（需要先读取才能获取 size）
    try:
        body = await request.body()
        request_size = len(body)
        body = json.loads(body) if body else {}
    except Exception as e:
        logger.warning("invalid_json_body", error=str(e))
        raise RequestValidationError("请求体不是有效的 JSON")

    # 只绑定有值的字段（request_id 已由中间件绑定）
    bind_context(request_size=request_size)
    if getattr(app.state, 'log_user_agent', False) and user_agent:
        bind_context(user_agent=user_agent)
    if client_ip:
        bind_context(client_ip=client_ip)

    try:
        # 认证：通过依赖注入验证（HTTPException 401 会自动抛出）
        await request.app.state.verify_token(
            x_api_key=request.headers.get("x-api-key"),
            authorization=request.headers.get("authorization"),
        )

        # 提取模型名称
        model = body.get("model")
        if not model:
            logger.warning("missing_model_field")
            raise RequestValidationError("请求体缺少 model 字段")

        bind_context(model=model)

        logger.info(
            "request_received",
            model=model,
            path=path,
            stream=body.get("stream", False)
        )

        # 获取路由信息
        upstream_url, api_key = router.get_route_info(model)

        # 构建完整的目标 URL（保留 query string）
        query_string = request.url.query
        target_url = f"{upstream_url.rstrip('/')}/{path}"
        if query_string:
            target_url = f"{target_url}?{query_string}"

        bind_context(upstream_url=upstream_url)

        logger.info(
            "routing_request",
            model=model,
            upstream_url=upstream_url,
            target_url=target_url
        )

        # 转发请求到上游，使用 httpx stream 直接获取响应
        # 这样可以拿到真实的 status_code 和 headers，再决定如何返回
        try:
            http_client = await client._get_client()
            forward_headers = client._prepare_headers(dict(request.headers), api_key, target_url)

            req = http_client.build_request(
                method="POST",
                url=target_url,
                headers=forward_headers,
                json=body
            )
            logger.info(
                "forwarding_request",
                model=model,
                upstream_url=upstream_url,
                target_url=target_url
            )

            # 在发送请求之前就启动警告任务（覆盖整个请求周期）
            warning_delay = config.logging.upstream_wait_warning_delay
            repeat_interval = config.logging.upstream_wait_warning_repeat_interval
            warning_done = asyncio.Event()

            async def warn_loop():
                await asyncio.sleep(warning_delay)
                while not warning_done.is_set():
                    elapsed = time.time() - start_time
                    logger.warning(
                        "still_waiting_for_upstream",
                        total_elapsed=round(elapsed, 1),
                        note="仍在等待上游响应"
                    )
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(warning_done.wait()),
                            timeout=repeat_interval
                        )
                        break  # warning_done 被设置了，退出
                    except asyncio.TimeoutError:
                        pass

            warn_task = asyncio.create_task(warn_loop())

            upstream_resp = await http_client.send(req, stream=True)

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "upstream_connection_error",
                model=model,
                upstream_url=upstream_url,
                error=str(e)
            )
            log_request(logger, model=model, upstream_url=upstream_url, status_code=502, duration=duration)
            clear_context()
            return Response(
                content=json.dumps({
                    "error": {
                        "type": "upstream_error",
                        "message": f"无法连接上游: {str(e)}",
                        "upstream_url": upstream_url
                    }
                }, ensure_ascii=False),
                status_code=502,
                media_type="application/json"
            )

        # 构建流式生成器，负责读取上游响应并在结束时关闭
        async def stream_upstream():
            try:
                async for chunk in upstream_resp.aiter_bytes(8192):
                    yield chunk
            finally:
                warning_done.set()
                await warn_task
                await upstream_resp.aclose()
                duration = time.time() - start_time
                log_request(
                    logger,
                    model=model,
                    upstream_url=upstream_url,
                    status_code=upstream_resp.status_code,
                    duration=duration
                )
                clear_context()

        # 透传上游的 status_code 和关键 headers
        response_headers = {}
        for key in ("content-type", "x-request-id"):
            if key in upstream_resp.headers:
                response_headers[key] = upstream_resp.headers[key]
        response_headers["Cache-Control"] = "no-cache"
        response_headers["Connection"] = "keep-alive"
        response_headers["X-Accel-Buffering"] = "no"

        return StreamingResponse(
            stream_upstream(),
            status_code=upstream_resp.status_code,
            headers=response_headers,
            media_type=upstream_resp.headers.get("content-type", "text/event-stream")
        )

    except ProxyError as e:
        # 记录错误
        duration = time.time() - start_time
        log_error(logger, e, model=body.get("model") if 'body' in locals() else None)

        # 返回统一的 JSON 错误响应
        return Response(
            content=e.to_json(),
            status_code=e.status_code,
            media_type="application/json"
        )

    except Exception as e:
        # 记录未预期的错误
        duration = time.time() - start_time
        log_error(logger, e, path=path)

        # 返回统一的 JSON 500 错误
        return Response(
            content=json.dumps({
                "error": {
                    "type": "internal_error",
                    "message": f"内部服务器错误: {str(e)}"
                }
            }, ensure_ascii=False),
            status_code=500,
            media_type="application/json"
        )


@app.get("/health/live")
async def liveness_check():
    """
    存活探针（Liveness Probe）

    用于 Kubernetes 判断容器是否存活。
    只要服务进程在运行就返回 healthy。

    Returns:
        健康状态
    """
    return {
        "status": "healthy",
        "service": "claude-proxy-router"
    }


@app.get("/health/ready")
async def readiness_check():
    """
    就绪探针（Readiness Probe）

    用于 Kubernetes 判断容器是否可以接收流量。
    检查上游服务连通性。

    Returns:
        健康状态及上游检查结果
    """
    if not config:
        return {
            "status": "not_ready",
            "reason": "configuration not loaded"
        }

    upstream_status = {}
    all_healthy = True

    # 检查路由配置的上游
    for route in config.routes:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as http_client:
                resp = await http_client.get(route.upstream_url.rstrip('/') + "/health")
                upstream_status[route.pattern] = {
                    "healthy": resp.status_code < 500,
                    "status_code": resp.status_code
                }
                if resp.status_code >= 500:
                    all_healthy = False
        except Exception as e:
            upstream_status[route.pattern] = {
                "healthy": False,
                "error": str(e)
            }
            all_healthy = False

    return {
        "status": "healthy" if all_healthy else "not_ready",
        "service": "claude-proxy-router",
        "routes_count": len(config.routes),
        "upstreams": upstream_status
    }


@app.get("/health")
async def health_check():
    """
    兼容旧版本的健康检查端点

    Returns:
        健康状态
    """
    return await liveness_check()


@app.get("/")
async def root():
    """
    根路径，返回服务信息
    """
    return {
        "service": "Claude Proxy Router",
        "version": "1.0.0",
        "description": "智能代理路由器，根据模型类型路由到不同的上游服务器",
        "endpoints": {
            "proxy": "POST /{path}",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }


# 全局异常处理器
@app.exception_handler(ProxyError)
async def proxy_error_handler(request: Request, exc: ProxyError):
    """处理所有代理错误"""
    logger.error(
        "proxy_error",
        error_type=type(exc).__name__,
        error_message=exc.message,
        status_code=exc.status_code
    )

    return Response(
        content=exc.to_json(),
        status_code=exc.status_code,
        media_type="application/json"
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    """处理所有未捕获的异常"""
    logger.exception(
        "unhandled_error",
        error_type=type(exc).__name__,
        error_message=str(exc)
    )

    return Response(
        content=json.dumps({
            "error": {
                "type": "internal_error",
                "message": f"内部服务器错误: {str(exc)}"
            }
        }, ensure_ascii=False),
        status_code=500,
        media_type="application/json"
    )


def setup_claude_settings():
    """交互式配置 Claude Code 的 settings.json"""
    import json
    from pathlib import Path
    from dotenv import dotenv_values

    # 加载 .env 获取默认值
    env = dotenv_values(".env")

    # 查找 settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        print(f"找到配置文件: {settings_path}")
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    else:
        print(f"未找到 {settings_path}，将创建新文件")
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings = {}

    # 从 .env 读取默认值
    port = env.get("SERVER_PORT", "12346")
    auth_token = env.get("AUTH_TOKEN", "")

    # 从 ROUTE_NAMES 对应的 pattern 提取模型前缀（去掉通配符 *）
    route_names = env.get("ROUTE_NAMES", "OPUS,SONNET,HAIKU")
    names = [n.strip() for n in route_names.split(",") if n.strip()]

    def get_model_prefix(name: str) -> str:
        pattern = env.get(f"{name}_PATTERN", "")
        return pattern.rstrip("*").rstrip("-").rstrip(".")

    opus_prefix = get_model_prefix("OPUS") if "OPUS" in names else ""
    sonnet_prefix = get_model_prefix("SONNET") if "SONNET" in names else ""
    haiku_prefix = get_model_prefix("HAIKU") if "HAIKU" in names else ""

    print("\n--- Claude Code 配置 ---")
    print("直接回车保持不变，输入 default 使用默认值\n")

    # 跳过标记
    SKIP_MARKER = object()

    def prompt_value(label: str, env_default: str, current_value: str | None) -> str | object:
        """提示用户输入值

        Args:
            label: 配置项名称
            env_default: .env 中的默认值
            current_value: settings.json 中当前已配置的值（None 表示未配置）
        """
        display_default = current_value if current_value is not None else env_default
        user_input = input(f"  {label} (直接回车保持不变，当前: {display_default}): ").strip()
        if user_input.lower() == "default":
            return env_default  # 显式输入 default，使用 .env 默认值
        if not user_input:
            return SKIP_MARKER  # 直接回车跳过
        return user_input

    # 获取 settings.json 中的当前值
    current_base_url = settings.get("env", {}).get("ANTHROPIC_BASE_URL")
    current_token = settings.get("env", {}).get("ANTHROPIC_AUTH_TOKEN")
    current_sonnet = settings.get("env", {}).get("ANTHROPIC_DEFAULT_SONNET_MODEL")
    current_opus = settings.get("env", {}).get("ANTHROPIC_DEFAULT_OPUS_MODEL")
    current_haiku = settings.get("env", {}).get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
    current_timeout = settings.get("env", {}).get("API_TIMEOUT_MS")

    base_url = prompt_value("ANTHROPIC_BASE_URL", f"http://localhost:{port}", current_base_url)
    token = prompt_value("ANTHROPIC_AUTH_TOKEN", auth_token, current_token)
    sonnet_model = prompt_value("ANTHROPIC_DEFAULT_SONNET_MODEL", sonnet_prefix, current_sonnet)
    opus_model = prompt_value("ANTHROPIC_DEFAULT_OPUS_MODEL", opus_prefix, current_opus)
    haiku_model = prompt_value("ANTHROPIC_DEFAULT_HAIKU_MODEL", haiku_prefix, current_haiku)
    api_timeout = prompt_value("API_TIMEOUT_MS", "300000", current_timeout)

    # 初始化 env 部分
    if "env" not in settings:
        settings["env"] = {}

    # 只更新非跳过的字段
    updates = [
        ("ANTHROPIC_BASE_URL", base_url),
        ("ANTHROPIC_AUTH_TOKEN", token),
        ("ANTHROPIC_DEFAULT_SONNET_MODEL", sonnet_model),
        ("ANTHROPIC_DEFAULT_OPUS_MODEL", opus_model),
        ("ANTHROPIC_DEFAULT_HAIKU_MODEL", haiku_model),
        ("API_TIMEOUT_MS", api_timeout),
    ]

    skipped = []
    for key, value in updates:
        if value is not SKIP_MARKER:
            settings["env"][key] = value
        else:
            skipped.append(key)
            current = settings["env"].get(key)
            if current is not None:
                print(f"  跳过 {key}（保留原值: {current}）")

    if skipped:
        print()

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print(f"已写入 {settings_path}")
    print(json.dumps(settings["env"], indent=2, ensure_ascii=False))


def main():
    """主函数，启动服务器"""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Claude 代理路由器 - 智能代理路由服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                    # 使用默认配置
  python main.py gen-token          # 生成随机 Token
  python main.py setup              # 配置 Claude Code settings.json
  python main.py --port 8080        # 指定端口
        """
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("gen-token", help="生成随机 auth_token")
    subparsers.add_parser("setup", help="交互式配置 Claude Code 的 settings.json")

    parser.add_argument("--host", type=str, default=None, help="服务器监听地址")
    parser.add_argument("--port", type=int, default=None, help="服务器监听端口")
    parser.add_argument("--reload", action="store_true", help="启用自动重载")
    parser.add_argument("--log-level", type=str, choices=["debug", "info", "warning", "error", "critical"],
                        default=None)
    parser.add_argument("--log-user-agent", action="store_true", help="在日志中显示 User-Agent")
    parser.add_argument("--lang", type=str, choices=["zh", "en"], default="zh",
                        help="日志语言 (zh 中文 / en 英文，默认中文)")
    parser.add_argument("--utc", action="store_true",
                        help="使用 UTC 时区而非本地时区")
    parser.add_argument("--request-id-prefix", action="store_true",
                        help="在 request_id 标签中显示 request_id= 前缀")
    parser.add_argument("--env-file", type=str, default=None,
                        help=".env 文件路径（默认当前目录的 .env）")

    args = parser.parse_args()

    # 生成 Token 子命令
    if args.command == "gen-token":
        import secrets
        token = f"sk-proxy-{secrets.token_hex(32)}"
        print(token)
        return

    # 配置 Claude Code 子命令
    if args.command == "setup":
        setup_claude_settings()
        return

    # 如果配置还未加载，先加载配置
    global config
    if config is None:
        # 加载 .env 文件（支持 --env-file 指定路径）
        env_loaded = load_env_file(args.env_file)
        if not env_loaded and not args.env_file:
            print("错误: 未找到 .env 文件", file=sys.stderr)
            print("提示: 请创建 .env 文件或使用 --env-file 指定配置文件", file=sys.stderr)
            print("示例: cp .env.example .env", file=sys.stderr)
            sys.exit(1)
        try:
            config = Config.from_env()
        except ConfigError as e:
            print(f"配置错误: {e.message}", file=sys.stderr)
            sys.exit(1)

    host = args.host if args.host is not None else config.server.host
    port = args.port if args.port is not None else config.server.port
    log_level = args.log_level if args.log_level is not None else config.logging.level.lower()
    global _log_lang
    _log_lang = args.lang

    # 通过环境变量传递给子进程
    import os
    os.environ["LOG_LANG"] = args.lang
    os.environ["LOG_UTC"] = "true" if args.utc else "false"
    os.environ["REQUEST_ID_PREFIX"] = "true" if args.request_id_prefix else "false"

    # 配置应用（添加中间件等），必须在 uvicorn.run 之前调用
    log_user_agent = args.log_user_agent or (config.logging.log_user_agent if config else False)
    configure_app(log_user_agent=log_user_agent)

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=args.reload,
        log_level=log_level
    )


if __name__ == "__main__":
    main()
