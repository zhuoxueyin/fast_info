# fastInfo · 部署手册 v2.0

> 适用阶段:正式环境首次部署 + 后续迭代  
> 三环境模型:L(本地)· S(预发)· P(正式)  
> 配套文档:`docs/ports-分配方案.md`(端口规则)/ `AGENTS.md §9.1`(DevOps 路线)

---

## 0. 三环境发布理念(本文核心)

```
                        同一份代码仓库
                              │
                              ▼
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                     ▼                        ▼
   ┌─────────┐          ┌──────────┐              ┌──────────┐
   │  L 本地  │          │  S 预发  │              │  P 正式  │
   │ (开发机) │          │ (本机docker)│             │ (云服务器) │
   └─────────┘          └──────────┘              └──────────┘
   • Python venv        • Docker Compose          • Docker Compose
   • 端口 8000/5173     • 端口 18000/18080         • 端口 18000/18080
   • start.ps1         • deploy-staging.sh        • deploy-prod.sh
   • 改一改代码就跑      • 完整 6 服务全套          • git pull + 完整 6 服务
   • 无容器             • 带容器                    • 带容器 + restart 策略
```

**关键原则(写代码/写文档必须遵守)**:

1. **同一份代码同一份 docker-compose.yml** — 三环境**共用** compose 文件,仅 env 文件差异
2. **代码 0 硬编码端口/URL** — 全部走 env(`FASTINFO_API_PORT`/`MONGO_URL`/等)
3. **容器内端口始终不变** — 仅**主机端口**随环境映射(详见 §3)
4. **首次部署后,**后续迭代只改代码、不改任何 env 文件** — 改代码 → git push → 服务器 git pull + 重 build

---

## 1. 当前 docker / 配置文件全清单(基于 2026-07-04 仓库)

### 1.1 已就位(不需要再改)

| 文件 | 用途 | 谁改 |
|---|---|---|
| `docker-compose.yml` | 6 服务编排 + 端口映射 | 不改,端口走 env |
| `docker/api.Dockerfile` | API + 后台 daemon 共用镜像 | 不改 |
| `docker/web.Dockerfile` | 前端 + 文档构建 + nginx | 不改 |
| `docker/nginx/default.conf` | 反代 /api/、/healthz、/swagger、/docs/ | 不改 |
| `docker/api-entrypoint.sh` | 启动 init admin 账号 | 不改 |
| `.env.example` | 共享 env 模板(密钥段) | 复制为 `.env` 后填密钥 |
| `docker/env.docker.local.example` | Docker 模式差异覆盖(**本机预发用,APP_ENV=docker**) | 复制为 `docker/env.docker.local` |
| `docker/env.prod.local.example` | ECS 生产专用差异覆盖(**APP_ENV=prod**) | 复制为 `docker/env.prod.local` |
| `requirements.docker.txt` | Docker 运行时依赖(精简版) | 不改 |
| `.dockerignore` | 排除 data/、*.log 等 | 不改 |
| `.gitignore` | 排除 .env / env.docker.local / env.prod.local | 不改 |

### 1.2 本次新增(本次手册配套落地)

| 新增文件 | 用途 | 在哪运行 |
|---|---|---|
| `scripts/deploy-local.sh` | L 本地开发环境拉起 | 本机(本机有 docker 起 mongo+redis,API 走 venv) |
| `scripts/deploy-staging.sh` | S 预发布环境拉起 | 本机(完整 6 服务,18080 端口) |
| `scripts/deploy-prod.sh` | P 正式环境拉起/更新 | 云服务器(git pull + build + up + healthcheck) |
| `scripts/check-env-sync.sh` | env 模板与实例同步检查 | 部署前手动跑,发现实例缺 key |
| `docs/deploy-runbook.md` | **本文档**(单一权威源,描述三脚本何时用) | — |

### 1.3 文件加载优先级(必须理解)

