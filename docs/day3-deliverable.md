# fastInfo · Day 3 交付
日期:2026-07-02 · 状态:✅ 完成

## 🎯 目标
把 fastInfo 从「CLI + API」升级到「**Web 可视化平台 + 完整文档站**」,覆盖 PRD 的 12 个核心功能。

## ✅ N 件事
1. **Web 前端**(Vue 3 + Vite + Naive UI + Tailwind)
   - 11 个页面:公域首页 / 今日最热 / 全局搜索 / 资讯详情 / 登录 / 注册 / 个人中心 / inbox / 创建订阅 / 管理员首页 / 任务监控 / Banner 配置
   - Pinia 全局状态,JWT 自动注入,Vue Router 路由守卫
   - ECharts 图表(汇总统计)、Naive UI 组件库(表格/表单/抽屉/Tabs)
2. **后端增量 9 个 API** + 2 个新集合
   - `/api/banner` (公开 GET + admin PUT)
   - `/api/categories` (公开)
   - `/api/inbox` (Bearer)
   - `/api/admin/stats/users/subscriptions/tasks/source-status/tasks/runs/tasks/runs/{id}/llm/health/ingest/run` (admin)
   - `/api/subs/parse` (Bearer) — NL 预览
3. **文档站**(VitePress)
   - 12 篇 Markdown:首页 / 快速开始 / 概念 / 鉴权 / NL 订阅 / API 总览 + 6 篇 API 详情
   - VitePress 默认主题 + 顶栏 nav + 侧边栏 sidebar
   - 顶部 nav 直接跳 Swagger UI(`/docs`)
4. **admin 账号初始化脚本** `scripts/init_admin.py`
5. **PRD + 技术架构** 文档 — `.trae/documents/prd.md` + `technical-architecture.md`
6. **数据脚本** `scripts/init_admin_collections.py`

## 🛠️ 改动(关键文件)

### 后端新增
- [src/api/deps_admin.py](file:///d:/WORK/trae/fast_info/src/api/deps_admin.py) - require_admin 依赖
- [src/api/routes/banner.py](file:///d:/WORK/trae/fast_info/src/api/routes/banner.py)
- [src/api/routes/inbox.py](file:///d:/WORK/trae/fast_info/src/api/routes/inbox.py)
- [src/api/routes/categories.py](file:///d:/WORK/trae/fast_info/src/api/routes/categories.py)
- [src/api/routes/admin.py](file:///d:/WORK/trae/fast_info/src/api/routes/admin.py)
- [src/storage/mongo_writer.py](file:///d:/WORK/trae/fast_info/src/storage/mongo_writer.py) - 加 `get_banner/set_banner/list_categories/record_task_run/get_recent_task_runs/get_source_status_24h/get_user_inbox` + `_serialize_datetimes` 工具
- [src/api/schemas.py](file:///d:/WORK/trae/fast_info/src/api/schemas.py) - BannerConfig / TaskRun / SourceStatus / LLMHealth / InboxItem
- [src/api/routes/__init__.py](file:///d:/WORK/trae/fast_info/src/api/routes/__init__.py) - 注册 4 个新 router
- [scripts/init_admin.py](file:///d:/WORK/trae/fast_info/scripts/init_admin.py) - 管理员账号脚本
- [scripts/init_admin_collections.py](file:///d:/WORK/trae/fast_info/scripts/init_admin_collections.py) - 集合初始化

### 后端修改
- [scripts/ingest_daemon.py](file:///d:/WORK/trae/fast_info/scripts/ingest_daemon.py) - 每次抓取自动写 `task_runs`

### 前端(全新)
- [frontend/](file:///d:/WORK/trae/fast_info/frontend/) - Vue 3 + Vite + Naive UI + Tailwind
  - 11 页面 + ItemCard 组件 + DefaultLayout + Pinia auth store + ofetch 客户端
- [frontend/vite.config.ts](file:///d:/WORK/trae/fast_info/frontend/vite.config.ts) - proxy `/api → :8000` + `/docs → :5174`

### 文档(全新)
- [docs-site/](file:///d:/WORK/trae/fast_info/docs-site/) - VitePress 文档站
  - 12 篇 .md + 主题配置

### 文档(更新)
- [AGENTS.md](file:///d:/WORK/trae/AGENTS.md) - §1/§4/§6/§7/§9/§11/§12 同步
- [.trae/documents/prd.md](file:///d:/WORK/trae/fast_info/.trae/documents/prd.md) - 完整 PRD
- [.trae/documents/technical-architecture.md](file:///d:/WORK/trae/fast_info/.trae/documents/technical-architecture.md) - 技术架构

## 📊 当前数据(2026-07-02 实测)

| 集合 / 路由 | 条数 / 数量 |
|---|---|
| `items` | **49** |
| `subscriptions` | **15** |
| `users` | **13** |
| `subscriptions_delivered` | **10** |
| `banner_config` | **1** (新增) |
| `task_runs` | **0** (daemon 还没跑过) |
| `api_e2e_smoke` | **13/13 ✓** (Day 2) |
| 后端 API 总数 | **23 个** (Day 2: 15 + Day 3 新增 9 - 1 重叠 = 23) |
| 前端路由 | **13 条** |
| 前端页面 | **11 个** |
| 文档站页面 | **12 篇** |
| **前端 build 耗时** | **5.46s** |

## 🧪 验证命令

### 后端
```powershell
# 0) 启动 API(8000)
python scripts/api_server.py

# 1) 初始化集合 + admin 账号(各跑一次)
python scripts/init_admin_collections.py
python scripts/init_admin.py --username admin --password "admin@2026"

# 2) 端到端 smoke
python examples/api_e2e_smoke.py --no-ingest   # 13/13
```

### 前端
```powershell
cd frontend
npm install
npm run dev                                    # http://localhost:5173
# 或生产构建
npm run build                                  # 5.46s
```

### 文档站
```powershell
cd docs-site
npm install
npm run dev                                    # http://localhost:5174
```

### 全链路验证
```powershell
# 三个服务同时跑,各自端口:
# 8000 - FastAPI (Swagger UI: /docs)
# 5173 - Vue 前端
# 5174 - VitePress 文档站
# 浏览顺序:打开 5173,玩一遍,然后 5174 看文档,最后 8000 调试 API
```

## ⚠️ 已知 / 推迟
- **Day 4 待做**:subs_scheduler daemon(当前订阅要手动跑)
- **Day 4 待做**:v2 检索(BGE-M3 / LanceDB)
- **P2**:ECharts 按需引入(tree-shake 后包大小待优化)
- **P2**:前端移动端适配(只 desktop 体验,平板未深度测)
- **NEW-7**:ingest_daemon 日志无轮转
- **NEW-8**:requirements.txt 没 pin 版本
- **NEW-9**:CORS 没限制具体域名(开发期 `*`,生产改白名单)

## 🚀 Day 4 预告
- `subs_scheduler.py` daemon:按 `next_run_at` 自动触发
- 抓取扩源:RSS(掘金/V2EX/HN/IT 桔子)+ 热搜 API(Tavily/七牛云/微博)
- v2 检索:BGE-M3 嵌入 + LanceDB + RRF 融合
- 前端补:`/subs/:id` 详情 / 暂停启用 / 触发历史
- 前端补:管理员用户列表的"封禁 / 改角色"
- 移动端布局(平板)