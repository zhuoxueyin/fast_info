# fastInfo · 环境隔离与排查防蹿方案 v1.0
======================================

> 📌 **Day 5 配套文档**
> 痛点:本机 + Docker 预发两套环境数据隔离,但排查异常时经常蹿环境(看错日志、连错库、用错 API 地址)。
> 方案:用 **5 层防御 + 2 个工具脚本**,从 shell 到数据库全链路打"环境身份标识"。

---

## 0. 一句话总结

**在终端外壳、日志、API 响应、MongoDB 集合、前端 5 层都贴 `APP_ENV` 标签,
让人/工具一眼能看出"我现在在哪一套"。** 任何代码分支都不能假设当前是哪套环境。

---

## 1. 现状问题

| # | 现象 | 根因 |
|---|---|---|
| 1 | 2 个 PowerShell 窗口都开了 fastInfo,不知道哪个跑的是哪套 | shell 无 env 标识 |
| 2 | `data/backend.log` 本地/Docker 容器同名,`tail -f` 时容易搞混 | 日志路径无 env 前缀 |
| 3 | `mongosh` 复制粘贴命令时默认连 `127.0.0.1:27017`,本地环境,但用户想查 docker | 客户端无 db 名提示 |
| 4 | Swagger 看到 `:18000` 端口,以为是线上 | 接口无 env 标识 |
| 5 | 同事问"线上订阅数据怎么少了一条",查了半天发现是 docker 那套被 reset 过 | 数据隔离但视觉无差异 |

---

## 2. 核心设计原则

### 2.1 单一真实源(Single Source of Truth)

**`APP_ENV` 是唯一的"环境身份变量"**,所有代码、脚本、文档都从这里读:

```
APP_ENV = dev | docker | prod | staging | test
```

读法优先级(高→低):
1. shell `export APP_ENV=...`
2. `.env` / `docker/env.docker.local` 里的 `APP_ENV=`
3. `src/_env.py` 启发式兜底(读 `/proc/1/cgroup` 或 `MONGO_URL`)

**严禁**:
- ❌ 各处自定义 `RUN_MODE` / `DEPLOY_ENV` / `IS_LOCAL` 等别名变量
- ❌ 代码里写 `if hostname == 'aliyun-ecs'` 之类的硬编码判断
- ❌ 用 `if port == 8000:` 推断环境(端口可变,不是身份)

### 2.2 隔离 + 标识 双保险

| 层 | 隔离手段 | 标识手段 |
|---|---|---|
| 端口 | L-* vs S-* 端口段不同 | `data/whoami.json` + shell PS1 |
| 数据库 | `MONGO_DB` 不同(dev=fastinfo / docker=fastinfo_docker) | 集合首字段 `_env`(可选) |
| 文件 | 日志路径带 env 后缀 | 文件名 + 内容前缀 |
| API | 不同端口 + CORS | 响应头 `X-FastInfo-Env` |

**隔离防事故,标识防误判**。两层都要做。

---

## 3. 5 层防御(完整蓝图)

### 第一层:Shell 外壳(日常最常看到)

**改动点**:

1. **PowerShell 提示符永久染色**:在 `$PROFILE` 里加:
   ```powershell
   # 加载后根据 APP_ENV 给提示符染色
   function prompt {
       $envName = $env:APP_ENV
       if (-not $envName) {
           if ($env:MONGO_URL -like 'mongodb://mongo:*') { $envName = 'docker' } else { $envName = 'dev' }
       }
       $color = switch ($envName) {
           'docker'  { 'Yellow' }
           'prod'    { 'Red' }
           'staging' { 'Magenta' }
           default   { 'Cyan' }
       }
       $tag = "[$($envName.ToUpper())]"
       "$tag $(Get-Location) > "
   }
   ```

2. **`whereami.ps1` 一键查**(✅ 已落地):
   ```powershell
   .\scripts\whereami.ps1          # 详细
   .\scripts\whereami.ps1 -Quick   # 一行总结
   .\scripts\whereami.ps1 -Json    # 脚本串联
   ```
   输出:ENV tag / MONGO_URL / MONGO_DB / Mongo ping / 来源层级(shell vs .env vs docker.env)。

**效果**:开 shell 第一眼就看到 `[DEV]` 或 `[DOCKER]` 彩色前缀;查异常前先 `whereami` 一次,5 秒确认环境。