```
docker compose up 时,容器内环境变量叠加顺序(高 → 低):

  ┌── compose 的 env_file: docker/env.docker.local     ← 最高
  ├── compose 的 volumes:  ./env:/app/.env             ← 通过 volume 挂进容器
  ├── compose 的 environment: 显式 env: 条目          ← (本项目未用)
  ├── shell 环境变量                                ← 服务器 SSH 时手动 export 的
  └── 代码默认值                                    ← src/_env.py 里的硬默认
```

> 详见 `src/_env.py` 的 `_candidate_paths()` 和 `docker-compose.yml` 的 `env_file:`。

### 1.4 模板与实例文件(必须理解)

本项目把 **env 模板**和 **env 实例**严格分开:

| 类型 | 文件 | 是否进 git | 谁负责更新 | 说明 |
|---|---|---|---|---|
| **模板** | `.env.example` | ✅ 进 git | 代码仓库维护 | 共享配置的key清单,任何环境通用 |
| **模板** | `docker/env.docker.local.example` | ✅ 进 git | 代码仓库维护 | Docker 预发环境的key清单 |
| **模板** | `docker/env.prod.local.example` | ✅ 进 git | 代码仓库维护 | 生产环境的key清单 |
| **实例** | `.env` | ❌ gitignore | 每个环境手动维护 | 真实 API Key / SECRET / 密码 |
| **实例** | `docker/env.docker.local` | ❌ gitignore | 每个环境手动维护 | 预发真实配置 |
| **实例** | `docker/env.prod.local` | ❌ gitignore | 每个环境手动维护 | 生产真实配置 |

**关键规则(违反必踩坑)**:

1. `git pull` **只更新模板**,不会动实例文件。
2. 当模板新增/修改 key 时,实例文件必须**手动同步**,否则部署会退回到代码默认值,甚至报错。
3. 首次部署:从模板复制实例,然后填真实值。
4. 后续迭代:每次 `git pull` 后,先跑 `bash scripts/check-env-sync.sh` 检查实例是否缺 key,再执行部署脚本。
5. 不要把实例文件提交到 git;`.gitignore` 已保护,但请人工确认。

**env 同步检查命令(部署前必跑)**:

```bash
cd /opt/fast_info
bash scripts/check-env-sync.sh
```

- 全绿 ✅:实例包含模板全部 key,可以部署。
- 黄/红 ❌:实例缺少 key,按提示把缺失 key 从模板复制到实例并填值,再重新检查。

---

## 2. 端口规划(三环境对照表)

| 服务 | 容器内 | 本地 L | 预发 S | 正式 P | 备注 |
|---|---|---|---|---|---|
| FastAPI | 8000 | 8000 | **18000** | **18000** | L-+10000 走语义化 |
| Nginx (Web) | 80 | - | **18080** | **18080** | 同上 |
| MongoDB | 27017 | 27017 | **27018** | **27018** | +1 业内惯例 |
| Redis | 6379 | 6379 | **6380** | **6380** | +1 业内惯例 |
| Vite Frontend dev | 5173 | 5173 | - | - | 仅本地开发 |
| VitePress docs dev | 5174 | 5174 | - | - | 仅本地开发 |

**P 环境(云服务器)实际对外(公网)开放**:

| 端口 | 服务 | 必须开? | 备注 |
|---|---|---|---|
| **18080** | Nginx 主入口 | **必开** | 用户访问的唯一端口 |
| **18000** | FastAPI 直连 | 可选 | 给运维/调试用,生产环境可关 |
| 27018 / 6380 | DB | **绝不开** | 数据库不能直接对外暴露 |
| 22 | SSH | 必开 | 部署/排错通道 |

云服务器防火墙(腾讯云轻量是"防火墙",阿里云是"安全组"):

