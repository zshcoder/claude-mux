# 调试笔记

## 文件说明

本文件记录修 bug 过程中发现的**珍贵经验**、**易错点**、**关键注意事项**。
这些内容来自实际调试过程，是团队或个人经验的沉淀。

---

## 记录规则

1. **抓住重点**：不要过于详细，核心是"这个问题是怎么发现的"、"根因是什么"、"解决方案是什么"
2. **分类清晰**：按问题类型分类，便于未来检索
3. **可执行**：记录能指导未来类似问题的解决方案

---

## Python 相关

### 环境变量在子进程中重置

**问题**：模块级全局变量在 uvicorn 多进程模式下被重置为默认值。

**场景**：`main.py` 中用全局变量 `_log_lang` 存储命令行参数，但 uvicorn 会创建子进程，子进程中该变量被重置。

**根因**：Python 模块在子进程中被重新导入，全局变量恢复默认值。

**解决方案**：用环境变量传递关键配置，子进程可通过 `os.environ.get()` 读取。

**相关 commit**：419922d

---

## Python 相关

### uvicorn 使用字符串导入导致中间件不生效

**问题**：添加了 RequestIDMiddleware 但请求中没有 request_id，日志也不显示。

**排查过程**：
1. 独立测试 `bind_context` + 日志输出正常
2. RequestIDRenderer 和 _ConsoleRendererWithRequestID 单独测试正常
3. 但服务器运行时就是不显示 request_id

**根因**：`uvicorn.run("main:app", ...)` 使用字符串导入会创建新的 app 实例，而 `configure_app()` 是对旧实例操作的。

```python
# 错误写法 - 会创建新实例
uvicorn.run("main:app", host="0.0.0.0", port=12346)

# 正确写法 - 直接传递实例
uvicorn.run(app, host="0.0.0.0", port=12346)
```

**相关文件**：main.py

---

### structlog ConsoleRenderer 输出包含 ANSI 转义序列

**问题**：正则匹配日志级别 `[info]` 失败，导致 request_id 无法正确插入。

**排查**：ConsoleRenderer 输出类似：
```
\x1b[2m2026-03-21T00:12:22.146140\x1b[0m [\x1b[32m\x1b[1minfo     \x1b[0m] ...
```

**根因**：structlog 的 ConsoleRenderer 默认输出包含 ANSI 颜色转义序列，正则 `\w+` 无法匹配包含颜色代码的文本。

**解决方案**：
1. 先用 ANSI 转义序列正则去除颜色代码
2. 在纯净文本上做正则匹配
3. 根据纯净文本的匹配位置，在原始输出中插入内容

```python
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

def insert_after_level(output, request_id_tag):
    clean = ANSI_ESCAPE.sub('', output)
    match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+ \[)(\w+)(\s*\])', clean)
    if match:
        # 计算原始输出中的位置并插入
        ...
```

---

## 通用模块

### request_id_logging.py - Request ID 日志增强

**文件位置**：`request_id_logging.py`

**功能**：
- 自动生成请求唯一 ID（支持客户端传入 x-request-id）
- 绑定到 structlog 上下文，所有日志自动携带
- request_id 紧跟日志级别显示，便于追踪并发请求
- 支持配置颜色和前缀格式
- 通用模块，可直接复制到其他项目使用

#### 快速开始

```bash
# 1. 复制 request_id_logging.py 到项目根目录

# 2. 修改 main.py
from request_id_logging import setup_request_id_logging, RequestIDMiddleware

# 在应用创建后、uvicorn.run 之前调用
setup_request_id_logging(level="INFO")

# 添加中间件
app.add_middleware(RequestIDMiddleware)

# 3. 启动服务
uvicorn.run(app, host="0.0.0.0", port=8000)  # 注意：直接传 app，不是字符串！
```

#### 完整集成示例

```python
# main.py
import argparse
from fastapi import FastAPI
from request_id_logging import setup_request_id_logging, RequestIDMiddleware

app = FastAPI()

# 命令行参数
parser = argparse.ArgumentParser()
parser.add_argument("--request-id-prefix", action="store_true", help="显示 request_id= 前缀")
args = parser.parse_args()

# 初始化日志（必须在其他日志调用之前）
setup_request_id_logging(
    level="INFO",
    show_request_id_prefix=args.request_id_prefix
)

# 添加中间件
app.add_middleware(RequestIDMiddleware)

@app.post("/api")
async def api_handler():
    # 所有日志都会自动包含 request_id
    logger.info("处理请求")  # 输出: [info][abc123] 处理请求
    ...

uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 如果项目已有 structlog 配置

```python
# 不想用 setup_request_id_logging？也可以只导入组件

from request_id_logging import RequestIDMiddleware, RequestIDRenderer, ConsoleRendererWithRequestID
from your_logger import setup_logging  # 你的现有配置函数

# 在你的 setup_logging 中添加这些 processor
def setup_logging_with_request_id(...):
    # 原有 processors...
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        RequestIDRenderer(),  # 添加这个
        # ... 其他 processors
        ConsoleRendererWithRequestID(colors=True)  # 替换原有的 ConsoleRenderer
    ]
    structlog.configure(processors=processors, ...)

# 中间件单独添加
app.add_middleware(RequestIDMiddleware)
```

#### 配置项

| 配置项 | 位置 | 说明 |
|--------|------|------|
| `REQUEST_ID_PREFIX` | 文件顶部 | `False`=显示 `[abc123]`，`True`=显示 `[request_id=abc123]` |
| `REQUEST_ID_COLOR` | 文件顶部 | ANSI 颜色代码，默认 `\x1b[33m`（黄色） |

**颜色代码参考**：

| 代码 | 颜色 |
|------|------|
| `\x1b[31m` | 红色 |
| `\x1b[32m` | 绿色 |
| `\x1b[33m` | 黄色（默认） |
| `\x1b[34m` | 蓝色 |
| `\x1b[35m` | 洋红 |
| `\x1b[36m` | 青色 |

#### API 参考

**`setup_request_id_logging(level, json_format, lang, utc, show_request_id_prefix)`**

配置 structlog 日志系统（带 request_id 支持）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `level` | str | `"INFO"` | 日志级别 |
| `json_format` | bool | `False` | 是否输出 JSON 格式 |
| `lang` | str | `"zh"` | 日志语言 |
| `utc` | bool | `False` | 是否使用 UTC 时间 |
| `show_request_id_prefix` | bool | `False` | 是否显示 `request_id=` 前缀 |

**`RequestIDMiddleware`**

FastAPI/Starlette 中间件，自动生成/绑定 request_id。

**`RequestIDRenderer`**

structlog processor，从上下文提取 request_id 并标记位置。

**`ConsoleRendererWithRequestID`**

structlog renderer，将 request_id 插入到日志级别后面。

---

## 待补充

（后续修 bug 时持续记录）
