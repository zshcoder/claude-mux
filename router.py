"""
模型路由器模块

负责根据模型名称匹配路由规则，返回对应的上游 URL 和 API 密钥。
支持通配符匹配（使用 fnmatch）。
"""

import fnmatch
from typing import Optional, Tuple

from config import Config, RouteRule
from errors import RoutingError
from logger import get_logger

logger = get_logger(__name__)


class ModelRouter:
    """
    模型路由器
    
    根据模型名称匹配路由规则，返回对应的上游 URL 和 API 密钥。
    """
    
    def __init__(self, config: Config):
        """
        初始化路由器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        logger.info(
            "router_initialized",
            routes_count=len(config.routes),
            default_upstream=config.default_upstream
        )
    
    def get_upstream_url(self, model: str) -> str:
        """
        根据模型名称获取上游 URL
        
        Args:
            model: 模型名称（如 "claude-3-opus-20240229"）
        
        Returns:
            匹配的上游 URL，若无匹配则返回默认 URL
        
        Example:
            >>> router.get_upstream_url("claude-3-opus-20240229")
            "https://api.anthropic.com"
        """
        route = self._match_route(model)
        if route:
            logger.debug(
                "route_matched",
                model=model,
                upstream_url=route.upstream_url,
                pattern=route.pattern
            )
            return route.upstream_url
        
        # 未匹配到任何路由，抛出错误而不是使用默认上游
        raise RoutingError(
            f"模型 '{model}' 未匹配到任何路由配置，请检查 ROUTE_NAMES 和对应的 PATTERN 配置",
            model=model,
            available_patterns=[r.pattern for r in self.config.routes]
        )
    
    def get_api_key(self, model: str) -> Optional[str]:
        """
        根据模型名称获取对应的 API 密钥
        
        Args:
            model: 模型名称
        
        Returns:
            API 密钥，若无匹配则抛出 RoutingError
        
        Example:
            >>> router.get_api_key("claude-3-opus-20240229")
            "sk-ant-xxx"
        """
        route = self._match_route(model)
        
        if not route:
            raise RoutingError(
                f"模型 '{model}' 未匹配到任何路由配置，请检查 ROUTE_NAMES 和对应的 PATTERN 配置",
                model=model,
                available_patterns=[r.pattern for r in self.config.routes]
            )
        
        api_key = self.config.get_api_key(route)
        
        if api_key:
            logger.debug(
                "api_key_found",
                model=model,
                has_route=route is not None
            )
        else:
            logger.warning(
                "api_key_not_found",
                model=model,
                has_route=route is not None
            )
        
        return api_key
    
    def get_route_info(self, model: str) -> Tuple[str, Optional[str]]:
        """
        获取完整的路由信息（上游 URL 和 API 密钥）
        
        Args:
            model: 模型名称
        
        Returns:
            元组 (upstream_url, api_key)
        
        Example:
            >>> router.get_route_info("claude-3-opus-20240229")
            ("https://api.anthropic.com", "sk-ant-xxx")
        """
        route = self._match_route(model)
        
        if not route:
            raise RoutingError(
                f"模型 '{model}' 未匹配到任何路由配置，请检查 ROUTE_NAMES 和对应的 PATTERN 配置",
                model=model,
                available_patterns=[r.pattern for r in self.config.routes]
            )
        
        upstream_url = route.upstream_url
        api_key = self.config.get_api_key(route)
        
        return upstream_url, api_key
    
    def _match_route(self, model: str) -> Optional[RouteRule]:
        """
        匹配路由规则
        
        按配置顺序匹配，返回第一个匹配的规则。
        
        Args:
            model: 模型名称
        
        Returns:
            匹配的路由规则，若无匹配则返回 None
        """
        for route in self.config.routes:
            if self._match_pattern(model, route.pattern):
                return route
        
        return None
    
    @staticmethod
    def _match_pattern(model: str, pattern: str) -> bool:
        """
        匹配模型名称和模式
        
        使用 fnmatch 进行通配符匹配。
        
        Args:
            model: 模型名称
            pattern: 匹配模式（支持通配符 * 和 ?）
        
        Returns:
            是否匹配
        
        Examples:
            >>> ModelRouter._match_pattern("claude-3-opus-20240229", "claude-3-opus*")
            True
            >>> ModelRouter._match_pattern("claude-3-5-sonnet-20241022", "claude-3-opus*")
            False
            >>> ModelRouter._match_pattern("claude-3-haiku-20240307", "claude-*")
            True
        """
        return fnmatch.fnmatch(model.lower(), pattern.lower())
    
    def add_route(self, pattern: str, upstream_url: str, api_key: Optional[str] = None):
        """
        动态添加路由规则
        
        Args:
            pattern: 模型匹配模式
            upstream_url: 上游 URL
            api_key: API 密钥（可选）
        
        Example:
            >>> router.add_route("claude-4-*", "https://future-proxy.example.com")
        """
        route = RouteRule(
            pattern=pattern,
            upstream_url=upstream_url,
            api_key=api_key
        )
        self.config.routes.append(route)
        
        logger.info(
            "route_added",
            pattern=pattern,
            upstream_url=upstream_url
        )
    
    def list_routes(self) -> list:
        """
        列出所有路由规则
        
        Returns:
            路由规则列表
        """
        return [
            {
                "pattern": route.pattern,
                "upstream_url": route.upstream_url,
                "has_api_key": route.api_key is not None
            }
            for route in self.config.routes
        ]