```
入站规则(白名单):
  TCP 22    | 你的 IP(SSH 用)
  TCP 18080 | 0.0.0.0/0(用户访问)
  TCP 18000 | 你的 IP(API 调试,可选)
  
出站规则:
  默认(全开)即可
```

---

## 2.5. 分支策略与三环境对应

> **P 正式环境只部署 `master` 分支。** L/S 环境可跑 feature 分支做自测，但上线代码必须通过 PR/Merge 合入 master。

### 2.5.1 三环境对应分支

| 环境 | 代码位置 | 分支要求 | 用途 |
|---|---|---|---|
| **L 本地** | 本机 venv | feature / 任意 | 开发自测、快速反馈 |
| **S 预发** | 本机 Docker | feature / 任意 | 完整 6 服务验证，通常在 feature 合并前跑一遍 |
| **P 正式** | 云服务器 Docker | **必须 master** | 线上用户访问的唯一代码 |

### 2.5.2 推荐 Git Flow

```text
本机:  git checkout feat/xxx
       ... 改代码 / 本地 L 模式测试 ...
       git commit -m "..."
       git push origin feat/xxx
       
       # 可选：本机 S 模式完整验证
       bash scripts/deploy-staging.sh
       
       # 在 GitHub 提 PR 合并到 master
       # (单人项目也可本地 merge 后 push)

服务器: ssh root@<SERVER_IP>
       cd /opt/fast_info
       git checkout master
       git pull origin master
       bash scripts/deploy-prod.sh
```

### 2.5.3 为什么 P 环境只保留一个目录

### 2.5.5 服务器红线:只读代码,绝不 push

**生产服务器 (`/opt/fast_info`) 只用于部署，禁止在该目录做任何 git push、commit、merge 等写仓库操作。**

原因:

- 服务器代码必须可追踪为 `origin/master` 的精确副本
- 在服务器上写代码/merge 会导致本地和远程分支状态不一致，难以回滚
- 所有代码改动必须在本地开发机完成，由你本人 review 后 push master，服务器只做 `git pull`

**正确流程**:

```text
本地开发机: git checkout feat/xxx → 改代码 → commit → push origin feat/xxx → 你 merge 到 master → push origin master
服务器:      git checkout master && git pull origin master && bash scripts/deploy-prod.sh
```

### 2.5.6 为什么 P 环境只保留一个目录

**不要在服务器上为不同分支建多个项目目录。** 原因:

- Docker volumes(`mongo_data` / `redis_data` / `api_data`)按项目目录隔离，多目录会导致数据分裂
- `.env` 需要维护多份，容易配错
- 端口 18080/18000 只有一套，多目录会冲突

### 2.5.4 `deploy-prod.sh` 的分支保护

脚本已内置分支检查:

- 当前分支不是 `master` 时，**报错退出**，提示切换到 master
- 指定 commit 部署时(`bash scripts/deploy-prod.sh <commit-sha>`)可跳过 master 检查，用于紧急回滚
- 同步代码后用 `git clean -fdx -e .env -e docker/env.docker.local` 清理未跟踪文件，**保留 env 文件**

---

## 3. 首次部署到 P 环境(云服务器) — 完整指令

### 3.0 必须 User 提供(在开始前准备好)

| # | 项 | 提供方式 | 示例 |
|---|---|---|---|
| 1 | 服务器 SSH 公网 IP + 用户名 | 控制台 | `root@1.2.3.4` |
| 2 | SSH 登录方式 | 密钥文件 OR 密码 | `/path/to/key.pem` |
| 3 | (可选)MMX_API_KEY | MiniMax 控制台 | `eyJhbGc...`(只给用得上的那 1 个) |
| 4 | (可选)KIMI_API_KEY | Kimi 控制台 | `sk-...(可不填)` |
| 5 | (可选)FASTINFO_ADMIN_USERNAME | 你 | 默认 `admin`,可不填 |
| 6 | (可选)FASTINFO_ADMIN_PASSWORD | 你 | 默认 `admin@2026`,**生产必须改** |

