# ADR-002: 使用环境变量而非 YAML 文件进行配置

## 状态

已接受

## 背景

Claude Proxy Router 需要一种方式来管理配置，包括：
- 认证 Token
- 路由规则（模型 pattern 到上游 URL 的映射）
- 服务器设置（端口、日志级别）

## 决策

使用 `.env` 文件配合 `python-dotenv` 进行配置管理，而非 YAML 配置文件。

```bash
# .env 示例
AUTH_TOKEN=sk-proxy-xxx
DEFAULT_UPSTREAM=https://api.anthropic.com
SERVER_PORT=12346
ROUTE_NAMES=OPUS,SONNET,HAIKU
OPUS_PATTERN=claude-opus-*
OPUS_UPSTREAM=https://api.anthropic.com
OPUS_AUTH_TOKEN=sk-ant-xxx
```

## 理由

### 优势

1. **12-Factor App 原则**：配置与代码分离，环境变量是云原生应用的标准做法
2. **Kubernetes 友好**：可以轻松通过 ConfigMap、Secret 或容器环境变量注入配置
3. **无需额外解析**：python-dotenv 直接读取 .env 文件到环境变量
4. **部署灵活性**：同一份代码在不同环境（dev/staging/prod）使用不同配置
5. **密钥管理集成**：可以配合 Vault、AWS Secrets Manager 等密钥管理服务

### 劣势

1. **嵌套结构不便**：复杂嵌套配置（如多层路由规则）在 .env 中不够直观
2. **类型转换**：需要手动进行类型转换（如字符串到整数）
3. **IDE 支持**：.env 文件的 IDE 支持不如 YAML 完善

## 替代方案考虑

### YAML 配置文件

```yaml
# config.yaml
default_upstream: https://api.anthropic.com
routes:
  - pattern: claude-opus-*
    upstream: https://api.anthropic.com
    api_key: sk-ant-xxx
```

**否决原因**：
- 需要额外的依赖（PyYAML）
- 在 Kubernetes 中使用不如环境变量方便
- 密钥不能直接放在 YAML 中（需要额外的密钥注入机制）

### JSON 配置文件

**否决原因**：与 YAML 类似，且可读性更差。

## 后果

- 配置加载简单，只需 `load_dotenv()`
- 所有配置必须是扁平的键值对，不能有嵌套结构
- 路由规则通过命名约定（`{NAME}_PATTERN` 等）来组织
- 生产环境建议使用 Kubernetes Secret 或 Vault 管理敏感配置

## 相关决策

- 如果未来需要更复杂的配置结构，可以考虑引入 Pydantic Settings 来支持多种配置源
