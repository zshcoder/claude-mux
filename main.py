"""
Claude 代理路由器 - 主应用

基于 FastAPI 的智能代理路由器，根据 Claude 模型类型将请求路由到不同的上游服务器。
支持 SSE 流式响应和 API 密钥管理。
"""

import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from auth import create_auth_dependency
from client import UpstreamClient
from config import Config
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
config: Config = None
router: ModelRouter = None
client: UpstreamClient = None
logger = None


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
        logger = setup_logging(
            level=config.logging.level,
            json_format=(config.logging.format == "json")
        )
        
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
        
        logger.info("application_started", routes_count=len(config.routes))
        
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

# 添加 CORS 中间件（可选）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/{path:path}")
async def proxy_request(path: str, request: Request) -> Response:
    """
    拦截所有 POST 请求并转发到相应的上游服务器
    """
    start_time = time.time()
    
    # 绑定请求上下文
    bind_context(request_path=path)
    
    try:
        # 认证：通过依赖注入验证（HTTPException 401 会自动抛出）
        await request.app.state.verify_token(
            x_api_key=request.headers.get("x-api-key"),
            authorization=request.headers.get("authorization"),
        )

        # 读取请求体
        try:
            body = await request.json()
        except Exception as e:
            logger.warning("invalid_json_body", error=str(e))
            raise RequestValidationError("请求体不是有效的 JSON")
        
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
                content=f'{{"error":{{"type":"proxy_error","message":"无法连接上游: {str(e)}"}}}}',
                status_code=502,
                media_type="application/json"
            )
        
        # 构建流式生成器，负责读取上游响应并在结束时关闭
        async def stream_upstream():
            try:
                async for chunk in upstream_resp.aiter_bytes(1):
                    yield chunk
            finally:
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
        
        # 返回错误响应
        return Response(
            content=e.message,
            status_code=e.status_code,
            media_type="text/plain"
        )
    
    except Exception as e:
        # 记录未预期的错误
        duration = time.time() - start_time
        log_error(logger, e, path=path)
        
        # 返回 500 错误
        return Response(
            content=f"内部服务器错误: {str(e)}",
            status_code=500,
            media_type="text/plain"
        )


@app.get("/health")
async def health_check():
    """
    健康检查端点
    
    Returns:
        健康状态
    """
    return {
        "status": "healthy",
        "routes_count": len(config.routes) if config else 0,
        "default_upstream": config.default_upstream if config else None
    }


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
        content=exc.message,
        status_code=exc.status_code,
        media_type="text/plain"
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
        content=f"内部服务器错误: {str(exc)}",
        status_code=500,
        media_type="text/plain"
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
    print("直接回车使用 [默认值]\n")

    def prompt_value(label: str, default: str) -> str:
        user_input = input(f"  {label} [{default}]: ").strip()
        return user_input if user_input else default

    base_url = prompt_value("ANTHROPIC_BASE_URL", f"http://localhost:{port}")
    token = prompt_value("ANTHROPIC_AUTH_TOKEN", auth_token)
    sonnet_model = prompt_value("ANTHROPIC_DEFAULT_SONNET_MODEL", sonnet_prefix)
    opus_model = prompt_value("ANTHROPIC_DEFAULT_OPUS_MODEL", opus_prefix)
    haiku_model = prompt_value("ANTHROPIC_DEFAULT_HAIKU_MODEL", haiku_prefix)
    api_timeout = prompt_value("API_TIMEOUT_MS", "300000")

    # 写入 env 部分
    if "env" not in settings:
        settings["env"] = {}

    settings["env"]["ANTHROPIC_BASE_URL"] = base_url
    settings["env"]["ANTHROPIC_AUTH_TOKEN"] = token
    settings["env"]["ANTHROPIC_DEFAULT_SONNET_MODEL"] = sonnet_model
    settings["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"] = opus_model
    settings["env"]["ANTHROPIC_DEFAULT_HAIKU_MODEL"] = haiku_model
    settings["env"]["API_TIMEOUT_MS"] = api_timeout

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

    print(f"\n已写入 {settings_path}")
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
    parser.add_argument("--log-level", type=str, choices=["debug", "info", "warning", "error", "critical"], default=None)
    
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
        try:
            config = Config.from_env()
        except ConfigError as e:
            print(f"配置错误: {e.message}", file=sys.stderr)
            sys.exit(1)
    
    host = args.host if args.host is not None else config.server.host
    port = args.port if args.port is not None else config.server.port
    log_level = args.log_level if args.log_level is not None else config.logging.level.lower()
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=log_level
    )


if __name__ == "__main__":
    main()