> 📌 项目当前的 `env.docker.local.example` 里有 `FASTINFO_ADMIN_PASSWORD=admin@2026`(首次启动自动建 admin 账号用)。**生产服务器强烈建议改成强密码**。

### 3.1 [Agent] 服务器初始化(SSH 上去,2-5 min)

```bash
# 3.1.1 连接
ssh root@<SERVER_IP>

# 3.1.2 操作系统确认(必须是 Ubuntu 22.04 或 Debian 11+)
cat /etc/os-release | grep PRETTY_NAME

# 3.1.3 安装 Docker + Compose v2(已装跳过)
if ! command -v docker &>/dev/null; then
  apt-get update && apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") main" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  usermod -aG docker $USER
  newgrp docker
fi

# 3.1.4 验证
docker --version            # 期望:Docker version 24+
docker compose version      # 期望:Docker Compose version v2.x+
```

**确认**:出现 `Docker version 24+` 和 `Docker Compose version v2.x+`。任一缺失,**停下来**。

### 3.2 [Agent] 上传项目代码(2 min)

**方式 A — Git(推荐)**:先本机 `git push`,服务器 clone
```bash
# === 在本机(PowerShell),一次 ===
cd D:\WORK\trae\fast_info
git push origin master    # 前置:需要在 GitHub 建仓库并 add remote

# === 在服务器上 ===
mkdir -p /opt/fast_info
cd /opt/fast_info
git clone https://github.com/<USER>/fast_info.git .
```

**方式 B — scp(没建仓库时)**:
```bash
# === 在本机 PowerShell ===
scp -r D:\WORK\trae\fast_info root@<SERVER_IP>:/opt/fast_info
```

**确认**:
```bash
cd /opt/fast_info
ls | grep -E "(Dockerfile|docker-compose|docker/|src/|scripts/|.env.example)"
# 必须看到这些,缺则停
```

### 3.3 [Agent + User] 创建配置文件(2 min)

```bash
cd /opt/fast_info

# 3.3.1 复制 env 模板
cp .env.example .env
cp docker/env.prod.local.example docker/env.prod.local
```

**3.3.2 [User 必须]** 编辑 `.env`,填这 3 个值(其它不动):

```bash
nano .env
```

```ini
# ──────── 这 3 行必须改 ────────
MMX_API_KEY=sk-你的真实key...          # [User] MiniMax 控制台拿
FASTINFO_SECRET=$(openssl rand -base64 32)   # [Agent 自动填]生产用 32 字节随机
FASTINFO_ADMIN_PASSWORD=你的强密码     # [User] admin 后台登录密码(默认 admin@2026 不安全,改!)
# ──────── 其它保持默认 ────────
KIMI_API_KEY=                       # 留空,除非用 Kimi
# 其余 SMTP/LARK/... 全部保持空(不用就不配)
```

**自动生成 SECRET 的方法**(Agent 自己跑):

```bash
SECRET=$(openssl rand -base64 32)
sed -i "s|^FASTINFO_SECRET=.*|FASTINFO_SECRET=$SECRET|" /opt/fast_info/.env
```

**确认**:
```bash
grep -E "^MMX_API_KEY|^FASTINFO_SECRET|^FASTINFO_ADMIN_PASSWORD" /opt/fast_info/.env
# 三行非空
```

**3.3.3 [Agent 可以]** `docker/env.prod.local` 一律用默认值,不需改(首次部署后请修改默认 admin 密码):

