"""
异步 HTTP 客户端模块

负责与上游服务器通信，支持：
- 异步 HTTP 请求
- SSE 流式响应处理
- 连接池管理
- 错误处理
"""

import json
from typing import AsyncIterator, Dict, Optional

import httpx

from errors import UpstreamError
from logger import get_logger

logger = get_logger(__name__)


class UpstreamClient:
    """
    上游 HTTP 客户端
    
    使用 httpx 发送异步请求，支持流式响应。
    """
    
    def __init__(self, timeout: float = 60.0, max_connections: int = 100):
        """
        初始化上游客户端
        
        Args:
            timeout: 请求超时时间（秒），默认 60 秒
            max_connections: 最大连接数，默认 100
        """
        self.timeout = timeout
        self.max_connections = max_connections
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "upstream_client_initialized",
            timeout=timeout,
            max_connections=max_connections
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        获取或创建 HTTP 客户端
        
        Returns:
            httpx.AsyncClient 实例
        """
        if self._client is None or self._client.is_closed:
            # 配置连接池限制
            limits = httpx.Limits(
                max_connections=self.max_connections,
                max_keepalive_connections=self.max_connections // 2
            )
            
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=300.0,    # SSE 流可能持续很久
                    write=10.0,
                    pool=10.0
                ),
                limits=limits,
                follow_redirects=True,
            )
        
        return self._client
    
    async def forward_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Dict,
        api_key: Optional[str] = None
    ) -> AsyncIterator[bytes]:
        """
        转发请求到上游服务器并流式返回响应
        
        Args:
            method: HTTP 方法
            url: 目标 URL
            headers: 原始请求头
            body: 请求体
            api_key: 上游 API 密钥（如果提供，将替换 Authorization 头）
        
        Yields:
            响应数据块（支持 SSE 流）
        
        Raises:
            UpstreamError: 上游服务器错误
        
        Note:
            - 如果 api_key 参数提供，将设置 Authorization 头为 "Bearer {api_key}"
            - 否则保留原始请求头中的 Authorization
        """
        client = await self._get_client()
        
        # 准备转发的请求头
        forward_headers = self._prepare_headers(headers, api_key, url)
        
        logger.info(
            "forwarding_request",
            method=method,
            url=url,
            has_api_key=api_key is not None
        )
        
        try:
            # 使用 stream 方法发送请求，支持流式响应
            async with client.stream(
                method=method,
                url=url,
                headers=forward_headers,
                json=body
            ) as response:
                # 记录响应状态
                logger.info(
                    "upstream_response_received",
                    status_code=response.status_code,
                    content_type=response.headers.get('content-type', '')
                )
                
                # 检查错误状态码
                if response.status_code >= 400:
                    # 读取错误响应体
                    error_body = await response.aread()
                    error_msg = error_body.decode('utf-8', errors='replace')
                    
                    logger.error(
                        "upstream_error_response",
                        status_code=response.status_code,
                        error=error_msg[:500]  # 限制日志长度
                    )
                    
                    # 对于 4xx 错误，透传给客户端
                    if 400 <= response.status_code < 500:
                        raise UpstreamError(
                            f"上游返回错误: {response.status_code}",
                            status_code=response.status_code,
                            upstream_url=url
                        )
                    else:
                        # 对于 5xx 错误，返回 502
                        raise UpstreamError(
                            f"上游服务器错误: {response.status_code}",
                            status_code=502,
                            upstream_url=url
                        )
                
                # 流式读取并返回响应
                logger.debug(
                    "streaming_response",
                    status_code=response.status_code,
                    content_type=response.headers.get('content-type', '')
                )
                
                async for chunk in response.aiter_bytes():
                    yield chunk
                    
        except httpx.TimeoutException as e:
            logger.error(
                "upstream_timeout",
                url=url,
                timeout=self.timeout,
                error=str(e)
            )
            raise UpstreamError(
                f"上游服务器超时: {url}",
                status_code=504,
                upstream_url=url
            )
        except httpx.ConnectError as e:
            logger.error(
                "upstream_connection_failed",
                url=url,
                error=str(e)
            )
            raise UpstreamError(
                f"无法连接到上游服务器: {url}",
                status_code=502,
                upstream_url=url
            )
        except httpx.HTTPStatusError as e:
            logger.error(
                "upstream_http_error",
                url=url,
                status_code=e.response.status_code,
                error=str(e)
            )
            raise UpstreamError(
                f"上游 HTTP 错误: {e.response.status_code}",
                status_code=502,
                upstream_url=url
            )
        except httpx.HTTPError as e:
            logger.error(
                "upstream_http_error",
                url=url,
                error=str(e)
            )
            raise UpstreamError(
                f"上游请求失败: {str(e)}",
                status_code=502,
                upstream_url=url
            )
    
    def _prepare_headers(self, headers: Dict[str, str], api_key: Optional[str], target_url: str) -> Dict[str, str]:
        """
        准备转发请求头
        
        只转发必要的头，不转发原始请求的 host/connection 等头，
        让 httpx 自动处理 Host 和 HTTP/2 伪头。
        
        Args:
            headers: 原始请求头
            api_key: API 密钥（可选）
            target_url: 目标 URL（用于提取 Host 头）
        
        Returns:
            处理后的请求头
        """
        # 只保留需要转发的头，白名单模式
        forward_headers = {}
        
        # 从原始请求中提取有用的头
        passthrough_headers = {
            'content-type',
            'accept',
            'anthropic-version',
            'anthropic-beta',
            'user-agent',
        }
        
        for key, value in headers.items():
            if key.lower() in passthrough_headers:
                forward_headers[key] = value
        
        # 设置认证头
        # Anthropic 使用 x-api-key，其他上游可能使用 Authorization: Bearer
        if api_key:
            forward_headers['x-api-key'] = api_key
            forward_headers['Authorization'] = f"Bearer {api_key}"
        
        # 禁用压缩，确保 SSE 流式数据能即时透传
        forward_headers['Accept-Encoding'] = 'identity'
        
        return forward_headers
    
    async def close(self):
        """关闭连接池"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("upstream_client_closed")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
