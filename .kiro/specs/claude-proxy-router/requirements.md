# Requirements Document

## Introduction

Claude Code 默认只能配置一个基础 URL，但在实际开发中，我们需要根据不同的模型将请求路由到不同的上游服务器。例如：
- Opus 模型转发到官方 API
- Sonnet 模型转发到低价代理
- Haiku 模型转发到另一个渠道

本项目旨在构建一个基于 FastAPI 的智能代理路由器，能够根据请求中的模型字段自动路由到相应的上游服务器，并完整支持 SSE 流式输出。

## Requirements

### Requirement 1: 本地代理服务

**User Story:** 作为 Claude Code 用户，我希望在本地运行一个代理服务，以便能够拦截并路由我的 Claude API 请求。

#### Acceptance Criteria

1. WHEN 系统启动时 THEN 系统 SHALL 在 `http://localhost:8000` 上监听 HTTP 请求
2. WHEN 服务运行时 THEN 系统 SHALL 能够接收发往 `/{path}` 的所有请求（主要是 `/v1/messages`）
3. IF 服务无法启动 THEN 系统 SHALL 提供清晰的错误信息并退出

### Requirement 2: 请求解析与模型识别

**User Story:** 作为系统，我需要从请求中提取模型信息，以便决定将请求路由到哪个上游服务器。

#### Acceptance Criteria

1. WHEN 收到 POST 请求到 `/v1/messages` THEN 系统 SHALL 解析 JSON Body 并提取 `model` 字段
2. WHEN 请求体不是有效的 JSON THEN 系统 SHALL 返回 400 错误并说明原因
3. WHEN 请求体缺少 `model` 字段 THEN 系统 SHALL 使用默认上游 URL 进行转发
4. WHEN 解析成功 THEN 系统 SHALL 记录请求的模型名称用于路由决策

### Requirement 3: 基于配置的路由匹配

**User Story:** 作为用户，我希望通过配置文件定义模型到上游 URL 的映射关系，以便灵活管理路由规则。

#### Acceptance Criteria

1. WHEN 系统启动时 THEN 系统 SHALL 加载配置文件中的模型到 URL 映射规则
2. WHEN 请求的模型匹配某个路由规则 THEN 系统 SHALL 使用该规则定义的上游 URL
3. IF 请求的模型不匹配任何规则 THEN 系统 SHALL 使用配置的默认上游 URL
4. WHEN 配置文件不存在或格式错误 THEN 系统 SHALL 提供清晰的错误信息并使用合理的默认值
5. WHEN 配置文件更新时 THEN 系统 SHALL 支持热重载配置而无需重启服务（可选）

### Requirement 3.1: API 密钥管理

**User Story:** 作为用户，我需要为不同的上游服务器配置不同的 API 密钥，以便正确认证到各个服务。

#### Acceptance Criteria

1. WHEN 配置路由规则时 THEN 系统 SHALL 支持为每个规则配置独立的 API 密钥
2. WHEN 配置 API 密钥时 THEN 系统 SHALL 支持从环境变量读取密钥（推荐方式）
3. IF 路由规则未配置 API 密钥 THEN 系统 SHALL 使用默认 API 密钥
4. WHEN 转发请求时 THEN 系统 SHALL 使用对应上游的 API 密钥替换原始 Authorization 头
5. IF 既未配置规则密钥也未配置默认密钥 THEN 系统 SHALL 保留原始请求头中的 Authorization
6. WHEN 从环境变量读取密钥失败 THEN 系统 SHALL 记录警告日志并继续运行

### Requirement 4: 透明转发与流式响应

**User Story:** 作为用户，我希望请求能够透明地转发到上游服务器，并实时接收流式响应，以保持与直接调用 API 一致的体验。

#### Acceptance Criteria

1. WHEN 转发请求时 THEN 系统 SHALL 保留原始请求头（包括 Authorization）和请求体
2. WHEN 上游服务器返回 SSE 流式响应 THEN 系统 SHALL 以流的形式透传给客户端
3. WHEN 上游服务器返回非流式响应 THEN 系统 SHALL 原样转发响应
4. IF 上游服务器连接失败 THEN 系统 SHALL 返回 502 错误并提供有用的错误信息
5. IF 上游服务器返回错误状态码 THEN 系统 SHALL 透传该状态码和错误信息

### Requirement 5: 错误处理与日志

**User Story:** 作为运维人员，我需要详细的日志和清晰的错误信息，以便排查问题和监控服务状态。

#### Acceptance Criteria

1. WHEN 请求处理过程中发生错误 THEN 系统 SHALL 记录详细的错误日志
2. WHEN 请求成功处理 THEN 系统 SHALL 记录请求的基本信息（模型、上游 URL、响应状态）
3. IF 日志系统配置 THEN 系统 SHALL 支持不同的日志级别（DEBUG、INFO、WARNING、ERROR）
4. WHEN 服务启动或关闭 THEN 系统 SHALL 记录相应的事件日志

### Requirement 6: 配置管理

**User Story:** 作为用户，我希望能轻松配置和管理路由规则，而不需要修改代码。

#### Acceptance Criteria

1. WHEN 系统启动时 THEN 系统 SHALL 从配置文件或环境变量读取配置
2. WHEN 配置路由规则时 THEN 系统 SHALL 支持基于模型名称前缀的匹配（如 `claude-3-opus*` 匹配所有 Opus 变体）
3. WHEN 配置上游 URL 时 THEN 系统 SHALL 验证 URL 格式的有效性
4. IF 配置了多个匹配规则 THEN 系统 SHALL 按照配置顺序使用第一个匹配的规则