```ini
# 默认值已经正确(端口 18080/18000,服务名 mongo/redis)
MONGO_URL=mongodb://mongo:27017
MONGO_DB=fastinfo_prod
REDIS_URL=redis://redis:6379

# ---------- 应用标识 ----------
# P 正式环境必须标识为 prod;S 预发可改为 staging,L 本地为 dev
APP_ENV=prod

DATA_DIR=/app/data
LANCEDB_DIR=/app/data/lancedb
FASTINFO_WEB_PORT=18080
FASTINFO_API_PORT=18000
FASTINFO_MONGO_PORT=27018
FASTINFO_REDIS_PORT=6380
FASTINFO_BOOTSTRAP=1
FASTINFO_INIT_ADMIN=1
FASTINFO_ADMIN_USERNAME=admin
FASTINFO_ADMIN_PASSWORD=admin@2026
```

> 📌 注意:`docker/env.prod.local` **覆盖** `.env` 里的同名 key,所以 admin 密码实际生效优先级是:`env.prod.local` > `.env`。**若用环境变量覆盖**,得直接改 `env.prod.local` 的 `FASTINFO_ADMIN_PASSWORD`。
> ⚠️ 首次部署成功后,请立刻用 admin 登录并修改密码。

### 3.3.4 [Agent] 部署前 env 同步检查(**必须**,防止模板更新后实例缺 key)

**每次 `git pull` 后、执行 `deploy-prod.sh` 前**,必须跑同步检查:

```bash
cd /opt/fast_info
bash scripts/check-env-sync.sh prod
```

**通过标准**:输出全绿 ✅,无缺失 key。

**如果提示缺失 key**:

```bash
# 例:提示 env.prod.local 缺少 FASTINFO_ADMIN_PASSWORD
# 1. 打开模板,看默认值和注释
nano docker/env.prod.local.example

# 2. 把缺失 key 复制到实例,并填入真实值
nano docker/env.prod.local
```

**为什么不能跳过**:模板文件(`*.example`)会随代码更新,但实例文件(`.local`)被 git 忽略,`git pull` 不会自动同步。实例缺 key 时,程序会退回到代码默认值,导致类似"admin 不存在"这类问题。

### 3.4 [Agent] 启动服务(5-15 min,build 占大头)

**必须走 `scripts/deploy-prod.sh`**,不要直接 `docker compose up`:

```bash
cd /opt/fast_info

# 3.4.1 一键部署(内部包含 env 检查 / build / up / admin 初始化 / 健康检查)
bash scripts/deploy-prod.sh
```

**如果只想本地手动调试用**:

```bash
# 3.4.2 手动 build + up(不推荐生产使用,会跳过 admin 初始化和 env 同步检查)
docker compose up -d --build
sleep 10
docker compose ps
```

**成功判据**:`STATUS` 列所有 service `Up` 或 `Up (healthy)`。
如果有 `Restarting`/`Exit 1`,**别急着继续**,跳 §5 故障定位。

### 3.5 [Agent] 验收(1 min)

```bash
# 3.5.1 API 健康检查(走 Nginx 主入口)
curl -s http://127.0.0.1:18080/healthz
# 期望:{"status":"ok","mongo_version":"8.x",...}

# 3.5.2 API stats(确认 mongo 连上)
curl -s http://127.0.0.1:18080/api/stats
# 期望:JSON,含 items / subscriptions / users 计数字段

# 3.5.3 前端页面
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/
# 期望:200

# 3.5.4 swagger
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/docs
# 期望:200
```

**全 200** → ✅ 首次部署完成。  
**任意失败** → §5 故障定位。

### 3.6 [User 自己] 浏览器验证 + 防火墙放行

```text
浏览器输入:http://<SERVER_IP>:18080/

期望:看到 fastInfo 首页 / 登录页
```

如果只通 SSH 不通 18080 → §5.4 防火墙放行。

### 3.7 [无需操作] deploy 脚本已在 git 里

> 三份脚本(`scripts/deploy-local.sh` / `deploy-staging.sh` / `deploy-prod.sh`)在 git 里追踪,`git clone` 或 `git pull` 后**自动到位**,**不需要在服务器上手工创建**。
>
> 改脚本 = 改 `scripts/deploy-*.sh` 文件 + 提交 → 服务器 `git pull` 自动同步。

