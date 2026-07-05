# fastInfo · 日常环境使用手册 v1.0
=================================

> 📌 **Day 5 配套**:你日常工作会用到 3 套环境(本机 dev / 本机 docker 预发 / ECS 生产)。
> 这份手册告诉你**每种场景该跑什么、排查前该查什么、什么时候切哪套**。
>
> 配合阅读:`docs/env-isolation-strategy.md`(整体策略)/ `docs/env-ecs-deploy-checklist.md`(ECS 部署)

---

## 0. 一句话总结

```
日常 90% 时间 = 本机 venv 开发(start.ps1 一把梭)
临时验证     = 本机 docker 预发(docker compose up,跟 dev 数据隔离)
正式部署     = ECS 生产(bash deploy-prod.sh,独立 db)
```

**排查任何异常前,先跑 `whereami` 确认你在哪。**

---

## 1. 三种场景速查表

| 场景 | 启动命令 | 数据 db | MONGO_URL | 端口 |
|---|---|---|---|---|
| **本机开发 (dev)** | `.\start.ps1` | `fastinfo` | `127.0.0.1:27017` | API 8000 / Web 5173 |
| **本机 docker 预发 (docker)** | `docker compose up -d` | `fastinfo_docker` | `mongo:27017` (容器内) | API 18000 / Web 18080 |
| **ECS 生产 (prod)** | `bash deploy-prod.sh` | `fastinfo_prod` | `mongo:27017` (容器内) | API 18000 / Web 18080 |

**3 套 db 物理隔离,数据不会蹿。** 标识是辅助,不是隔离手段。

---

## 2. 日常使用 SOP

### 2.1 本机开发(dev) — 90% 时间在这里

**第一件事**(开 shell 后):
```powershell
.\scripts\whereami.ps1 -Quick
# 期望: [DEV]  mongo=mongodb://127.0.0.1:27017  db=fastinfo  ping=OK
```

**启动服务**:
```powershell
.\start.ps1                # 一把梭起 backend + frontend + docs + ingest + scheduler
# 或选择性起:
.\start.ps1 -Only backend  # 只起 API
```

**写代码 / 改 ingest**:
```powershell
# 改完代码后:
.\restart.ps1 -Only backend   # 重启 backend (1 秒)
# ingest_daemon / subs_scheduler 改完用 .\restart.ps1 -Only ingest/scheduler
```

**手动跑一次 ingest 测试**:
```powershell
.venv\Scripts\python.exe scripts\ingest_daemon.py --once
```

**清理去重(测试用,生产绝不要跑)**:
```powershell
.venv\Scripts\python.exe scripts\reset_delivered.py
```

---

### 2.2 本机 docker 预发验证(docker) — 验证完整链路

**何时用**:
- 改了 docker / nginx / docker-compose,要看实际容器行为
- 验证"我的代码在容器里跑没崩"
- 给同事看效果(链接 `:18080`)
- 预发验证完才推到 ECS

**启动**:
```powershell
# 第一次:
Copy-Item docker\env.docker.local.example docker\env.docker.local
# 编辑填入你的容器端口(默认就 OK)

# 启动:
docker compose up -d --build
# 等 ~30 秒,自动建索引

# 验证:
.\scripts\diag_env.ps1 -Target docker
# 期望: dev 那条 profile 显示 4/4 OK
```

**日常操作**:
```powershell
# 看日志
docker compose logs -f api

# 重启某个服务(代码改了)
docker compose restart api

# 全部重建(改了 requirements / Dockerfile)
docker compose up -d --build

# 完全清理(⚠️ 删数据卷)
docker compose down -v
```

**与本机 dev 互不干扰**:
- dev 跑在 `127.0.0.1:27017` (本地 Mongo)
- docker 跑在 `127.0.0.1:27018` → `mongo:27017` (容器 Mongo)
- 端口不同,db 名不同,**不会冲突**

---

### 2.3 ECS 生产部署(prod) — 上线才用

