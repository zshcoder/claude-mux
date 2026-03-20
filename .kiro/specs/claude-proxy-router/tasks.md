# Implementation Plan

## 项目设置与基础结构

- [ ] 1. 初始化项目结构和依赖
  - 创建项目目录结构（main.py, router.py, client.py, config.py, logger.py, errors.py）
  - 创建 requirements.txt，包含：fastapi, uvicorn, httpx, pyyaml, structlog, python-dotenv, pytest, pytest-asyncio
  - 创建 .env.example 文件
  - 创建 README.md 基础文档
  - 创建 config.yaml 示例配置文件
  - _Requirements: 1.1, 6.1_

- [ ] 2. 实现错误定义模块
  - 在 errors.py 中定义错误类：ProxyError, ConfigError, UpstreamError, RoutingError
  - 为每个错误类添加适当的错误消息和状态码
  - _Requirements: 5.1_

## 核心配置系统

- [ ] 3. 实现配置管理器
  - 在 config.py 中创建 RouteRuledataclass（pattern, upstream_url, api_key, api_key_env）
  - 创建 Config dataclass（default_upstream, default_api_key, routes, log_level, port）
  - 实现 Config.from_file() 方法从 YAML 文件加载配置
  - 实现 Config.from_env() 方法从环境变量加载配置
  - 添加配置验证逻辑（URL 格式、必需字段等）
  - 编写单元测试验证配置加载和验证
  - _Requirements: 3.1, 3.2, 3.4, 6.1, 6.2, 6.3_

- [ ] 4. 实现 API 密钥管理
  - 在 Config 类中添加 get_api_key() 方法，支持从环境变量读取密钥
  - 实现密钥优先级逻辑：规则密钥 > 默认密钥 > 原始请求头
  - 添加密钥读取失败时的警告日志
  - 编写单元测试验证密钥管理逻辑
  - _Requirements: 3.1.1, 3.1.2, 3.1.3, 3.1.4, 3.1.5, 3.1.6_

## 日志系统

- [ ] 5. 实现 structlog 日志配置
  - 在 logger.py 中实现 setup_logging() 函数，支持 JSON 和 console 格式
  - 实现 get_logger() 函数获取 logger 实例
  - 实现 log_request() 函数记录请求信息
  - 配置 structlog 处理器（时间戳、日志级别、格式化）
  - 编写单元测试验证日志输出
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

## 路由系统

- [ ] 6. 实现模型路由器
  - 在 router.py 中创建 ModelRouter 类
  - 实现 __init__() 方法，接收 Config 实例
  - 实现 get_upstream_url() 方法，支持通配符匹配（使用 fnmatch 或正则）
  - 实现 get_api_key() 方法，返回对应路由的 API 密钥
  - 实现 add_route() 方法动态添加路由规则
  - 编写单元测试验证路由匹配逻辑（精确匹配、通配符匹配、默认回退）
  - _Requirements: 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.1.3_

## 上游客户端

- [ ] 7. 实现异步 HTTP 客户端
  - 在 client.py 中创建 UpstreamClient 类
  - 实现 __init__() 方法，配置超时和连接池
  - 实现 forward_request() 异步方法，支持流式响应
  - 实现 API 密钥替换逻辑（如果提供 api_key 参数）
  - 实现 close() 方法关闭连接池
  - 添加错误处理（连接失败、超时等）
  - 编写单元测试验证请求转发（使用 mock服务器）
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 3.1.4_

- [ ] 8. 实现 SSE 流式响应处理
  - 在 forward_request() 中正确处理 SSE 流
  - 使用 httpx 的 stream() 方法异步迭代响应块
  - 确保流式数据正确透传给客户端
  - 编写集成测试验证 SSE 流式传输
  - _Requirements: 4.2, 4.3_

## FastAPI 应用

- [ ] 9. 创建 FastAPI 应用主文件
  - 在 main.py 中创建 FastAPI 应用实例
  - 配置 CORS 中间件（如需要）
  - 实现应用生命周期管理（startup 和 shutdown 事件）
  - 初始化配置、路由器、客户端和日志
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 10. 实现请求处理端点
  - 实现 POST /{path:path} 路由处理器
  - 从请求体中提取 model 字段
  - 使用路由器获取上游 URL 和 API 密钥
  - 调用客户端转发请求
  - 流式返回响应（使用 StreamingResponse）
  - 添加错误处理和日志记录
  - 编写集成测试验证完整请求流程
  - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 11. 实现错误处理中间件
  - 添加全局异常处理器捕获 ProxyError 及其子类
  - 返回适当 HTTP 状态码和错误响应
  - 记录所有错误到日志
  - 编写测试验证错误处理
  - _Requirements: 5.1, 5.2_

## 测试与验证

- [ ] 12. 编写集成测试
  - 创建测试配置文件和 mock上游服务器
  - 测试完整的请求流程（不同模型路由到不同上游）
  - 测试 API 密钥替换逻辑
  - 测试 SSE 流式响应
  - 测试错误场景（无效请求、上游失败等）
  - _Requirements: All_

- [ ] 13. 编写性能测试
  - 使用 locust 创建负载测试脚本
  - 测试并发请求处理能力
  - 测试流式响应性能
  - 验证性能目标（> 100 req/s, < 50ms 延迟增加）
  - _Requirements: 4.2_

## 文档与部署

- [ ] 14. 完善项目文档
  - 编写 README.md，包含项目介绍、安装步骤、配置说明
  - 添加使用示例和配置示例
  - 编写 API 文档（FastAPI 自动生成）
  - 创建 Dockerfile（可选）
  - 创建 docker-compose.yml（可选）
  - _Requirements: All_

- [ ] 15. 准备部署配置
  - 创建生产环境配置示例
  - 编写部署文档（Gunicorn + Uvicorn）
  - 添加健康检查端点（可选）
  - 添加 Prometheus metrics（可选）
  - _Requirements: All_

## 测试清单

在完成所有任务后，执行以下验证：

- [ ] 所有单元测试通过（pytest）
- [ ] 所有集成测试通过
- [ ] 代码覆盖率 > 90%
- [ ] 手动测试：Claude Code 连接到代理
- [ ] 手动测试：不同模型路由到正确上游
- [ ] 手动测试：SSE 流式响应正常工作
- [ ] 性能测试满足目标
- [ ] 文档完整且准确
