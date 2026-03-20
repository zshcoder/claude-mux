# ADR-004: 统一错误响应格式

## 状态

已接受

## 背景

Claude Proxy Router 在处理错误时有多种不同的响应格式：

```python
# 格式1：纯文本
return Response(content="错误消息", media_type="text/plain")

# 格式2：简化的 JSON
return Response(content='{"error":{"type":"proxy_error","message":"..."}}')

# 格式3：异常对象的 message
return Response(content=exc.message, media_type="text/plain")
```

这种不一致性使得客户端难以处理错误。

## 决策

所有错误响应使用统一的 JSON 格式：

```json
{
  "error": {
    "type": "<error_type>",
    "message": "<错误描述>",
    "<可选额外字段>": "<值>"
  }
}
```

所有自定义异常继承 `ProxyError` 基类，提供 `to_json()` 方法：

```python
class ProxyError(Exception):
    error_type: str = "proxy_error"

    def __init__(self, message: str, status_code: int = 500, **extra):
        self.message = message
        self.status_code = status_code
        self.extra = extra

    def to_dict(self) -> dict:
        error_obj = {
            "type": self.error_type,
            "message": self.message,
        }
        error_obj.update(self.extra)
        return {"error": error_obj}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
```

## 错误类型

| type 值 | HTTP 状态码 | 使用场景 |
|---------|-------------|----------|
| `validation_error` | 400 | 请求验证失败 |
| `routing_error` | 400 | 路由匹配问题 |
| `upstream_error` | 502 | 上游服务器错误 |
| `proxy_error` | 500 | 代理内部错误 |
| `internal_error` | 500 | 未预期的内部错误 |

## 示例响应

### 400 - 缺少 model 字段

```json
{
  "error": {
    "type": "validation_error",
    "message": "请求体缺少 model 字段"
  }
}
```

### 502 - 上游连接失败

```json
{
  "error": {
    "type": "upstream_error",
    "message": "无法连接到上游服务器: https://api.example.com",
    "upstream_url": "https://api.example.com"
  }
}
```

## 理由

1. **一致性**：所有错误响应格式统一，客户端容易解析
2. **可扩展性**：通过 `extra` 字段可以添加额外信息
3. **标准化**：符合 RFC 7807 Problem Details 思想
4. **调试友好**：包含足够的信息用于问题诊断

## 后果

- 所有 HTTP 响应始终使用 `application/json` content-type
- 异常处理器统一使用 `exc.to_json()` 返回错误
- 日志中记录完整的错误上下文
- 客户端可以依赖统一的错误格式进行错误处理

## 相关决策

- 考虑未来支持 RFC 7807 的完整 Problem Details 格式（添加 `type`、`instance`、`status` 字段）