**何时用**:
- 代码经过 dev + docker 验证,推到 ECS
- 紧急 hotfix

**部署流程**:
```bash
# 在 ECS 上:
cp docker/env.prod.local.example docker/env.prod.local
# 编辑填生产专用值:
#   APP_ENV=prod
#   MONGO_DB=fastinfo_prod
#   FASTINFO_SITE_BASE=https://fastinfo.example.com
#   FASTINFO_SECRET=<32+ 位随机>
#   (其他 key 跟 dev 共享,从 .env 来)

# 跑部署
bash scripts/deploy-prod.sh
# 自动:检测 env.prod.local → export FASTINFO_ENV_FILE → build → up → 健康检查
```

**完整 7 步清单见 `docs/env-ecs-deploy-checklist.md`**,部署后必须逐项打勾。

---

## 3. 排查异常 SOP(查问题第一时间跑这个)

### 3.1 黄金流程(每次都要)

```powershell
# 第 1 步:确认我在哪(5 秒)
.\scripts\whereami.ps1 -Quick

# 第 2 步:确认环境健康(10 秒)
.\scripts\diag_env.ps1
# 或对比两套:
.\scripts\diag_env.ps1 -Both
```

**这两个跑完,90% 的"环境问题"已经定位**:
- `[DEV]` + ping OK → 数据是 dev 的,跟 docker/prod 无关
- `[DEV]` + ping FAIL → MongoDB 没起,起 docker 里的 redis 或本机 Mongo
- `[DOCKER]` + ports 全 OK → 在 docker 预发里查
- `[DOCKER]` + ports 部分 DOWN → docker compose 没全部起来

### 3.2 具体场景的排查

#### 场景 A:"同事说 docker 上看不到某条新闻"
```powershell
.\scripts\whereami.ps1        # 我是 dev 还是 docker?
.\scripts\diag_env.ps1 -Both  # docker 那套 healthy 吗?

# 确认是 docker 环境后:
docker compose exec mongo mongosh fastinfo_docker --eval \
  "db.items.find({_id:'xxx'}).pretty()"
```

#### 场景 B:"生产数据被写错地方了"
```bash
# 在 ECS 上:
docker exec fastinfo-api python -c \
  "from env_identity import get_env_identity; import json; print(json.dumps(get_env_identity(), indent=2))"
# 检查 env/declared/mongo_db

# 如果 env=prod 但 mongo_db=fastinfo (不是 fastinfo_prod) → 漏配 prod env_file
# 立即停止 ingest_daemon:
docker compose stop ingest_daemon
```

#### 场景 C:"本地连不上 Mongo"
```powershell
.\scripts\diag_env.ps1 -Target dev
# 看 mongo 端口 27017 是否 [OPEN]
# FAIL → 起 Mongo: docker compose up -d redis mongo  (只起这俩)

# 如果是 docker:
.\scripts\diag_env.ps1 -Target docker
# 看 mongo 容器是否 healthy
docker compose ps mongo
```

#### 场景 D:"想看 docker 里的 ingest 日志,但分不清哪个窗口"
```powershell
# 窗口 1:本机 dev 的 ingest
Get-Content data\ingest.log -Tail 20 -Wait

# 窗口 2:docker 的 ingest(独立终端)
docker compose logs -f ingest_daemon
# 或:
.\scripts\diag_env.ps1 -Target docker  # 端口 + 健康
```

---

## 4. 切换环境的正确姿势

### 4.1 "我想在 docker 里测试刚改的代码"

```powershell
# dev 不用停,直接:
docker compose up -d --build api
# docker 会 mount ./src(如果有)或者重建镜像
# 代码生效后再切回 dev:
docker compose stop api    # 停 docker api
.\restart.ps1 -Only backend  # 起 dev api
```

### 4.2 "我想在 dev 里临时测试 docker 的某个配置"

