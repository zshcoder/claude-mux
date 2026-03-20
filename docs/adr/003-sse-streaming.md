# ADR-003: SSE 流式响应处理设计

## 状态

已接受

## 背景

Claude API 支持 Server-Sent Events (SSE) 流式响应，客户端可以实时获取生成的内容，而不需要等待完整响应。

```bash
# 启用流式响应
curl -X POST https://api.anthropic.com/v1/messages \
  -d '{"stream": true, ...}'
```

代理需要透明地转发这些 SSE 流。

## 决策

使用 httpx 的异步流式 API 原生转发 SSE 响应，不在代理层解析或修改 SSE 事件。

```python
async def forward_request(...):
    async with client.stream(method, url, ...) as response:
        async for chunk in response.aiter_bytes():
            yield chunk
```

## 关键设计点

### 1. 流式转发而非缓冲

```python
# 正确：流式转发
async for chunk in response.aiter_bytes():
    yield chunk

# 错误：先读完再发送
body = await response.aread()  # 这会阻塞直到完整响应
yield body
```

### 2. 禁用压缩解压缩

```python
forward_headers['Accept-Encoding'] = 'identity'
```

确保代理服务器不会自动解压缩 SSE 流，避免引入额外延迟。

### 3. 设置适当的缓冲头

```python
response_headers["Cache-Control"] = "no-cache"
response_headers["X-Accel-Buffering"] = "no"
```

通知下游代理（如 Nginx）不要缓冲 SSE 流。

### 4. 长连接超时

```python
httpx.Timeout(
    connect=10.0,
    read=300.0,    # SSE 流可能持续很久
    write=10.0,
    pool=10.0
)
```

SSE 流式响应的读取超时需要设置较长，因为 AI 生成可能需要几分钟。

## 理由

1. **低延迟**：流式转发确保数据即时到达客户端
2. **低内存**：不需要在内存中缓冲完整响应
3. **透明代理**：不解析 SSE 内容，保持与上游 API 的完全兼容
4. **简单实现**：不需要理解 SSE 协议细节

## 潜在问题

### 1. 错误处理复杂

流式响应一旦开始发送就不能改变状态码。解决方案：
- 在开始流式传输前验证请求
- 上游返回错误状态码时抛出异常

### 2. 连接中断处理

如果上游在流式传输过程中断开连接，httpx 会抛出异常。日志记录即可。

### 3. 背压 (Backpressure)

如果客户端接收速度慢于上游发送速度，可能导致问题。当前实现依赖 httpx 的背压机制。

## 后果

- 代理保持对 SSE 内容的完全透明
- 客户端收到的 SSE 事件与直接调用上游相同
- 代理的内存使用与响应大小无关
- 需要配置较长的读超时以支持长时间流式响应
