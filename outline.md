Claude Code 默认只能配一个基础 URL，但实际开发中，我们经常需要把 Opus 转发到官方，把 Sonnet 转发到某个低价代理，甚至把 Haiku 转发到另一个渠道。

为了实现这个目标，**Python 异步 Web 框架 (FastAPI) + 异步 HTTP 客户端 (httpx)** 是最完美的组合，特别是处理 LLM 必需的 **SSE (Server-Sent Events) 流式输出**时，性能非常好。


### 二、 技术方案设计

#### 1. 核心流程
1.  **启动本地服务**：监听 `http://localhost:8000`。
2.  **拦截请求**：捕获 Claude Code 发往 `/{path}` 的所有请求（主要是 `/v1/messages`）。
3.  **解析模型**：读取 POST 请求的 JSON Body，提取 `model` 字段（如 `claude-3-5-sonnet-20241022`）。
4.  **路由匹配**：根据配置文件，将该模型映射到对应的 `UPSTREAM_URL`（如果不匹配，则回退到默认 URL）。
5.  **透明转发与流式返回**：将请求头、鉴权信息和 Body 原样转发给目标 URL，并**将响应以流 (Stream) 的形式透传回 Claude Code**。