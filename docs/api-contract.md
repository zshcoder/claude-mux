# API Contract

本文档定义 Claude Proxy Router 的 API 契约，包括请求格式、响应格式和错误处理。

## 目录

- [认证](#认证)
- [代理端点](#代理端点)
- [健康检查](#健康检查)
- [错误响应格式](#错误响应格式)

---

## 认证

### 请求头认证

所有请求必须包含以下认证头之一：

| 头名称 | 示例 | 描述 |
|--------|------|------|
| `x-api-key` | `x-api-key: sk-proxy-abc123...` | 推荐方式 |
| `Authorization` | `Authorization: Bearer sk-proxy-abc123...` | 备用方式 |

### 认证失败

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": {
    "type": "validation_error",
    "message": "认证失败: Invalid token"
  }
}
```

---

## 代理端点

### `POST /{path}`

代理所有请求到相应的上游服务器。

#### 请求

```http
POST /v1/messages HTTP/1.1
Host: localhost:12346
Content-Type: application/json
x-api-key: sk-proxy-your-token

{
  "model": "glm-4",
  "messages": [
    {"role": "user", "content": "你好！"}
  ],
  "max_tokens": 100,
  "stream": false
}
```

#### 请求体字段

| 字段 | 类型 | 必需 | 描述 |
|------|------|------|------|
| `model` | string | **是** | 模型名称，用于路由匹配 |
| `messages` | array | 是 | 消息列表 |
| `max_tokens` | integer | 是 | 最大生成 token 数 |
| `stream` | boolean | 否 | 是否使用 SSE 流式响应（默认 false） |
| `temperature` | float | 否 | 采样温度（0-1） |
| `system` | string | 否 | 系统提示词 |

#### 响应（非流式）

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "content": [
    {"type": "text", "text": "你好！有什么可以帮助你的吗？"}
  ],
  "model": "glm-4",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 25
  }
}
```

#### 响应（SSE 流式）

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no

event: message_start
data: {"type":"message_start","message":{"id":"msg_abc123",...}}

event: content_block_start
data: {"type":"content_block_start","index":0,"type":"content_block","content":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"你"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"好！"}}

event: message_stop
data: {}
```

---

## 健康检查

### `GET /health/live`

存活探针（Liveness Probe），判断服务进程是否存活。

```http
GET /health/live HTTP/1.1

{
  "status": "healthy",
  "service": "claude-proxy-router"
}
```

### `GET /health/ready`

就绪探针（Readiness Probe），检查上游服务连通性。

```http
GET /health/ready HTTP/1.1

{
  "status": "healthy",
  "service": "claude-proxy-router",
  "routes_count": 3,
  "upstreams": {
    "default": {"healthy": true, "status_code": 200},
    "claude-opus-*": {"healthy": true, "status_code": 200},
    "glm-*": {"healthy": true, "status_code": 200}
  }
}
```

### `GET /health`

向后兼容的健康检查端点（等同于 `/health/live`）。

---

## 错误响应格式

所有错误响应都使用统一的 JSON 格式：

```json
{
  "error": {
    "type": "<error_type>",
    "message": "<错误描述>",
    "<额外字段>": "<可选的额外信息>"
  }
}
```

### 错误类型

| type 值 | HTTP 状态码 | 描述 |
|---------|-------------|------|
| `validation_error` | 400 | 请求验证失败（无效 JSON、缺少 model 字段等） |
| `routing_error` | 400 | 路由匹配错误 |
| `upstream_error` | 502 | 上游服务器错误（连接失败、超时、5xx 响应） |
| `proxy_error` | 500 | 代理内部错误 |
| `internal_error` | 500 | 未预期的内部错误 |

### 错误响应示例

#### 400 - 无效 JSON

```json
{
  "error": {
    "type": "validation_error",
    "message": "请求体不是有效的 JSON"
  }
}
```

#### 400 - 缺少 model 字段

```json
{
  "error": {
    "type": "validation_error",
    "message": "请求体缺少 model 字段"
  }
}
```

#### 401 - 认证失败

```json
{
  "error": {
    "type": "validation_error",
    "message": "认证失败: Invalid token"
  }
}
```

#### 502 - 上游连接失败

```json
{
  "error": {
    "type": "upstream_error",
    "message": "无法连接到上游服务器: https://api.example.com",
    "upstream_url": "https://api.example.com"
  }
}
```

#### 502 - 上游返回 5xx

```json
{
  "error": {
    "type": "upstream_error",
    "message": "上游服务器错误: 502",
    "upstream_url": "https://api.anthropic.com"
  }
}
```

#### 500 - 内部错误

```json
{
  "error": {
    "type": "internal_error",
    "message": "内部服务器错误: Unexpected error"
  }
}
```

---

## 状态码总结

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功（可能是流式响应） |
| 400 | 请求格式错误或缺少必需字段 |
| 401 | 认证失败 |
| 502 | 上游服务器错误 |
| 504 | 上游服务器超时 |
| 500 | 代理内部错误 |
