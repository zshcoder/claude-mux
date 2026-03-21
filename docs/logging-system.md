# claude-mux 结构化日志系统详解

## 日志示例解析

```
2026-03-22T03:47:57.830198 [warning  ][8c132b80] 仍在等待上游响应 [main] func_name=warn_loop lineno=285 model=MiniMax-M2.7 note=仍在等待上游响应 request_path=v1/messages request_size=524732 thread=81072 total_elapsed=5.0 upstream_url=https://api.minimaxi.com/anthropic
```

| 字段 | 说明 |
|------|------|
| `2026-03-22T03:47:57.830198` | ISO 格式时间戳 |
| `[warning]` | 日志级别 |
| `[8c132b80]` | Request ID（8位UUID） |
| `仍在等待上游响应` | 翻译后的事件消息 |
| `[main]` | 日志器名称 |
| `func_name=warn_loop` | 调用函数名 |
| `lineno=285` | 代码行号 |
| `model=...` | 额外上下文字段 |

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                      日志数据流                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  logger.warning("still_waiting", model=..., note=...)      │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              structlog 处理器管道                    │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │ 1. merge_contextvars    ← 合并上下文变量            │   │
│  │ 2. add_logger_name      ← 添加日志器名 [main]       │   │
│  │ 3. add_log_level        ← 添加级别 [warning]        │   │
│  │ 4. TimeStamper          ← ISO 时间戳                │   │
│  │ 5. RequestIDRenderer    ← 提取 request_id 到前面    │   │
│  │ 6. CallsiteParameterAdder ← func_name/lineno/thread │   │
│  │ 7. MessageTranslateProcessor ← 英文→中文翻译        │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         ConsoleRendererWithRequestID                 │   │
│  │         (将 [request_id] 插入到级别后面)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│                     控制台输出                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 关键文件

| 文件 | 作用 |
|------|------|
| [logger.py](../logger.py) | 主日志配置、消息翻译、上下文绑定 |
| [request_id_logging.py](../request_id_logging.py) | Request ID 中间件和自定义渲染器 |

---

## 核心组件详解

### 1. structlog 初始化 ([logger.py:86-159](../logger.py#L86-L159))

```python
def setup_logging(level: str = "INFO", json_format: bool = False, lang: str = "zh", utc: bool = False):
    # 处理器管道
    shared_processors = [
        structlog.contextvars.merge_contextvars,      # 合并上下文
        structlog.stdlib.add_logger_name,             # [main]
        structlog.stdlib.add_log_level,               # [warning]
        structlog.processors.TimeStamper(fmt="iso"),  # 时间戳
        _RequestIDRenderer(),                         # request_id 提取
        CallsiteParameterAdder(parameters=[           # 调用位置
            CallsiteParameter.FUNC_NAME,              # func_name
            CallsiteParameter.LINENO,                 # lineno
            CallsiteParameter.THREAD,                 # thread
        ]),
        MessageTranslateProcessor(),                  # 中英文翻译
    ]

    # 渲染器选择
    if json_format:
        processors += [JSONRenderer()]      # 生产环境
    else:
        processors += [ConsoleRendererWithRequestID()]  # 开发环境
```

### 2. Request ID 中间件 ([request_id_logging.py:68-88](../request_id_logging.py#L68-L88))

每个 HTTP 请求自动生成唯一 ID，绑定到日志上下文：

```python
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 优先使用客户端传入的 x-request-id
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]

        # 绑定到 structlog 上下文（所有日志自动携带）
        bind_context(request_id=request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 3. 上下文绑定 ([logger.py:254-290](../logger.py#L254-L290))

```python
# 绑定上下文（后续所有日志自动携带）
bind_context(
    model="MiniMax-M2.7",
    request_path="v1/messages",
    request_size=524732,
    upstream_url="https://api.minimaxi.com/anthropic"
)

logger.warning("still_waiting_for_upstream", total_elapsed=5.0, note="仍在等待上游响应")
# 输出包含所有绑定的上下文字段

# 请求结束后清除
clear_context()
```

### 4. 中英文消息翻译 ([logger.py:70-83](../logger.py#L70-L83))

```python
_LOG_MESSAGES = {
    "still_waiting_for_upstream": ("仍在等待上游响应", "Still waiting for upstream response"),
    "request_received": ("收到请求", "Request received"),
    # ...
}

class MessageTranslateProcessor:
    def __call__(self, logger, method_name, event_dict):
        event = event_dict.get("event")
        if event in _LOG_MESSAGES:
            lang = event_dict.get("lang", "zh")
            zh_msg, en_msg = _LOG_MESSAGES[event]
            event_dict["event"] = zh_msg if lang == "zh" else en_msg
        return event_dict
