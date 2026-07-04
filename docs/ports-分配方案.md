# fastInfo · 端口分配方案
日期:2026-07-04 · 状态:✅ 实施

## 一、设计目标

1. **本地开发(L) + Docker 预发(S) 完全隔离** — 两套端口不冲突,可同时跑
2. **端口号本身带语义** — 看一眼数字就知道是哪个环境
3. **业务代码零分叉** — 所有端口走 env 注入,代码里没有 `if env == "docker"`

## 二、端口对照表(一眼分清)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          本机(127.0.0.1)                                │
├──────────────┬───────────────┬─────────────────┬───────────────────────┤
│  服务        │ 本地开发 (L)  │ Docker 预发 (S) │ 视觉规律              │
├──────────────┼───────────────┼─────────────────┼───────────────────────┤
│ FastAPI      │     8000      │     18000       │ +10000 (5 位=staging) │
│ Nginx (Web)  │     -         │     18080       │ +10000                │
│ MongoDB      │    27017      │     27018       │ +1 (业内惯例)        │
│ Redis        │     6379      │      6380       │ +1 (业内惯例)        │
│ Vite 前端dev │     5173      │      -          │ (本地专属,5xxx 段)   │
│ VitePress    │     5174      │      -          │ (本地专属)           │
├──────────────┼───────────────┼─────────────────┼───────────────────────┤
│ 端口数量     │   4 个        │    4 个         │ (互不冲突)            │
└──────────────┴───────────────┴─────────────────┴───────────────────────┘
```

**识别口诀**:
- **5 位数 1 开头(18000/18080)** → Docker 预发环境
- **4 位数 8 开头(8000)** → 本地 FastAPI
- **5 位数 27xxx(27017/27018)** → MongoDB
- **4 位数 63xx(6379/6380)** → Redis
- **5 位数 51xx(5173/5174)** → 前端 dev server

## 三、API 访问方式(4 种入口全部能 work)

| 访问 URL | 走法 | 用途 |
|---|---|---|
| `http://127.0.0.1:8000/api/...` | 本机 uvicorn | 本地直接调(无 Nginx) |
| `http://127.0.0.1:5173/api/...` | Vite dev proxy → :8000 | 前端开发联调 |
| `http://127.0.0.1:18000/api/...` | 主机:18000 → 容器 api:8000 | Docker 预发直连(调试) |
| `http://127.0.0.1:18080/api/...` | 主机:18080 → Nginx → api:8000 | Docker 预发走完整链路(推荐) |

## 四、容器内部端口(代码层面)

**容器内部都用标准端口**,不跟主机端口混淆:

| 服务 | 容器内端口 | 配置位置 |
|---|---|---|
| FastAPI (uvicorn) | 8000 | `scripts/api_server.py` 默认 |
| Nginx | 80 | `docker/nginx/default.conf` |
| MongoDB | 27017 | `mongo:8` 镜像默认 |
| Redis | 6379 | `redis:7-alpine` 镜像默认 |

**主机端口 ← 容器端口** 的映射在 `docker-compose.yml` 的 `ports:` 段:

```yaml
api:
  ports:
    - "${FASTINFO_API_PORT:-18000}:8000"  # 主机 18000 → 容器 8000
web:
  ports:
    - "${FASTINFO_WEB_PORT:-18080}:80"    # 主机 18080 → 容器 80
```

## 五、环境变量映射

| 变量 | 本地默认值 | Docker 默认值 | 用途 |
|---|---|---|---|
| `FASTINFO_API_PORT` | `8000` | `18000` | 主机 FastAPI 端口 |
| `FASTINFO_WEB_PORT` | `8080` | `18080` | 主机 Nginx 端口 |
| `FASTINFO_MONGO_PORT` | (无,直接用 27017) | `27018` | 主机 Mongo 端口 |
| `FASTINFO_REDIS_PORT` | (无,直接用 6379) | `6380` | 主机 Redis 端口 |
| `MONGO_URL` | `mongodb://127.0.0.1:27017` | `mongodb://mongo:27017` | Mongo 连接串(容器内用服务名) |
| `REDIS_URL` | `redis://127.0.0.1:6379` | `redis://redis:6379` | Redis 连接串 |

