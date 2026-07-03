# 快速开始

## 1. 环境准备

```powershell
# Python 3.11+ + venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# MongoDB 8.x 本地监听 27017
# Redis 7.x(可选,代码目前不依赖)

# LLM API Key(二选一,推荐都配以启用 fallback)
$env:MMX_API_KEY  = "sk-..."      # 主:M2.7-highspeed / M2.7 / M3
$env:KIMI_API_KEY = "sk-..."      # 备:K2.6
```

## 2. 启动后端

```powershell
# 一键启动 API(uvicorn)
python scripts/api_server.py
# → http://127.0.0.1:8000

# Swagger UI:http://127.0.0.1:8000/docs
# Health:   curl http://127.0.0.1:8000/healthz
```

## 3. 启动前端

```powershell
cd frontend
npm install
npm run dev
# → http://127.0.0.1:5173
```

## 4. 启动文档站(本指南)

```powershell
cd docs-site
npm install
npm run dev
# → http://127.0.0.1:5174
```

## 5. 4 步烟雾测试

```powershell
# 激活 venv
. .\scripts\activate.ps1

# 验证 LLM + fallback
python examples/smoke_test.py                  # 期望 4/4

# 验证 API 全链路
python examples/api_e2e_smoke.py --no-ingest   # 期望 13/13
```

## 6. 注册管理员(可选,用于后台)

```powershell
python scripts/init_admin.py --username admin --password "admin@2026"
# 第一次登录后请改密码!
```

## 7. 手动触发一次抓取

```powershell
# CLI
python fastinfo.py ingest --limit 8

# 或后台守护(30 min 一轮)
python scripts/ingest_daemon.py --interval 1800
```

## 目录结构

```
fast_info/
├── src/                ← Python 后端
│   ├── api/            ← FastAPI routes + schemas
│   ├── auth/           ← JWT + PBKDF2
│   ├── crawler/        ← RSS 抓取
│   ├── llm/            ← 4 级 fallback
│   ├── retrieval/      ← 检索(v1 / v2 升级位)
│   ├── storage/        ← MongoDB CRUD
│   └── subscription/   ← NL 解析 + run
├── scripts/            ← 运维脚本(daemon / smoke / init)
├── examples/           ← 样例(smoke / e2e / fetch+summary)
├── docs/               ← 方案 / 里程碑 / ADR
├── docs-site/          ← 本文档站 (VitePress)
├── frontend/           ← Web 平台 (Vue3 + Vite + Naive UI + Tailwind)
├── data/               ← 运行时数据(log / session)
└── AGENTS.md           ← 项目元文档
```