**简要说明**:
- `scripts/deploy-local.sh` —— L 本地开发(本机用,起 mongo+redis + 引导用 start.ps1)
- `scripts/deploy-staging.sh` —— S 预发(本机 docker 完整 6 服务)
- `scripts/deploy-prod.sh` —— P 正式(服务器 git pull + build + up + healthcheck)

**验证脚本存在**:

```bash
ls -la /opt/fast_info/scripts/deploy-*.sh
# 期望:deploy-local.sh / deploy-staging.sh / deploy-prod.sh 三个文件,都有 -rwxr-xr-x
```

---

## 4. 后续迭代(改代码 → 三环境分别跑哪个)

> **三份脚本,三环境各一个**,git 里追踪,改完 push 服务器 `git pull` 自动同步。

### 4.1 本机开发(L 模式)— 用 `deploy-local.sh`

**场景**:本机写代码、自测(单服务快速反馈)

```bash
# 首次:本机起 mongo+redis + 提示启动 API
bash scripts/deploy-local.sh

# 启动 API(另开终端)
.\start.ps1                    # Windows PowerShell
# 或
source .venv/bin/activate && python scripts/api_server.py    # Linux/macOS
```

### 4.2 本机预发(S 模式)— 用 `deploy-staging.sh`

**场景**:本机起完整 6 服务(模拟生产,验证 compose 配置)

```bash
# 一次性 build + 完整起
bash scripts/deploy-staging.sh

# 改代码后重 build
bash scripts/deploy-staging.sh
```

### 4.3 服务器正式(P 模式)— 用 `deploy-prod.sh`

**场景**:腾讯云/阿里云服务器拉起或日常迭代

```bash
ssh root@<SERVER_IP>
cd /opt/fast_info

# 确保在 master 分支(P 环境强制要求)
git checkout master
git pull origin master

# 首次部署 / 日常迭代
bash scripts/deploy-prod.sh

# 部署指定 commit(回滚场景)
bash scripts/deploy-prod.sh a1b2c3d4
```

**期望输出**:
```
==> 0/6 前置检查
   ✅ 全部通过
==> 1/6 分支检查
   ✅ 当前分支:master
==> 2/6 同步代码
   当前 commit:a1b2c3d
==> 3/6 build 新镜像(5-15 分钟)
   ✅ build 完成
==> 4/6 restart containers
==> 5/6 健康检查
   ✅ API /healthz 200
   ✅ /api/stats 200
   ✅ 全部 6 个容器 Up
==> 6/6 ✅ 部署完成 · a1b2c3d · 2026-07-05T10:30:00+08:00
```

### 4.4 三脚本对照速查

| 脚本 | 跑在哪 | 干什么 | 跑完起什么 |
|---|---|---|---|
| `scripts/deploy-local.sh` | 本机 | 检 venv/env/docker → 起 mongo+redis | 引导运行 start.ps1(API/ingest/scheduler) |
| `scripts/deploy-staging.sh` | 本机 | 完整 build + 6 服务 up | 6 个 docker 容器(18080 端口) |
| `scripts/deploy-prod.sh` | 云服务器 | git pull + build + up + healthcheck | 6 个 docker 容器(18080 端口) |

### 4.5 `.env` 什么时候动(只 3 个时机)

| 时机 | 谁改 | 改什么 |
|---|---|---|
| 首次部署 | User 提供密钥后由 Agent 写入 | `MMX_API_KEY` / `FASTINFO_SECRET` / `FASTINFO_ADMIN_PASSWORD` |
| 密钥轮换 | User | 比如 6 个月换一次 API key |
| 加新 LLM / 新推送渠道 | User | 比如接个新的搜索 API |

**改代码、迭代功能 → 不动 .env**。

---

## 5. 故障定位(Agent 自助)

### 5.1 容器没起来

