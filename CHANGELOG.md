# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **文档**：新增 `docs/` 目录，包含完整文档体系
  - `api-contract.md` - API 契约文档
  - `production-guide.md` - 生产运维指南
  - `runbook.md` - 故障排查运行手册
  - `adr/` - 架构决策记录目录

### Changed

- **错误处理**：统一错误响应格式为 JSON（`errors.py`）
  - 所有异常现在返回统一的 JSON 错误格式
  - 错误类型包括：`validation_error`, `routing_error`, `upstream_error`, `proxy_error`, `internal_error`
  - 异常提供 `to_dict()` 和 `to_json()` 方法

### Security

- **CORS**：CORS 配置现在可通过 `CORS_ORIGINS` 环境变量配置
  - 之前：硬编码 `allow_origins=["*"]`
  - 现在：默认 `*`，可配置具体域名列表

## [1.0.0] - 2024-03-20

### Added

- **核心功能**
  - 基于 FastAPI 的智能代理路由器
  - 根据模型名称自动路由到不同的上游服务器
  - 支持通配符匹配（fnmatch 语法）

- **认证**
  - Token 认证机制（`x-api-key` 或 `Authorization: Bearer`）
  - 防时序攻击的比较算法

- **SSE 流式响应**
  - 完整支持 Server-Sent Events 流式传输
  - 透明转发上游 SSE 事件

- **日志系统**
  - structlog 结构化日志
  - Console/JSON 双格式支持
  - 请求上下文绑定

- **配置系统**
  - 环境变量配置（`.env` 文件）
  - 路由组配置（`{NAME}_PATTERN`, `{NAME}_UPSTREAM`, `{NAME}_AUTH_TOKEN`）

- **CLI 工具**
  - `python main.py gen-token` - 生成随机认证 Token
  - `python main.py setup` - 交互式配置 Claude Code settings.json

- **健康检查**
  - `/health/live` - 存活探针
  - `/health/ready` - 就绪探针（含上游连通性检查）

- **项目文档**
  - `README.md` - 完整使用文档
  - `.kiro/specs/` - 需求、设计、任务文档

### Technical Details

- FastAPI 0.115+
- httpx 0.28+ (异步 HTTP 客户端)
- uvicorn 0.32+ (ASGI 服务器)
- structlog 24.4+ (结构化日志)
- pydantic 2.10+ (数据验证)
- python-dotenv 1.0+ (环境变量管理)

---

## 版本历史说明

| 版本 | 含义 |
|------|------|
| Major | 不兼容的 API 变更 |
| Minor | 向后兼容的功能新增 |
| Patch | 向后兼容的问题修复 |

[Unreleased]: https://github.com/example/claude-proxy-router/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/example/claude-proxy-router/releases/tag/v1.0.0