---

### 第二层:日志(查问题时主要靠它)

**改动点**:

1. **日志路径带 env 后缀**:
   ```
   data/dev.backend.log     ← 本地
   data/docker.backend.log  ← Docker 容器内
   ```
   start.ps1 启动时根据 `$env:APP_ENV` 决定文件名;docker-compose 卷挂载时重命名。

2. **日志行前缀注入**:用 logging filter,每行自动加 `[DEV]` / `[DOCKER]`:
   ```python
   # src/_log.py
   import logging, os
   class EnvPrefixFilter(logging.Filter):
       def filter(self, record):
           record.env_tag = f"[{os.environ.get('APP_ENV','dev').upper()}]"
           return True
   # formatter: "%(asctime)s %(env_tag)s %(name)s %(levelname)s %(message)s"
   ```

3. **uiautomator/start.ps1 启动横幅**带 env 颜色(后续在 start.ps1 改造里落地)。

**效果**:`tail -f data/backend.log` 时每行都有 `[DEV]` 前缀,跟另一个 shell 的 `[DOCKER]` 区分。

---

### 第三层:API 响应(代码里最常判断)

**改动点**:

1. **`/healthz` 增强**(返回 env 字段):
   ```json
   {
     "status": "ok",
     "mongo_version": "8.0.4",
     "env": "docker",
     "env_tag": "[DOCKER]",
     "mongo_db": "fastinfo_docker",
     "mongo_url_host": "mongo:27017"
   }
   ```

2. **新增 `/api/whoami`**:跟 `healthz` 差不多但更详细,任何用户都能调,方便 curl 自查。

3. **响应头 `X-FastInfo-Env`**:每个 API 响应都带,curl `-I` 即可见。

4. **Swagger UI 标题**:`fastInfo API · [DOCKER]` (FastAPI 的 `title` 是创建时定的,用 lifespan + middleware 动态改写)。

**效果**:Swagger 标题一眼区分;curl 自查快速。

---

### 第四层:MongoDB(数据真相)

**改动点**(可选,默认关闭,因为会污染数据):

1. **写入时自动加 `_env` 字段**(双保险):
   ```python
   # storage/mongo_writer.py 的 insert 前
   doc['_env'] = os.environ.get('APP_ENV', 'dev')
   ```
   已有 `_id` 为主键,`_env` 只是个冗余字段,查询时 `db.items.find({_env: 'docker'})` 防止蹿环境。

2. **诊断 helper 脚本**:`scripts/dump_db.py` 强制要求指定 `--env`,禁止无差别 dump:
   ```bash
   python scripts/dump_db.py --env docker --out backup.json
   python scripts/dump_db.py --env dev --out dev.json
   ```

3. **admin 后台 banner**:SourcesPage / BannerConfigPage 顶部永远贴彩色 env 条。

**效果**:即使误连错数据库,数据 `_env` 字段也会暴露"哦这是 docker 那套"。

---

### 第五层:前端(给人最后一道屏障)

**改动点**:

1. **`<EnvBanner>` 组件**:NavBar 顶部彩色横条,管理员可见:
   ```
   ┌──────────────────────────────────────────────────┐
   │ ⚠ [DOCKER] mongo=fastinfo_docker   [切环境] [?]  │
   └──────────────────────────────────────────────────┘
   ```

2. **api.ts 拦截器**:收到 5xx 时自动在 toast 里附 env 信息。

3. **admin 登录后弹一次 toast**:首次进 admin 强制确认"这是 docker 不是 prod"。

**效果**:Web 上管理员第一眼看到彩色横幅,即使别人误登录 docker 也不会当成 prod 操作。

---

## 4. 已落地(本次最小集) ✅

| 工具 | 路径 | 作用 |
|---|---|---|
| `whereami.ps1` | `scripts/whereami.ps1` | 一键查当前 shell 在哪套环境 |
| `diag_env.ps1` | `scripts/diag_env.ps1` | 全维度诊断(端口 + HTTP + Mongo) |
| `env_identity.py` | `src/env_identity.py` | Python 端统一读 `APP_ENV` / 生成彩色横幅 |
| `_env.py` 增强 | `src/_env.py` | APP_ENV 启发式兜底,加载 .env 后自动设 |