**配置位置**:
- 本地:`项目根/.env`(FASTINFO_API_PORT 等)
- Docker:`docker/env.docker.local`(覆盖本地值)

## 六、代码里端口怎么读(全部走 env)

```python
# 之前(硬编码)
parser.add_argument("--port", type=int, default=8000)
base = "http://127.0.0.1:8000"

# 之后(读 env,带原值做默认)
parser.add_argument(
    "--port", type=int,
    default=int(os.environ.get("FASTINFO_API_PORT", "8000"))
)
base = f"http://127.0.0.1:{os.environ.get('FASTINFO_API_PORT', '8000')}"
```

```ts
// 之前(vite.config.ts)
target: 'http://127.0.0.1:8000'

// 之后
const API_TARGET = process.env.VITE_API_TARGET
  || `http://127.0.0.1:${process.env.FASTINFO_API_PORT || 8000}`
target: API_TARGET
```

## 七、启动命令速查

### 本地开发(L)
```powershell
# 起基础服务(Mongo / Redis 走 Docker,fastInfo 进程走本机 venv)
docker compose up -d mongo redis

# 起 API
python scripts/api_server.py              # 默认 8000
# 或者
FASTINFO_API_PORT=8080 python scripts/api_server.py

# 起前端 dev(可选)
cd frontend; npm run dev                   # :5173,proxy → :8000

# 起 docs dev(可选)
cd docs-site; npm run dev                  # :5174
```

### Docker 预发(S)
```powershell
# 一次起全部 6 个服务(mongo / redis / api / web / ingest / subs)
$env:DOCKER_REGISTRY_PREFIX = "docker.m.daocloud.io/library/"
docker compose up -d --build

# 浏览器访问
#   http://127.0.0.1:18080/         (Web,推荐,走 Nginx)
#   http://127.0.0.1:18000/docs     (Swagger UI,直连 API)
#   http://127.0.0.1:18080/docs/    (VitePress 文档)
```

## 八、新人 Onboarding 看这一张表就够

| 想看 / 想调 | 本地开发 | Docker 预发 |
|---|---|---|
| 前端 Web | http://127.0.0.1:5173 | http://127.0.0.1:18080 |
| Swagger UI | http://127.0.0.1:8000/docs | http://127.0.0.1:18000/docs |
| Mongo | 127.0.0.1:27017 | 127.0.0.1:27018 |
| Redis | 127.0.0.1:6379 | 127.0.0.1:6380 |
| API Key 配哪 | `项目根/.env` | `docker/env.docker.local` |
| 配置文件 | `.env` | `.env` + `docker/env.docker.local`(后者覆盖) |

## 九、违反原则的情况(不允许)

- ❌ 在 Python 代码里硬编码 `127.0.0.1:8000` 而不读 env
- ❌ 在 docker-compose.yml 里把主机端口设成跟本地相同(8000/6379)
- ❌ 在 Vite proxy 里硬编码目标端口
- ❌ 在文档里写"访问 http://127.0.0.1:8000"而不区分本地/Docker

任何新增 URL 必须:
1. 优先读 env(`FASTINFO_API_PORT` / `VITE_API_TARGET`)
2. 找不到时给本地默认值 8000
3. 文档里写"本地 / Docker"两套 URL,不要只写一套

## 十、未来扩展

如果要加新端口(比如 Elasticsearch、MinIO),按相同规律分配:
- 本地:经典端口(9200 / 9000)
- Docker:`原端口 + 10000`(19200 / 19000) 或 `+1`(9201 / 9001)

更新本文件 §2 对照表 + docker-compose.yml + env 模板。