```

### 5. 自定义渲染器 ([request_id_logging.py:116-167](../request_id_logging.py#L116-L167))

将 `[request_id]` 紧跟在日志级别后面：

```python
class ConsoleRendererWithRequestID:
    def __call__(self, logger, method_name, event_dict):
        request_id_tag = event_dict.pop("_request_id", None)

        # 调用默认渲染器
        output = self._default_renderer(logger, method_name, event_dict)

        # 将 request_id 插入到级别后面
        if request_id_tag:
            # 正则匹配: 2024-01-01T12:00:00 [warning]
            # 插入后:   2024-01-01T12:00:00 [warning][abc123]
            output = prefix + request_id_tag + remainder

        return output
```

---

## 警告循环机制

**场景**：上游响应慢时定期输出警告

### 执行时序图

```
时间线 ──────────────────────────────────────────────────────────────────►

主协程:  create_task() ──► send() await ───────────────────────────► 返回响应
             │                  │                                      │
             │                  │ 阻塞等待上游...                       │
             │                  │                                      │
warn_loop:   ├─ sleep(5s) ──► 检查 ──► warn ──► wait_for(5s) ──► 检查 ──► warn ──► ...
             │                  │         │                    │         │
             │                  │         │ 超时继续            │         │
             │                  │                              │         │
             │                  │        ◄── finally: warning_done.set() ◄┤
             │                  │                              │         │
             │                  │                              ▼         │
             │                  │                         break 退出     │
             │                  │                              │         │
             │                  │                         await warn_task ◄┤
```

### 核心代码详解

#### 第一步：准备阶段（请求发出前）

```python
# [main.py:277-279]
warning_delay = config.logging.upstream_wait_warning_delay      # 5.0 秒
repeat_interval = config.logging.upstream_wait_warning_repeat_interval  # 5.0 秒
warning_done = asyncio.Event()  # 事件对象，用于协程间通信
```

**`asyncio.Event()` 原理**：
- 类似一个信号灯，初始状态为「未设置」
- `warning_done.set()` → 设置为「已设置」
- `warning_done.is_set()` → 检查状态
- `await warning_done.wait()` → 阻塞直到被设置

#### 第二步：启动后台警告任务

```python
# [main.py:281-297]
async def warn_loop():
    # 1️⃣ 首次延迟：等待 5 秒后才输出第一条警告
    await asyncio.sleep(warning_delay)

    # 2️⃣ 循环检查
    while not warning_done.is_set():
        elapsed = time.time() - start_time
        logger.warning("still_waiting_for_upstream", total_elapsed=round(elapsed, 1))

        # 3️⃣ 等待通知或超时
        try:
            await asyncio.wait_for(
                asyncio.shield(warning_done.wait()),  # 🔑 关键：shield 保护
                timeout=repeat_interval
            )
            break  # wait() 成功返回 → Event 被设置了 → 退出循环
        except asyncio.TimeoutError:
            pass  # 超时 → 继续下一轮循环

# 4️⃣ 创建后台任务（非阻塞，立即返回）
warn_task = asyncio.create_task(warn_loop())
```

**关键点解析**：

| 技术点 | 作用 |
|--------|------|
| `asyncio.create_task()` | 将协程调度到事件循环，**立即返回** Task 对象 |
| `asyncio.wait_for(..., timeout=5)` | 等待最多 5 秒，超时抛 `TimeoutError` |
| `asyncio.shield(warning_done.wait())` | **保护**内部的 wait 不被取消，即使外部取消也能完成 |

**为什么要用 `asyncio.shield()`？**

```python
# 如果不用 shield，当 warn_task 被取消时：
# - warning_done.wait() 会被立即取消
# - 可能导致资源泄漏或状态不一致

# 用 shield 后：
# - 即使 warn_task 被取消，wait() 仍会正常完成
# - 确保状态转换的原子性
```

#### 第三步：主协程阻塞等待上游

```python
# [main.py:301]
upstream_resp = await http_client.send(req, stream=True)
# ☝️ 这里会阻塞，直到上游返回响应头
# 期间 warn_loop 在后台每 5 秒输出一条警告
```

**并发执行原理**：
```
┌─────────────────────────────────────────────────────────────┐
│                    asyncio 事件循环                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   Task 1: http_client.send()  ◄── 等待网络 I/O              │
│              │                                              │
│              │ 等待期间，事件循环切换到...                     │
│              ▼                                              │
│   Task 2: warn_loop()         ◄── 执行警告逻辑               │
│              │                                              │
│              │ sleep/wait_for 期间，切换回 Task 1            │
│              ▼                                              │
│   ...往复切换，直到 Task 1 的网络响应到达...                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 第四步：响应到达，清理后台任务