```bash
docker compose ps              # 看哪些 service 没 Up
docker compose logs --tail=80 <service-name>   # 单服务日志
```

**最常见的 3 个原因**:

1. `.env` 没创建或没填 `MMX_API_KEY` → API 容器循环重启
2. mongo 容器没起来 → API 等不到 mongo healthy
3. `DOCKER_REGISTRY_PREFIX` 没设 → 国内服务器拉 base image 超时

### 5.2 API 返 502

```bash
docker compose logs api | grep -iE "error|exception|traceback" | head -20
```

**主要排查路径**:

```bash
# A. Mongo 连不上
docker compose exec mongo mongosh --eval "db.adminCommand('ping')"
# 不通 → mongo 没起来 / MONGO_URL 错

# B. Redis 连不上
docker compose exec redis redis-cli ping
# 不通 → redis 容器没起 / REDIS_URL 错

# C. env 没生效
docker compose exec api env | grep -E "MONGO_URL|MMX_API_KEY|FASTINFO_SECRET"
# MMX_API_KEY 应该是你填的真 key,不能是空
```

### 5.3 build 卡

```bash
# 看 build 进度
docker compose build 2>&1 | tee /tmp/build.log

# 卡在 pip install(>10min)→ 改国内源
echo "" >> /opt/fast_info/Dockerfile
echo "RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple" >> /opt/fast_info/Dockerfile
docker compose build

# 卡在 npm install → 改 alpine 镜像源(在 web.Dockerfile 里加)
# 也可以 export 一下:
export DOCKER_REGISTRY_PREFIX=docker.m.daocloud.io/library/
docker compose build
```

### 5.4 端口冲突 / 公网访问不到

```bash
# 看哪些端口在听
ss -tlnp | grep -E '18000|18080|27018|6380'

# 防火墙(TX 轻量"防火墙",Aliyun "安全组")放行:
# TCP 18080 (主入口)
# TCP 18000 (API 调试)
# TCP 22    (SSH)
```

### 5.5 build 期间 CPU 100% 服务不可用

build 期间(5-15 min)容器在重建,API 临时不可用。**接受或避开高峰期**:
- 凌晨 build
- 或改用 Docker Hub 远程 build(本期不实现,Day 8+ 再说)

### 5.6 完全推倒重来

```bash
cd /opt/fast_info
docker compose down --remove-orphans    # 数据卷(mongo_data)保留
docker compose build --no-cache        # 不留缓存
docker compose up -d
```

数据卷(`mongo_data` `redis_data` `api_data`)在 `/var/lib/docker/volumes/`,**不要用 `docker compose down -v`**,会清空数据库。

---

## 6. 日常运维速查(Agent 自助)

```bash
cd /opt/fast_info

# 看所有容器状态
docker compose ps

# 看日志(全服务,实时)
docker compose logs -f

# 看日志(单服务最后 100 行)
docker compose logs --tail=100 api
docker compose logs --tail=100 ingest_daemon

# 重启某个服务
docker compose restart api

# 重启全部
docker compose restart

# 资源占用
docker stats

# 磁盘占用
docker system df

# 进容器调试
docker compose exec api bash
docker compose exec mongo mongosh

# mongo 备份(数据安全)
docker compose exec mongo mongodump --archive=/tmp/backup.archive --db fastinfo
docker cp <container>:/tmp/backup.archive /opt/fast_info/backup/
```

---

## 7. 不要做的事

| ❌ | 后果 |
|---|---|
| `docker compose down -v` | **清空 mongo/redis 数据** |
| 在 build 中 `reboot` 服务器 | 可能 corrupt Docker |
| 把 `.env` 文件 commit | 密钥进 git 历史 |
| 改 `docker-compose.yml` 的端口硬编码(不走 env) | 三环境不再共用 |
| 在 Python 代码写 `127.0.0.1:8000` 而不读 env | L 模式无法工作 |
| 直接 `kill -9` 容器 | 失去 docker 的 restart 策略保护 |