**立即可用**:
```powershell
# 第一步:查我在哪
.\scripts\whereami.ps1
.\scripts\whereami.ps1 -Quick    # 一行总结
.\scripts\whereami.ps1 -Json     # 给脚本用

# 第二步:查环境健康
.\scripts\diag_env.ps1                # 当前 env
.\scripts\diag_env.ps1 -Target dev    # 显式 dev
.\scripts\diag_env.ps1 -Both          # dev + docker 对比
```

---

## 5. 待落地(蓝图,等你拍板)

按收益/工作量排序:

### 5.1 高收益低成本(半小时内)

- [ ] **start.ps1 启动横幅染色**:启动时第一行彩色显示 env + 端口
- [ ] **healthz 加 env 字段**(改 `src/api/app.py`)
- [ ] **MongoDB 集合 `_env` 字段**(改 `src/storage/mongo_writer.py`,可选)

### 5.2 中收益中成本(半天)

- [ ] **PowerShell `$PROFILE` PS1 染色脚本**(改 `scripts/activate.ps1`)
- [ ] **日志前缀 filter**(新增 `src/_log.py` + `ingest_daemon.py` / `subs_scheduler.py` 接)
- [ ] **前端 `<EnvBanner>` 组件**(`frontend/src/components/EnvBanner.vue`)

### 5.3 低收益高成本(暂缓)

- [ ] Swagger 标题动态改写
- [ ] CORS 收紧到具体 env
- [ ] admin 登录二次确认 toast
- [ ] 自动 dump/db 同步脚本

---

## 6. 编码铁律(PR review 检查点)

| # | 原则 | 反例 | 正例 |
|---|---|---|---|
| P1 | **必须读 `APP_ENV`**,不读硬编码 | `if hostname.startswith('ecs')` | `if os.environ['APP_ENV'] == 'prod'` |
| P2 | **必须能 0 改动跑两套 env** | `mongosh ... --host mongo` | `mongosh $MONGO_URL` |
| P3 | **新代码必须自带 env 标识** | 启动不打 env tag | `startup_banner('api')` |
| P4 | **错误日志必须带 env** | `logger.error('failed')` | `logger.error('[DOCKER] failed')` |

---

## 7. 配合现有架构

| 现有机制 | 怎么配合 |
|---|---|
| `src/_env.py` 加载 `.env` | ✅ 已在里面加 APP_ENV 兜底 |
| `docker/env.docker.local.example` | ✅ 已声明 `APP_ENV=docker`,无需改 |
| `.env.example` | 📝 待加注释:`# APP_ENV 默认 dev,Docker compose 会覆盖` |
| `start.ps1` / `stop.ps1` / `status.ps1` | 📝 待 start.ps1 启动横幅染色 |
| `docs/ports-分配方案.md` L-* vs S-* | ✅ 端口天然隔离,无需改 |
| `AGENTS.md` P1~P3 | ✅ 本方案不破坏 P1(无历史兼容),不破坏 P3(admin 唯一) |

---

## 8. FAQ

**Q1: 为什么不直接用 hostname 判断?**
A: hostname 不可控(本地开发 / GitHub Actions / 阿里云 ECS 都不同),APP_ENV 是显式声明,最可靠。

**Q2: APP_ENV 不声明行不行?**
A: `_env.py` 启动时会启发式兜底,但**强烈建议显式声明**——本地开发就在根 `.env` 里写 `APP_ENV=dev`,Docker 在 `env.docker.local` 里写 `APP_ENV=docker`,一劳永逸。

**Q3: dev 和 docker 数据会不会意外串?**
A: 不会。`MONGO_URL` 不同(127.0.0.1:27017 vs mongo:27017)+ `MONGO_DB` 不同(fastinfo vs fastinfo_docker),物理隔离。标识只是辅助,不是隔离手段。

**Q4: 已经在用的同事需要改什么?**
A: 无需改代码,只需:
- 在根 `.env` 里加一行 `APP_ENV=dev`
- 排查异常前习惯跑 `whereami.ps1`

**Q5: 旧分支(没改 _env.py)的代码还能跑吗?**
A: 能。`_env.py` 兜底是纯增量,没 APP_ENV 时默认 'dev',对旧代码 0 影响。

---

## 9. 版本

- v1.0 · 2026-07-05 · Day 5 配套,核心方案 + 最小集落地