```powershell
# 把 docker 的 env 临时拷到 dev 的 .env:
Copy-Item docker\env.docker.local .env.local -Force
# 然后在 dev shell 里:
$env:APP_ENV = "docker"
$env:MONGO_URL = "mongodb://127.0.0.1:27018"
$env:MONGO_DB = "fastinfo_docker"
.\restart.ps1 -Only backend
# 测完改回:
Remove-Item Env:\APP_ENV -ErrorAction SilentlyContinue
.\restart.ps1 -Only backend
```

**但 90% 场景不推荐这样做**——直接 `docker compose up` 起一套独立的更安全。

### 4.3 "临时切到 ECS prod 验证(别真改东西!)"

```bash
# 在 ECS 上:
docker exec -it fastinfo-api python -c \
  "from env_identity import get_env_identity; import json; print(json.dumps(get_env_identity(), indent=2))"
# 确认是 prod + declared=True 后,只读查询:
docker exec fastinfo-api curl -s http://localhost:8000/api/items?limit=5
```

**严禁在 prod 直接调 DELETE / DROP / reset_delivered.py**。

---

## 5. 日常检查清单(每周一次 / 部署前必查)

```
[ ] whereami 在 dev 显示 [DEV],dev 的 Mongo ping OK
[ ] whereami 在 docker(如果起的话)显示 [DOCKER],docker 端口全开
[ ] .\diag_env.ps1 -Both 显示两套都健康
[ ] dev 没有遗留的 docker 的 db 误连(whereami 看 mongo_db)
[ ] docker 没有遗留的 dev 的 db 误连(whereami 看 mongo_db)
[ ] 没有两个 shell 同时跑同一个端口(8000/18000 冲突会端口占用)
```

---

## 6. 严禁做的事

| ❌ 严禁 | ✅ 应该 |
|---|---|
| 在 dev 里跑 `reset_delivered.py` | 在 docker 里跑,确认无误再考虑生产 |
| 在 prod 调 `mongosh fastinfo` (没带 _prod) | 用 `docker exec fastinfo-mongo mongosh fastinfo_prod` |
| 直接编辑 `docker/env.prod.local` 当 dev 用 | 用 `docker/env.docker.local` |
| 修改代码前不 whereami | 改前 5 秒 whereami,改完 5 秒再 whereami |
| 把 prod 的 MONGO_DB 改成 dev 的 fastinfo | 用 `fastinfo_prod`,**永远独立** |
| 在 dev 里 export `APP_ENV=prod` | dev 就该是 dev,prod 留给 ECS |

---

## 7. 一页 cheat sheet(打印贴墙上)

```
┌─────────────────────────────────────────────────────────────┐
│  fastInfo 日常环境 cheat sheet                                │
├─────────────────────────────────────────────────────────────┤
│  查环境    .\scripts\whereami.ps1 -Quick                    │
│  查健康    .\scripts\diag_env.ps1 -Both                     │
│  起 dev    .\start.ps1                                      │
│  重启 dev  .\restart.ps1 -Only backend                     │
│  起 docker docker compose up -d --build                     │
│  看 docker docker compose logs -f api                      │
│  部署 ECS  bash scripts/deploy-prod.sh                     │
│  紧急停服  docker compose stop api                          │
├─────────────────────────────────────────────────────────────┤
│  db 别名:dev=fastinfo / docker=fastinfo_docker / prod=fastinfo_prod │
│  端口别名:L-API=8000 / S-API=18000 / L-Mongo=27017 / S-Mongo=27018 │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 升级路径(将来要做的)

- [ ] **task 3 落地后**:`start.ps1` 启动横幅会自动染色 env;`/healthz` 返回 `env` 字段;Mongo 集合 `_env` 字段写入(策略待定)
- [ ] **PowerShell PS1 永久染色**:在 `$PROFILE` 加 `prompt` 函数,terminal 永远显示 `[DEV]/[DOCKER]`
- [ ] **前端 EnvBanner**:`<EnvBanner>` 组件贴在 NavBar 顶部
- [ ] **统一 docker 化开发**:让 docker 成为 dev 默认,v 退为 escape hatch

详细蓝图在 `docs/env-isolation-strategy.md`。