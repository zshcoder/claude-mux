"""
配置管理模块

所有配置从 .env 环境变量读取。

环境变量说明：
- AUTH_TOKEN: 代理认证 Token
- DEFAULT_UPSTREAM: 默认上游 URL（默认 https://api.anthropic.com）
- SERVER_HOST: 监听地址（默认 0.0.0.0）
- SERVER_PORT: 监听端口（默认 8000）
- LOG_LEVEL: 日志级别（默认 INFO）
- LOG_FORMAT: 日志格式 console/json（默认 console）
- ROUTE_NAMES: 路由组名称列表，逗号分隔（如 OPUS,SONNET,HAIKU）
- 每个路由组需要三个变量：{NAME}_PATTERN, {NAME}_UPSTREAM, {NAME}_AUTH_TOKEN
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

from errors import ConfigError

# 加载 .env
load_dotenv()


@dataclass
class RouteRule:
    """路由规则"""
    pattern: str
    upstream_url: str
    api_key: Optional[str] = None


@dataclass
class ServerConfig:
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "console"
    log_user_agent: bool = False


@dataclass
class Config:
    """主配置类"""
    default_upstream: str
    auth_token: Optional[str] = None
    default_api_key: Optional[str] = None
    routes: List[RouteRule] = field(default_factory=list)
    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_env(cls) -> "Config":
        """
        从环境变量加载配置

        通过 ROUTE_NAMES 遍历路由组，每组读取：
          {NAME}_PATTERN   - 模型匹配模式
          {NAME}_UPSTREAM  - 上游 URL
          {NAME}_AUTH_TOKEN - 上游认证凭证

        Raises:
            ConfigError: 配置缺失或无效
        """
        auth_token = os.environ.get("AUTH_TOKEN")
        if not auth_token:
            raise ConfigError("缺少环境变量: AUTH_TOKEN（请检查 .env 文件）")

        default_upstream = os.environ.get("DEFAULT_UPSTREAM", "https://api.anthropic.com")
        if not cls._validate_url(default_upstream):
            raise ConfigError(f"无效的 DEFAULT_UPSTREAM: {default_upstream}")

        # 解析 CORS 来源配置（逗号分隔的域名列表）
        cors_origins_str = os.environ.get("CORS_ORIGINS", "*")
        cors_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()]

        server = ServerConfig(
            host=os.environ.get("SERVER_HOST", "0.0.0.0"),
            port=int(os.environ.get("SERVER_PORT", "8000")),
            cors_origins=cors_origins if cors_origins else ["*"]
        )

        logging_config = LoggingConfig(
            level=os.environ.get("LOG_LEVEL", "INFO"),
            format=os.environ.get("LOG_FORMAT", "console"),
            log_user_agent=os.environ.get("LOG_USER_AGENT", "false").lower() == "true"
        )

        # 解析路由组
        routes = []
        route_names = os.environ.get("ROUTE_NAMES", "")
        if route_names:
            for name in route_names.split(","):
                name = name.strip()
                if not name:
                    continue

                pattern = os.environ.get(f"{name}_PATTERN")
                upstream = os.environ.get(f"{name}_UPSTREAM")
                token = os.environ.get(f"{name}_AUTH_TOKEN")

                if not pattern:
                    raise ConfigError(f"缺少环境变量: {name}_PATTERN")
                if not upstream:
                    raise ConfigError(f"缺少环境变量: {name}_UPSTREAM")
                if not cls._validate_url(upstream):
                    raise ConfigError(f"无效的上游 URL: {name}_UPSTREAM={upstream}")

                routes.append(RouteRule(
                    pattern=pattern,
                    upstream_url=upstream,
                    api_key=token
                ))

        return cls(
            default_upstream=default_upstream,
            auth_token=auth_token,
            default_api_key=os.environ.get("DEFAULT_AUTH_TOKEN"),
            routes=routes,
            server=server,
            logging=logging_config
        )

    def get_api_key(self, route: Optional[RouteRule] = None) -> Optional[str]:
        """获取认证凭证（路由级 > 默认级）"""
        if route and route.api_key:
            return route.api_key
        if self.default_api_key:
            return self.default_api_key
        return None

    @staticmethod
    def _validate_url(url: str) -> bool:
        """验证 URL 格式"""
        try:
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False
