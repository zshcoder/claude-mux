"""
错误定义模块

定义代理路由器中使用的所有自定义异常类。
"""


class ProxyError(Exception):
    """
    代理错误基类
    
    所有代理相关的错误都应继承此类。
    """
    
    def __init__(self, message: str, status_code: int = 500):
        """
        初始化代理错误
        
        Args:
            message: 错误消息
            status_code: HTTP 状态码
        """
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ConfigError(ProxyError):
    """
    配置错误
    
    当配置文件格式错误、缺少必需字段或配置无效时抛出。
    """
    
    def __init__(self, message: str):
        """
        初始化配置错误
        
        Args:
            message: 错误消息
        """
        super().__init__(message, status_code=500)


class UpstreamError(ProxyError):
    """
    上游服务器错误
    
    当与上游服务器通信失败时抛出，包括连接失败、超时、上游返回错误等。
    """
    
    def __init__(self, message: str, status_code: int = 502, upstream_url: str = None):
        """
        初始化上游错误
        
        Args:
            message: 错误消息
            status_code: HTTP 状态码（默认 502 Bad Gateway）
            upstream_url: 上游服务器 URL（可选，用于日志记录）
        """
        self.upstream_url = upstream_url
        super().__init__(message, status_code)


class RoutingError(ProxyError):
    """
    路由错误
    
    当路由匹配失败或路由配置有问题时抛出。
    """
    
    def __init__(self, message: str, status_code: int = 400):
        """
        初始化路由错误
        
        Args:
            message: 错误消息
            status_code: HTTP 状态码（默认 400 Bad Request）
        """
        super().__init__(message, status_code)


class RequestValidationError(ProxyError):
    """
    请求验证错误
    
    当请求格式无效或缺少必需字段时抛出。
    """
    
    def __init__(self, message: str):
        """
        初始化请求验证错误
        
        Args:
            message: 错误消息
        """
        super().__init__(message, status_code=400)
