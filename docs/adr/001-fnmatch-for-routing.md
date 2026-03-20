# ADR-001: 使用 fnmatch 而非正则表达式进行路由匹配

## 状态

已接受

## 背景

Claude Proxy Router 需要根据模型名称将请求路由到不同的上游服务器。模型名称示例：
- `claude-opus-20240229`
- `claude-sonnet-20241022`
- `glm-4-flash`
- `MiniMax-M2`

路由规则需要支持简单的通配符匹配，如 `claude-opus-*` 匹配所有 Opus 模型。

## 决策

使用 Python 标准库的 `fnmatch` 模块进行路由匹配，而非正则表达式。

```python
import fnmatch

# 示例
fnmatch.fnmatch("claude-opus-20240229".lower(), "claude-opus-*".lower())  # True
fnmatch.fnmatch("glm-4-flash".lower(), "glm-*".lower())  # True
```

## 理由

### 优势

1. **简单性**：fnmatch 语法直观易懂，`*` 匹配任意字符，`?` 匹配单个字符
2. **无需转义**：正则表达式的特殊字符（如 `.`、`+`）在 fnmatch 中不需要转义
3. **配置友好**：用户更容易写出正确的 pattern，如 `claude-opus-*` 而不是 `claude-opus-.*`
4. **性能**：对于简单模式，fnmatch 比正则表达式更快

### 劣势

1. **功能有限**：不支持复杂的匹配规则（如 `claude-(opus|sonnet)-*`）
2. **贪婪匹配**：`*` 是贪婪的，可能导致意外匹配

## 后果

- 用户配置路由规则时更简单直观
- 不支持需要复杂匹配规则的场景（需要扩展时可以添加正则支持）
- 匹配是大小写不敏感的（转换为小写后匹配）

## 相关决策

- 如果未来需要更复杂的路由规则，可以考虑添加 `regex:` 前缀支持正则表达式
