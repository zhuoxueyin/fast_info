# fastInfo · ECS 生产部署清单(必读 · Day 5)
====================================

> 📌 **Day 5 配套**:部署到阿里云 ECS 前,这份清单**逐项打勾**。
> ECS 部署链路:**只跑 Docker,不直接跑 Python**(通过 docker compose 拉起 6 个容器)。
>
> ⚠️ 漏掉任何一项,生产环境会被启发式兜底误判成 dev / docker,引发数据蹿环境事故。

---

## 0. 一句话总结

**ECS 上的 `APP_ENV` 必须显式 = `prod`,通过 `docker/env.prod.local`(独立的 env_file)注入容器。
绝不沿用本机预发的 `docker/env.docker.local`(那是 `APP_ENV=docker`)。**

---

## 1. ECS env 链路(实际)

ECS 容器启动时,`APP_ENV` 来自哪里(优先级 高→低):

```
1. docker-compose.yml services.*.environment: APP_ENV=prod
   ↑ 最高,但本项目不用(避免硬编码)
2. docker-compose.yml services.*.env_file
   ↑ **关键点**:由 ${FASTINFO_ENV_FILE:-docker/env.docker.local} 控制
   默认 env.docker.local (本机预发,APP_ENV=docker)
   ECS 必须用 env.prod.local (APP_ENV=prod)
3. volume 挂载的 /app/.env(项目根 .env) → src/_env.py 用 load_dotenv 加载
   ↑ override=False,所以 env_file 优先
4. 容器进程 shell env(几乎不会用)
```

`deploy-prod.sh` 已经自动 `export FASTINFO_ENV_FILE=docker/env.prod.local`,所以走 `bash scripts/deploy-prod.sh` 就 OK。
手动跑 `docker compose` 时需要**显式 export** 这个变量,否则会 fallback 到预发配置。

---

## 2. 部署清单(7 步,逐项打勾)

### ✅ Step 1: ECS 上创建 `docker/env.prod.local`

```bash
cd /path/to/fastinfo   # 你的项目根
cp docker/env.prod.local.example docker/env.prod.local
# 编辑 docker/env.prod.local,关键字段:
#   APP_ENV=prod
#   MONGO_DB=fastinfo_prod        # ⚠️ 必须含 prod,避免误连 dev / docker 的 db
#   FASTINFO_SITE_BASE=https://fastinfo.example.com
#   FASTINFO_SECRET=<32+ 位随机字符串>
```

⚠️ 这个文件已被 `.gitignore` 覆盖(`docker/env.prod.local`),不会被 commit。

### ✅ Step 2: ECS 上 `.env` 共享配置确认

```bash
[ -f .env ] || cp .env.example .env
# 填入真实 key:
#   MMX_API_KEY=<真实>
#   KIMI_API_KEY=<真实>
#   SMTP_*
#   LARK_* (可选)
# ⚠️ .env 不要写 APP_ENV,让 env_file 控制
```

### ✅ Step 3: 跑 `deploy-prod.sh`

```bash
bash scripts/deploy-prod.sh
```

该脚本会:
1. 检查 `docker/env.prod.local` 存在(否则 fallback + WARN)
2. `export FASTINFO_ENV_FILE=docker/env.prod.local`
3. `docker compose build` + `up -d`
4. 4 项健康检查(Nginx healthz / API stats / 容器数 / 直连 healthz)

**看到 `✅ 使用生产专用配置 docker/env.prod.local` 就对了**。

### ✅ Step 4: 验证 `APP_ENV=prod` 真的进了容器

```bash
# 方法 1:看容器环境变量
docker exec fastinfo-api printenv APP_ENV
# 期望: prod

# 方法 2:看容器内 /healthz(需要先实现 task 3 的 healthz env 字段)
curl -s http://<SERVER_IP>:18080/healthz | python -m json.tool
# 期望: {"status":"ok","env":"prod","declared":true,...}

# 方法 3:看启动日志
docker logs fastinfo-api 2>&1 | grep ENV-IDENTITY
# 期望: [ENV-IDENTITY] OK · APP_ENV=prod · declared=True · mongo_db=fastinfo_prod

# 方法 4:进容器 exec Python
docker exec fastinfo-api python -c \
  "from env_identity import get_env_identity; import json; print(json.dumps(get_env_identity(), indent=2))"
# 期望: env=prod, declared=True, mongo_db=fastinfo_prod
```

**如果出现 `[ENV-IDENTITY] WARNING: APP_ENV=prod is INFERRED`**:
→ 回到 Step 1,检查 `env.prod.local` 真的被加载。

### ✅ Step 5: 验证 `MONGO_DB` 真的是 prod 库

