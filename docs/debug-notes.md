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

---

## CI/CD 相关

### GitHub Actions 发布 PyPI 版本号问题

**问题**：发布 v1.0.1、v1.0.2 时，PyPI 报错 `400 Bad Request`，构建产物版本号始终是 1.0.0。

**排查过程**：
1. v1.0.0 成功发布
2. v1.0.1 失败 - 发现 `dist/` 目录有旧文件
3. 添加 `rm -rf dist/` 清理步骤
4. v1.0.2 仍然失败 - 上传的还是 `claude_mux-1.0.0-py3-none-any.whl`
5. 检查 `pyproject.toml`，发现版本号硬编码为 `"1.0.0"`

**根因**：
1. `pyproject.toml` 中 `version = "1.0.0"` 是硬编码
2. `python -m build` 从 `pyproject.toml` 读取版本号
3. GitHub Actions 每次 checkout 是干净的代码，不会自动更新版本号
4. `dist/` 目录的旧文件没有被清理（第一个问题）
5. 即使清理了 dist/，构建出来的还是 1.0.0（第二个问题）

**解决方案**：在 workflow 中动态替换版本号

```yaml
- name: Set version from tag
  run: |
    TAG=${GITHUB_REF#refs/tags/}
    VERSION=${TAG#v}
    sed -i "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml
    cat pyproject.toml | grep "^version"

- name: Build package
  run: |
    rm -rf dist/           # 清理旧构建产物
    python -m build        # 构建新版本
```

**关键点**：
- GitHub Actions 的 `on: push: tags: - 'v*'` 触发时，`GITHUB_REF` 包含完整的 tag 引用
- `${GITHUB_REF#refs/tags/}` 提取 tag 名称（如 `v1.0.3`）
- `${TAG#v}` 去除 `v` 前缀得到版本号（如 `1.0.3`）
- `sed -i` 原地替换 pyproject.toml 中的版本号

**相关文件**：`.github/workflows/release.yml`

**相关 commit**：
- `6d70e16` fix(ci): Release workflow 先清理 dist 目录再构建
- `3adf581` fix(ci): 从 tag 自动设置 pyproject.toml 版本号

---

## 待补充

（后续修 bug 时持续记录）
