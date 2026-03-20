"""
认证模块

使用 FastAPI Security 依赖注入实现 Token 认证。
支持 x-api-key 和 Authorization: Bearer 两种方式。
"""

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from logger import get_logger

logger = get_logger(__name__)

# 两种认证头
_x_api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
_auth_bearer_header = APIKeyHeader(name="Authorization", auto_error=False)


def _extract_token(
    x_api_key: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    """从请求头中提取 token"""
    if x_api_key:
        return x_api_key
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


def create_auth_dependency(auth_token: str):
    """
    创建认证依赖，闭包绑定 auth_token。

    Args:
        auth_token: 配置中的合法 token

    Returns:
        FastAPI 依赖函数
    """

    async def verify_token(
        x_api_key: Optional[str] = Security(_x_api_key_header),
        authorization: Optional[str] = Security(_auth_bearer_header),
    ) -> str:
        token = _extract_token(x_api_key, authorization)

        if not token or not secrets.compare_digest(token, auth_token):
            logger.warning("auth_failed")
            raise HTTPException(
                status_code=401,
                detail={
                    "type": "error",
                    "error": {
                        "type": "authentication_error",
                        "message": "Invalid API key",
                    },
                },
            )
        return token

    return verify_token