```bash
docker exec fastinfo-mongo mongosh --quiet --eval \
  "db.adminCommand({listDatabases: 1}).databases.map(d => d.name)"
# 期望包含 fastinfo_prod,**绝不包含** fastinfo / fastinfo_docker
```

如果发现 ECS 容器连了 dev 的 db,**立即停服**(数据写入会污染 dev)。

### ✅ Step 6: 验证 `_FASTINFO_APP_ENV_DECLARED=1`

```bash
docker exec fastinfo-api python -c \
  "from env_identity import is_declared; print('declared:', is_declared())"
# 期望: declared: True
```

如果返回 `False` → `_env.py` 没识别到声明。排查:
- `load_env()` 是否真的被调用?(所有 entrypoint 顶部都有)
- `load_dotenv` 的 `override=False` 是否把 shell 的 `APP_ENV` 跳过了?(理论上 env_file > load_dotenv,不会有问题)

### ✅ Step 7: 首次部署后 24h 内人工 whereami

```bash
docker exec fastinfo-api python -c \
  "from env_identity import get_env_identity, warn_if_undeclared_prod; import json; print(json.dumps(get_env_identity(), indent=2)); warn_if_undeclared_prod()"
```

期望:
- `env: "prod"`
- `declared: true`
- 无 WARN 输出

---

## 3. 出问题怎么排查

### 3.1 ECS 进程里 `APP_ENV=docker`(而不是 prod)

**症状**:`docker exec fastinfo-api printenv APP_ENV` 返回 `docker`。

**根因**:
1. 没创建 `docker/env.prod.local`,fallback 到 `env.docker.local`
2. 或者手动跑 `docker compose` 时没 `export FASTINFO_ENV_FILE`

**修复**:
- `cp docker/env.prod.local.example docker/env.prod.local` 并填值
- 部署用 `bash scripts/deploy-prod.sh`,不要手动 `docker compose up`

### 3.2 ECS 进程里 `APP_ENV=dev`

**症状**:`APP_ENV` 返回 `dev`。

**根因**:
1. ECS 容器内 `/app/.env` 从项目根 `.env` volume 挂载,而根 `.env` 里有 `APP_ENV=dev`
2. **但 `load_dotenv` 用 `override=False`,env_file 优先,所以 env_file 有值时不会用 .env 的 dev**
3. 如果 env_file 没设 APP_ENV,才会 fallback 到根 .env 的 dev

**修复**:
- `docker/env.prod.local` 必须显式设 `APP_ENV=prod`
- 根 `.env` 不要写 `APP_ENV`(避免误导)

### 3.3 看到 `[ENV-IDENTITY] WARNING: APP_ENV=prod is INFERRED`

**含义**:`detect_env()` 推断出 prod,但 `APP_ENV` 不是 env_file 显式注入的,而是 hostname / DMI 启发式命中。

**修复**:
1. 检查 `docker/env.prod.local` 真的存在且含 `APP_ENV=prod`
2. 检查 `deploy-prod.sh` 真的 export 了 `FASTINFO_ENV_FILE`
3. **不要依赖** hostname 启发式,必须显式

### 3.4 容器起不来,deploy-prod.sh 报错

**症状**:`bash scripts/deploy-prod.sh` 直接 exit 1。

**根因**:preflight 检查失败(.env 不存在 / MMX_API_KEY 没填 / env_file 不存在)。

**修复**:逐项看 preflight 输出,补齐缺失项。

---

## 4. 编码铁律(给后续开发者)

| # | 原则 |
|---|---|
| P1 | **绝不在代码里 hardcode** `if hostname == 'iZbp1...'`。永远读 `APP_ENV`。 |
| P2 | **所有 entrypoint 第一行** `from _env import load_env; load_env()`。 |
| P3 | **业务入口启动时**调 `warn_if_undeclared_prod()`,确保 prod 环境被显式声明。 |
| P4 | **生产配置永不进 git**:`.env` / `env.docker.local` / `env.prod.local` 都在 `.gitignore` 里。 |

---

## 5. 总结检查表(7/7 才能上线)

```
[ ] 1. ECS 上 docker/env.prod.local 已创建,含 APP_ENV=prod + MONGO_DB=fastinfo_prod
[ ] 2. ECS 上 .env 已填 MMX/KIMI 等共享 key(不含 APP_ENV)
[ ] 3. bash scripts/deploy-prod.sh 跑通,看到 "✅ 使用生产专用配置"
[ ] 4. docker exec fastinfo-api printenv APP_ENV → prod
[ ] 5. mongosh 看到 fastinfo_prod db,无 fastinfo / fastinfo_docker
[ ] 6. _FASTINFO_APP_ENV_DECLARED=1(通过 is_declared() 验证)
[ ] 7. 容器启动日志看到 [ENV-IDENTITY] OK 而非 WARNING
```

**7/7 通过才能上线。**