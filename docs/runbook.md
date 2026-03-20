# 运行手册

本文档提供 Claude Proxy Router 的故障排查和日常运维操作指南。

## 目录

- [快速诊断](#快速诊断)
- [常见问题排查](#常见问题排查)
- [日常运维操作](#日常运维操作)
- [紧急故障处理](#紧急故障处理)

---

## 快速诊断

### 1. 检查服务状态

```bash
# 检查进程是否运行
ps aux | grep "python main.py"

# 检查端口是否监听
netstat -tlnp | grep 12346

# 测试健康检查端点
curl http://localhost:12346/health/live
```

### 2. 检查日志

```bash
# 查看实时日志
tail -f logs/app.log

# 或使用 JSON 格式
cat logs/app.log | jq 'select(.level=="error")'
```

### 3. 检查上游连通性

```bash
# 测试到 Anthropic API 的连通性
curl -I https://api.anthropic.com/health

# 测试到智谱 AI 的连通性
curl -I https://open.bigmodel.cn/api/anthropic
```

---

## 常见问题排查

### 问题 1: 认证失败 (401)

**症状**：
```json
{
  "error": {
    "type": "validation_error",
    "message": "认证失败: Invalid token"
  }
}
```

**排查步骤**：

1. 确认请求头中包含正确的 token：
   ```bash
   # 检查请求是否带了 x-api-key
   curl -X POST http://localhost:12346/v1/messages \
     -H "x-api-key: sk-proxy-your-token" \
     -H "Content-Type: application/json" \
     -d '{"model":"glm-4","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
   ```

2. 确认 `.env` 中的 `AUTH_TOKEN` 与客户端使用的 token 一致：
   ```bash
   grep AUTH_TOKEN .env
   ```

3. 检查日志中的 `auth_failed` 事件：
   ```bash
   grep "auth_failed" logs/app.log
   ```

**解决方案**：
- 更新客户端使用的 token
- 或更新 `.env` 中的 `AUTH_TOKEN` 并重启服务

---

### 问题 2: 路由匹配失败

**症状**：
```
日志显示: route_not_matched_using_default
```

**排查步骤**：

1. 检查请求的模型名称是否与配置的 pattern 匹配：
   ```bash
   # 查看当前路由配置
   curl http://localhost:12346/health/ready | jq '.upstreams'
   ```

2. 测试 fnmatch 匹配：
   ```python
   import fnmatch
   model = "glm-4-flash"
   pattern = "glm-*"
   print(fnmatch.fnmatch(model.lower(), pattern.lower()))  # True
   ```

3. 检查 `ROUTE_NAMES` 和对应的 pattern：
   ```bash
   grep PATTERN .env
   ```

**解决方案**：
- 修改 `.env` 中的 `{NAME}_PATTERN` 使其能匹配请求的模型名称
- 例如：将 `glm-*` 改为 `glm*` 可以匹配所有以 glm 开头的模型

---

### 问题 3: 上游连接失败 (502)

**症状**：
```json
{
  "error": {
    "type": "upstream_error",
    "message": "无法连接到上游服务器: https://api.example.com",
    "upstream_url": "https://api.example.com"
  }
}
```

**排查步骤**：

1. 检查上游服务是否可达：
   ```bash
   # 测试直接连接到上游
   curl -I https://api.anthropic.com

   # 检查 DNS 解析
   nslookup api.anthropic.com

   # 检查路由
   traceroute api.anthropic.com
   ```

2. 检查防火墙规则：
   ```bash
   # 检查是否阻止了出站连接
   iptables -L -n | grep DROP
   ```

3. 检查代理设置（如果有 HTTP 代理）：
   ```bash
   echo $HTTP_PROXY
   echo $HTTPS_PROXY
   ```

4. 检查上游服务的 API 密钥是否有效：
   ```bash
   # 直接用 API 密钥测试上游服务
   curl -X POST https://api.anthropic.com/v1/messages \
     -H "x-api-key: sk-ant-your-key" \
     -H "Content-Type: application/json" \
     -d '{"model":"claude-opus-","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
   ```

**解决方案**：
- 修复网络连接问题
- 更新 `.env` 中 `{NAME}_AUTH_TOKEN` 为有效的密钥
- 检查上游服务状态（可能服务宕机）

---

### 问题 4: 超时错误 (504)

**症状**：
```json
{
  "error": {
    "type": "upstream_error",
    "message": "上游服务器超时: https://api.example.com",
    "upstream_url": "https://api.example.com"
  }
}
```

**排查步骤**：

1. 检查上游服务的响应时间：
   ```bash
   time curl -X POST https://api.anthropic.com/v1/messages \
     -H "x-api-key: sk-ant-your-key" \
     -H "Content-Type: application/json" \
     -d '{"model":"claude-opus-","messages":[{"role":"user","content":"test"}],"max_tokens":10}'
   ```

2. 检查网络延迟：
   ```bash
   ping api.anthropic.com
   ```

3. 查看当前的超时配置（`client.py` 中 `read=300.0`）

**解决方案**：
- 如果是网络问题，联系网络管理员
- 如果是上游服务慢，考虑增加超时配置
- 对于 SSE 流式请求，可能需要更长的超时时间

---

### 问题 5: CORS 错误

**症状**：
```
Access to fetch at 'http://localhost:12346' from origin 'https://example.com'
has been blocked by CORS policy
```

**排查步骤**：

1. 检查 `CORS_ORIGINS` 配置：
   ```bash
   grep CORS .env
   ```

2. 确认请求的 origin 在允许列表中

**解决方案**：

```bash
# 修改 .env，添加正确的域名
CORS_ORIGINS="https://example.com,https://admin.example.com"

# 重启服务
systemctl restart claude-proxy
```

---

## 日常运维操作

### 1. 添加新路由

编辑 `.env`：

```bash
# 添加新的路由组
ROUTE_NAMES="OPUS,SONNET,HAIKU,NEW_MODEL"

# 配置新路由
NEW_MODEL_PATTERN="new-model-*"
NEW_MODEL_UPSTREAM="https://new-api.example.com"
NEW_MODEL_AUTH_TOKEN="sk-new-key"
```

重启服务生效。

### 2. 更新 API 密钥

```bash
# 编辑 .env
nano .env
# 找到对应的 AUTH_TOKEN 修改

# 重启服务
systemctl restart claude-proxy
```

### 3. 查看服务状态

```bash
# 查看服务状态
systemctl status claude-proxy

# 查看实时日志
journalctl -u claude-proxy -f

# 查看启动日志
journalctl -u claude-proxy -n 50
```

### 4. 日志分析

```bash
# 统计错误数量
grep "error_occurred" logs/app.log | wc -l

# 查看最近 10 条错误
grep "error_occurred" logs/app.log | tail -10 | jq .

# 统计各状态码数量
grep "request_processed" logs/app.log | jq -r '.status_code' | sort | uniq -c

# 分析请求延迟
grep "request_processed" logs/app.log | jq '.duration_seconds' | awk '{sum+=$1; count++} END {print "avg:", sum/count, "ms"}'
```

---

## 紧急故障处理

### 紧急回滚

如果新配置导致服务不可用：

```bash
# 1. 立即回滚 .env
git checkout .env

# 2. 重启服务
systemctl restart claude-proxy

# 3. 确认服务恢复
curl http://localhost:12346/health/live
```

### 服务无法启动

```bash
# 1. 检查配置文件语法
python -c "from config import Config; Config.from_env()"

# 2. 检查端口占用
lsof -i :12346

# 3. 查看详细错误
python main.py 2>&1
```

### 内存泄漏或高 CPU

```bash
# 1. 查看资源使用
top -p $(pgrep -f "python main.py")

# 2. 生成火焰图（如果安装了 py-spy）
py-spy record -o profile.svg --pid $(pgrep -f "python main.py")

# 3. 重启服务临时解决
systemctl restart claude-proxy
```

### 上游服务完全不可用

临时将流量切换到备用上游：

```bash
# 1. 备份当前配置
cp .env .env.backup

# 2. 修改默认上游
sed -i 's|DEFAULT_UPSTREAM=.*|DEFAULT_UPSTREAM=https://backup-api.example.com|' .env

# 3. 重启服务
systemctl restart claude-proxy

# 4. 监控错误率
watch -n 5 'grep "upstream_error" logs/app.log | tail -5'
```