| ✅ | |
|---|---|
| `.env` 改完必须 `docker compose restart` | 才会生效 |
| mongo 每周 `mongodump` 一次 | 数据安全 |
| 改 Dockerfile → `docker compose build --no-cache` | 强制重建镜像层 |
| 改 docker-compose.yml → `docker compose up -d` | 重新创建服务 |

---

## 8. 已清理的过时文档

本次发布前清理(2026-07-04):

| 文件 | 处置 | 原因 |
|---|---|---|
| `docs/day6-deploy-plan-v1.0.md` | 删 | 当时写的是 GitHub Actions + TCR 路线,本次采纳更简单的"git pull + up -d --build",该文档过期 |
| `docs/server-deploy-runbook.md` | 删 | 之前一版,覆盖了回滚演练、故障排错等大量需求外的章节 |
| `docs/deploy-only.md` | 删 | 上一版精简版,缺乏三环境对齐和 [Agent]/[User] 责任划分 |

---

## 9. 版本与衔接

- **当前版本**:`deploy-runbook` v2.0(2026-07-04)
- **衔接**:`AGENTS.md §9.1` 的 DevOps Day 5-9 路线图中,本文档兑现了 Day 6-7 的目标(同机 docker 预发 + 服务器 docker 正式);Day 8 域名/HTTPS、Day 9 回滚演练 暂时不在本文档范围(用户当前不需要)
- **未来扩展点**(本次不实现):
  - 加入 nginx HTTPS + Cloudflare(对应 ADR-015)
  - 加入腾讯云 MongoDB 托管(对应 ADR-014)
  - 加入 staging/prod `compose -p` 隔离(对应 ADR-016)
  - 加入镜像 tag + 回滚脚本(对应 ADR-017)

---

## 10. 验证清单(完成后逐项打勾)

```text
L 本地模式(本机 bash)
[ ] bash scripts/deploy-local.sh 通过前置检查
[ ] docker compose ps mongo redis 都在 Up
[ ] .venv 提示运行 start.ps1(或手动 python scripts/api_server.py)
[ ] 浏览器访问 http://127.0.0.1:8000/healthz 200

S 预发模式(本机 docker)
[ ] bash scripts/deploy-staging.sh 通过 5 阶段检查
[ ] 6 个容器全 Up
[ ] curl 127.0.0.1:18080/healthz 200
[ ] 浏览器访问 http://127.0.0.1:18080/ 看到前端

P 正式模式(云服务器,首次)
[ ] 服务器 OS 是 Ubuntu 22.04+
[ ] docker / docker compose 都装好
[ ] /opt/fast_info 有完整代码(包括 scripts/deploy-{local,staging,prod}.sh)
[ ] 当前在 master 分支(`git branch --show-current`)
[ ] .env 填了 MMX_API_KEY / FASTINFO_SECRET / FASTINFO_ADMIN_PASSWORD
[ ] docker env.docker.local 复制自 .example
[ ] 腾讯云防火墙放通 TCP 18080/22(18000 可选)
[ ] bash scripts/deploy-prod.sh 走完 6 阶段
[ ] curl 127.0.0.1:18080/healthz 200
[ ] curl 127.0.0.1:18080/api/stats 200
[ ] 浏览器访问 http://<SERVER_IP>:18080/ 看到前端

P 正式模式(后续迭代)
[ ] 本机 feature 分支开发 + 自测
[ ] push feature → PR/Merge 到 master
[ ] 服务器 `git checkout master && git pull origin master`
[ ] bash scripts/deploy-prod.sh
[ ] 6 阶段全过,显示"部署完成 · commit xxx"
[ ] /healthz 仍 200
[ ] UI 显示新代码生效(可手动查某一处代码差异)
```

---

*Last updated: 2026-07-04 · 配套 AGENTS.md §9.1*
