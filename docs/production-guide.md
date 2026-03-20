# 生产运维指南

本文档提供 Claude Proxy Router 在生产环境中的部署和运维指南。

## 目录

- [安全配置](#安全配置)
- [密钥管理](#密钥管理)
- [性能调优](#性能调优)
- [监控集成](#监控集成)
- [日志管理](#日志管理)
- [高可用部署](#高可用部署)

---

## 安全配置

### CORS 配置

**生产环境不要使用 `*`**。配置具体的域名列表：

```bash
# .env
CORS_ORIGINS="https://your-app.example.com,https://admin.example.com"
```

#### Kubernetes Ingress 配置

如果使用 Nginx Ingress Controller：

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: claude-proxy
  annotations:
    nginx.ingress.kubernetes.io/cors-allow-origin: "https://your-app.example.com"
    nginx.ingress.kubernetes.io/cors-allow-methods: "POST, GET, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "x-api-key,Authorization,Content-Type"
spec:
  ingressClassName: nginx
  rules:
  - host: proxy.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: claude-proxy
            port:
              number: 12346
```

### 请求体大小限制

在反向代理层限制请求体大小，防止 DoS 攻击：

#### Nginx

```nginx
server {
    client_max_body_size 1M;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;
}
```

#### Kubernetes

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
data:
  proxy-body-size: "1m"
```

### HTTPS 配置

生产环境必须使用 HTTPS。推荐在反向代理层终止 TLS：

```nginx
server {
    listen 443 ssl http2;
    server_name proxy.example.com;

    ssl_certificate /etc/ssl/certs/proxy.crt;
    ssl_certificate_key /etc/ssl/private/proxy.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    location / {
        proxy_pass http://localhost:12346;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 密钥管理

### 环境变量 vs 密钥管理服务

| 方式 | 适用场景 | 推荐工具 |
|------|----------|----------|
| .env 文件 | 开发/小规模部署 | - |
| Kubernetes Secret | Kubernetes 部署 | `kubectl create secret` |
| Vault | 企业级密钥管理 | HashiCorp Vault |
| AWS Secrets Manager | AWS 环境 | AWS SDK |

### Kubernetes Secret 示例

```bash
# 创建 secret
kubectl create secret generic claude-proxy-secret \
  --from-literal=AUTH_TOKEN=sk-proxy-xxx \
  --from-literal=OPUS_AUTH_TOKEN=sk-ant-xxx \
  --from-literal=SONNET_AUTH_TOKEN=your-glm-key

# 在 Pod 中引用
kubectl set env deployment/claude-proxy --from=secret/claude-proxy-secret
```

### 密钥轮换流程

1. 在密钥管理服务中创建新密钥
2. 更新 `.env` 或 Secret 中的新密钥
3. 重启服务：`kubectl rollout restart deployment/claude-proxy`
4. 验证新密钥正常工作
5. 旧密钥可以在确认无引用后删除

---

## 性能调优

### uvicorn workers

根据 CPU 核心数调整 worker 数量：

```bash
# 推荐公式: 2 * CPU cores + 1
uvicorn main:app -w 9 --host 0.0.0.0 --port 12346
```

### Gunicorn + Uvicorn Workers

```bash
gunicorn main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:12346 \
  --max-requests 1000 \
  --max-requests-jitter 50
```

### 连接池配置

在 `client.py` 中已配置默认连接池：

```python
max_connections: int = 100  # 最大连接数
max_keepalive_connections: int = 50  # 最大 keepalive 连接数
```

如果需要调整，修改 `UpstreamClient` 实例化时的参数。

### 超时配置

| 超时类型 | 默认值 | 适用场景 |
|----------|--------|----------|
| 连接超时 | 10s | 网络连接建立 |
| 读超时 | 300s | SSE 流式响应 |
| 写超时 | 10s | 请求体发送 |
| 池超时 | 10s | 从连接池获取连接 |

---

## 监控集成

### Prometheus 指标

建议添加以下自定义指标：

```python
# 使用 prometheus_client
from prometheus_client import Counter, Histogram, generate_latest

# 请求计数器
REQUEST_COUNT = Counter(
    'proxy_requests_total',
    'Total proxy requests',
    ['model', 'upstream', 'status_code']
)

# 延迟直方图
REQUEST_LATENCY = Histogram(
    'proxy_request_duration_seconds',
    'Request latency',
    ['model', 'upstream']
)
```

### 日志聚合

#### 结构化日志格式（JSON）

```bash
# .env
LOG_FORMAT=json
LOG_LEVEL=INFO
```

#### ELK Stack 集成

```yaml
# filebeat.yml
filebeat.inputs:
- type: container
  paths:
    - /var/log/containers/claude-proxy*.log
  json.keys_under_root: true
  json.add_error_key: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

#### Loki 集成

```yaml
# promtail.yml
scrape_configs:
- job_name: claude-proxy
  static_configs:
  - targets:
      - localhost
    labels:
      job: claude-proxy
      __path__: /var/log/claude-proxy/*.log
```

### 健康检查告警

```yaml
# Prometheus alerting rules
groups:
- name: claude-proxy
  rules:
  - alert: ClaudeProxyDown
    expr: up{job="claude-proxy"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Claude Proxy Router is down"

  - alert: ClaudeProxyHighErrorRate
    expr: rate(proxy_requests_total{status_code=~"5.."}[5m]) > 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High error rate on Claude Proxy"
```

---

## 日志管理

### 日志级别

| 级别 | 使用场景 |
|------|----------|
| DEBUG | 开发调试（记录所有请求详情） |
| INFO | 正常运行（记录请求开始/结束） |
| WARNING | 可恢复的错误（如 API 密钥未找到） |
| ERROR | 上游错误、连接失败 |

### 日志分析示例

#### 查找慢请求

```bash
# JSON 格式日志
grep "request_processed" app.log | jq 'select(.duration_seconds > 5)' | jq .
```

#### 统计错误率

```bash
# 按状态码统计
grep "request_processed" app.log | jq -r '.status_code' | sort | uniq -c
```

#### 分析路由分布

```bash
# 按模型统计请求量
grep "request_received" app.log | jq -r '.model' | sort | uniq -c | sort -rn
```

---

## 高可用部署

### Kubernetes 部署示例

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-proxy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: claude-proxy
  template:
    metadata:
      labels:
        app: claude-proxy
    spec:
      containers:
      - name: claude-proxy
        image: claude-proxy-router:latest
        ports:
        - containerPort: 12346
        envFrom:
        - secretRef:
            name: claude-proxy-secret
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 12346
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 12346
          initialDelaySeconds: 5
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: claude-proxy
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 12346
  selector:
    app: claude-proxy
```

### Docker Compose 高可用

```yaml
version: '3.8'
services:
  proxy:
    image: claude-proxy-router
    deploy:
      replicas: 3
    env_file:
      - .env
    depends_on:
      - redis

  redis:
    image: redis:alpine
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```
