# Request ID 日志增强模块

`request_id_logging.py` 是一个通用模块，可直接复制到其他项目使用，为 FastAPI/Starlette 应用添加请求追踪功能。

## 功能

- 自动生成请求唯一 ID（支持客户端传入 `x-request-id`）
- 绑定到 structlog 上下文，所有日志自动携带
- request_id 紧跟日志级别显示，便于追踪并发请求
- 支持配置颜色和前缀格式

## 快速开始

### 1. 复制文件

将 `request_id_logging.py` 复制到项目根目录。

### 2. 修改 main.py

```python
from fastapi import FastAPI
from request_id_logging import setup_request_id_logging, RequestIDMiddleware

app = FastAPI()

# 初始化日志（必须在其他日志调用之前）
setup_request_id_logging(level="INFO")

# 添加中间件
app.add_middleware(RequestIDMiddleware)

# 启动服务
# 注意：uvicorn.run(app, ...) 直接传 app，不是字符串！
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. 查看效果

```
2026-03-21T00:28:23.221204 [info     ][abc123] 收到请求  [main] path=/api ...
```

## 完整集成示例

```python
import argparse
from fastapi import FastAPI
from request_id_logging import setup_request_id_logging, RequestIDMiddleware
import structlog

app = FastAPI()

# 命令行参数
parser = argparse.ArgumentParser()
parser.add_argument("--request-id-prefix", action="store_true", help="显示 request_id= 前缀")
args = parser.parse_args()

# 初始化日志
setup_request_id_logging(
    level="INFO",
    show_request_id_prefix=args.request_id_prefix
)

# 添加中间件
app.add_middleware(RequestIDMiddleware)

@app.post("/api")
async def api_handler():
    # 所有日志都会自动包含 request_id
    logger = structlog.get_logger(__name__)
    logger.info("处理请求")  # 输出: [info][abc123] 处理请求
    ...

uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 与现有 structlog 配置集成

如果项目已有 structlog 配置，可以只导入组件：

```python
from request_id_logging import RequestIDMiddleware, RequestIDRenderer, ConsoleRendererWithRequestID
from your_logger import setup_logging  # 你的现有配置函数

# 在你的 setup_logging 中替换 ConsoleRenderer
processors = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    RequestIDRenderer(),  # 添加这个
    # ... 其他 processors
    ConsoleRendererWithRequestID(colors=True),  # 替换原有的 ConsoleRenderer
]
structlog.configure(processors=processors, ...)

# 中间件单独添加
app.add_middleware(RequestIDMiddleware)
```

## 配置项

在文件顶部修改：

```python
REQUEST_ID_PREFIX = False      # False=显示 [abc123]，True=显示 [request_id=abc123]
REQUEST_ID_COLOR = "\x1b[33m" # ANSI 颜色代码
```

### 颜色代码参考

| 代码 | 颜色 |
|------|------|
| `\x1b[31m` | 红色 |
| `\x1b[32m` | 绿色 |
| `\x1b[33m` | 黄色（默认） |
| `\x1b[34m` | 蓝色 |
| `\x1b[35m` | 洋红 |
| `\x1b[36m` | 青色 |

## API 参考

### setup_request_id_logging()

配置 structlog 日志系统（带 request_id 支持）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | str | `"INFO"` | 日志级别 |
| `json_format` | bool | `False` | 是否输出 JSON 格式 |
| `lang` | str | `"zh"` | 日志语言 |
| `utc` | bool | `False` | 是否使用 UTC 时间 |
| `show_request_id_prefix` | bool | `False` | 是否显示 `request_id=` 前缀 |

### RequestIDMiddleware

FastAPI/Starlette 中间件，自动生成/绑定 request_id。

- 优先使用客户端传入的 `x-request-id`
- 无则自动生成 UUID（截取前 8 位）
- 绑定到 structlog 上下文
- 在响应头中返回 `X-Request-ID`

### RequestIDRenderer

structlog processor，从上下文提取 request_id 并标记位置。

### ConsoleRendererWithRequestID

structlog renderer，将 request_id 插入到日志级别后面。

## 常见问题

### Q: 日志中没有显示 request_id？

检查是否正确添加了中间件：

```python
app.add_middleware(RequestIDMiddleware)  # 必须！
```

同时确保 `uvicorn.run()` 直接传 app 对象，而不是字符串：

```python
# 错误
uvicorn.run("main:app", ...)

# 正确
uvicorn.run(app, ...)
```

### Q: request_id 显示在错误的位置？

确保 `RequestIDRenderer` 在 `TimeStamper` 之后、最终 renderer 之前。