```python
# [main.py:326-342]
async def stream_upstream():
    try:
        async for chunk in upstream_resp.aiter_bytes(8192):
            yield chunk
    finally:
        # 🔑 清理步骤（无论成功或异常都会执行）

        # 1️⃣ 通知 warn_loop 退出
        warning_done.set()

        # 2️⃣ 等待 warn_loop 真正退出
        await warn_task

        # 3️⃣ 关闭上游连接
        await upstream_resp.aclose()

        # 4️⃣ 记录请求日志
        log_request(logger, model=model, ...)
        clear_context()
```

**为什么要 `await warn_task`？**

```python
warning_done.set()  # 只是设置标志，warn_loop 可能还在 sleep 或 wait_for 中

await warn_task     # 确保协程完全退出后才继续
                    # 避免资源泄漏和竞态条件
```

### 完整流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         请求处理流程                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. 请求到达                                                         │
│       │                                                             │
│       ▼                                                             │
│  2. bind_context(request_id, model, ...)                            │
│       │                                                             │
│       ▼                                                             │
│  3. warning_done = asyncio.Event()                                  │
│       │                                                             │
│       ▼                                                             │
│  4. warn_task = create_task(warn_loop())  ◄── 后台启动              │
│       │                                                             │
│       ▼                                                             │
│  5. await http_client.send(...)  ◀─────────────────────────────┐   │
│       │                         │                               │   │
│       │  主协程阻塞中...          │  warn_loop 并发运行：         │   │
│       │                         │  ├─ sleep(5s)                 │   │
│       │                         │  ├─ 输出警告                   │   │
│       │                         │  ├─ wait_for(5s) 或被 set     │   │
│       │                         │  └─ 循环...                   │   │
│       ▼                         │                               │   │
│  6. 上游响应到达 ◄───────────────┴───────────────────────────────┘   │
│       │                                                             │
│       ▼                                                             │
│  7. return StreamingResponse(stream_upstream())                     │
│       │                                                             │
│       │  流式传输数据...                                              │
│       │                                                             │
│       ▼                                                             │
│  8. finally:                                                        │
│       ├─ warning_done.set()    → 通知 warn_loop                     │
│       ├─ await warn_task       → 等待退出                           │
│       ├─ await upstream_resp.aclose()                               │
│       ├─ log_request(...)                                            │
│       └─ clear_context()                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 配置

**配置项** ([config.py:69-70](../config.py#L69-L70)):

```python
upstream_wait_warning_delay: float = 5.0          # 首次警告延迟
upstream_wait_warning_repeat_interval: float = 5.0  # 重复间隔
```

**环境变量**:
```bash
UPSTREAM_WAIT_WARNING_DELAY=5.0
UPSTREAM_WAIT_WARNING_REPEAT_INTERVAL=5.0
```

### 为什么不用 threading.Timer？

| 对比项 | asyncio (当前方案) | threading.Timer |
|--------|-------------------|-----------------|
| 线程安全 | ✅ 单线程，无竞态 | ⚠️ 需要 Lock |
| 资源开销 | ✅ 轻量协程 | ❌ 每个定时器一个线程 |
| 取消机制 | ✅ Event + await | ⚠️ cancel() 不够优雅 |
| 与异步框架集成 | ✅ 原生支持 | ❌ 需要 run_in_executor |

---

## 使用示例

### 基本使用

```python
from logger import get_logger, bind_context, clear_context

logger = get_logger("main")

# 简单日志
logger.info("request_received", model="claude-3-opus")

# 带上下文的请求处理
bind_context(request_id="abc123", user_id="user456")
logger.info("processing_request")  # 自动包含 request_id, user_id
clear_context()
```

### 请求日志

```python
from logger import log_request

log_request(
    logger,
    model="MiniMax-M2.7",
    upstream_url="https://api.minimaxi.com/anthropic",
    status_code=200,
    duration=1.23
)
# 状态码 >= 500: error
# 状态码 >= 400: warning
# 状态码 < 400:  info
```

---

## 配置选项

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_FORMAT` | `console` | `console` 或 `json` |
| `LOG_LANG` | `zh` | `zh` 或 `en` |
| `LOG_UTC` | `false` | 是否使用 UTC 时间 |
| `UPSTREAM_WAIT_WARNING_DELAY` | `5.0` | 上游等待警告首次延迟（秒） |
| `UPSTREAM_WAIT_WARNING_REPEAT_INTERVAL` | `5.0` | 重复警告间隔（秒） |

---

## 依赖

```toml
[project.dependencies]
structlog = ">=24.0.0"
```

---

## 设计优势

1. **结构化输出**：所有日志字段都是 key=value 形式，便于解析和查询
2. **请求追踪**：Request ID 贯穿请求全生命周期
3. **调用位置**：自动记录函数名和行号，快速定位问题
4. **多语言支持**：中英文消息一键切换
5. **上下文隔离**：每个请求的上下文独立，不会互相干扰
6. **异步友好**：警告循环不阻塞主请求处理
