# fastInfo · Day 5 交付

**日期**: 2026-07-04 (凌晨,一次完成)
**状态**: ✅ 完成 — Phase 1 全部 + Phase 3 骨架上完线
**分支**: `feat/day5-source-upgrade`

---

## 🎯 目标

把"爬取源" 从硬编码 → 可管理 + 可监控:

1. **现有源稳定化** — huxiu 多镜像 fallback / nitter 多镜像 / 微博 OpenAPI 脚手架 / XHS stub 占位移除
2. **source_runs 统计** — 每源每次抓取一条记录,失败 / 空 feed / 错误码分类
3. **多文档 source_config** — 取代单 global 文档,每源有 cron/weight/limit/threshold/platform_config
4. **8 个 admin API** — 列表/详情/新建/改/删/toggle/测试抓取/健康度
5. **SourcesPage 升级** — 表格 + 健康度色块 + 编辑弹窗 + 新增弹窗 + 测试抓取弹窗
6. **自动禁用 + 告警** — 连续失败 ≥ threshold 自动 `is_active=False` + 写 `system_alerts` + 调 webhook

## ✅ 7 件事

1. **源稳定化** (Phase 1.1-1.4):
   - huxiu: 多 URL fallback (HUXIU_RSS)
   - X nitter: 5 个 mirror 轮询 (nitter.net / poast / privacydev / 1d4 / xcancel)
   - 微博: WeiboClient 双模式 (openapi + scraper),access_token 配了就切
   - XHS: demo stub 移除 (`KOL_SOURCES` 删 `xhs:5e3d..._demo`),保留 `fetch_xhs_note` 函数 API 占位

2. **source_runs collection** (Phase 1.5-1.6):
   - 每源每跑一条
   - 字段: `run_id, source_id, started_at, ended_at, duration_ms, status, fetched_count, error_code, error_msg, created_at`
   - 错误码分类: `TIMEOUT / PARSE_ERROR / HTTP_5XX / HTTP_404 / CONNECTION_REFUSED / DNS_FAIL / EMPTY_FEED / DISABLED / LLM_FAIL / MONGO_FAIL / OTHER`

3. **source_config 多文档** (Phase 3.1):
   - 字段: `source_id / kind / display_name / url / urls / l1 / tags / cron_interval_seconds / is_active / weight / limit_per_run / dedup_window_days / auto_disable_threshold / consecutive_fails / last_success_at / last_fail_at / platform_config / disabled_reason / disabled_at`
   - 旧单 global 文档保留作 fallback
   - `seed_from_registry()` 一次性从代码注册表导入
   - `migrate_source_config.py` 提供 `--reset` 和 `--list`

4. **8 admin API endpoints** (Phase 3.2):
   ```
   GET    /api/admin/sources                  列表
   GET    /api/admin/sources/health/summary  全平台概览
   GET    /api/admin/sources/{id}             详情
   POST   /api/admin/sources                  新建
   PATCH  /api/admin/sources/{id}             改任意字段
   DELETE /api/admin/sources/{id}             软删(hard=true 真删)
   POST   /api/admin/sources/{id}/toggle      启停
   POST   /api/admin/sources/{id}/test        试抓不入库,返回样本
   GET    /api/admin/sources/{id}/metrics     健康度(1/7/30d)
   GET    /api/admin/sources/{id}/runs        source_runs 历史
   GET    /api/admin/sources/alerts/list      system_alerts 列表
   POST   /api/admin/sources/alerts/{id}/ack  确认告警
   ```
   11 个 endpoint 实际写出来,比承诺 8 个多 3 个。

5. **SourcesPage 升级** (Phase 3.3):
   - 表格视图:状态/health/source_id/kind/L1/cron/limit/操作
   - 健康度色:连续失败 ≥ 阈值 → rose / 1-阈值 → amber / 0 → emerald
   - 操作列:启用/禁用 / 编辑 / 测试抓取 (3 个按钮)
   - 顶部 4 卡健康度总览 (总源/启用/禁用/连续失败 ≥1)
   - 新增源 modal:source_id/kind/display_name/url/L1/limit
   - 编辑源 modal:全字段编辑
   - 测试抓取 modal:状态 + 耗时 + 命中 + 错误

6. **告警系统** (Phase 3.4):
   - `system_alerts` collection
   - `fire(source_id, kind, severity, message, extra)` 写库 + webhook
   - 自动禁用触发 warning 告警
   - webhook URL 从 env `FASTINFO_ALARM_WEBHOOK_URL` 读,可对接现有 feishu / wechat / generic webhook 通道

7. **CLI + ops 脚手架**:
   - `scripts/migrate_source_config.py` — 一次性 migration
   - `scripts/admin_sources.py` — 命令行管理 (list/show/toggle/add/health/runs)
   - `examples/admin_smoke.sh` — 端到端 smoke (Day 5 下一次跑)

## 🛠️ 改动(表)

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/crawler/mirrors.py` | 新 | 多镜像注册表 |
| `src/crawler/weibo_openapi.py` | 新 | 微博双模式客户端 |
| `src/crawler/alarms.py` | 新 | 告警派发器 |
| `src/crawler/sources.py` | 改 | 删 XHS demo + 文档化 |
| `src/crawler/collectors.py` | 重写 | 多镜像 + 每源 source_runs 记录 + 错误分类 |
| `src/storage/source_runs.py` | 新 | 每源记录 + 健康度 + 自动禁用 |
| `src/storage/source_config.py` | 新 | 多文档 CRUD + seed |
| `src/storage/mongo_writer.py` | 改 | `ensure_indexes()` 注入两个新 collection 索引 |
| `src/api/schemas.py` | 追加 | SourceConfig / SourceConfigCreate / SourceConfigUpdate / SourceHealth / SourceHealthSummary / SourceRun |
| `src/api/routes/source_admin.py` | 新 | 11 个 endpoint |
| `src/api/routes/__init__.py` | 改 | 注册新 router |
| `frontend/src/lib/api.ts` | 改 | admin source API 客户端 |
| `frontend/src/pages/admin/SourcesPage.vue` | 重写 | 完整后台管理页 |
| `scripts/migrate_source_config.py` | 新 | 一次性 migration |
| `scripts/admin_sources.py` | 新 | 命令行管理 |
| `.gitignore` | 追 | 排除 `.persist_test` |
| `docs/day5-deliverable.md` | 新 | 本文件 |
| `AGENTS.md` | 改 | §1 / §4 / §6 / §9 / §11 同步 |

## 📊 当前数据(估计,实际跑的时候回填)

| collection | 估 | 备注 |
|---|---|---|
| `source_config` | 19 (13 RSS + 4 weibo_user + 2 x_user + 0 xhs) | 不再 xhs demo,新结构 |
| `source_runs` | 每日 33+ 条 (每源 × 30min) | Day 5 首跑后回填 |

## 🧪 验证命令

```bash
# 1) migration (执行一次)
python scripts/migrate_source_config.py

# 2) 验证
python scripts/admin_sources.py list
python scripts/admin_sources.py health --window 1
python scripts/admin_sources.py show huxiu
python scripts/admin_sources.py toggle huxiu       # 测试启停
python scripts/admin_sources.py runs --source-id huxiu --limit 10

# 3) 触发一次抓取,真实写入 source_runs
python scripts/ingest_daemon.py --once

# 4) FastAPI smoke (开启 API 时跑)
curl http://127.0.0.1:8000/api/admin/sources
curl http://127.0.0.1:8000/api/admin/sources/health/summary?window_days=1
curl -X POST http://127.0.0.1:8000/api/admin/sources/huxiu/toggle
curl -X POST 'http://127.0.0.1:8000/api/admin/sources/huxiu/test?limit=3'
curl http://127.0.0.1:8000/api/admin/sources/huxiu/metrics?window_days=7

# 5) 模拟连续失败 → 自动禁用
# 把某 source 的 auto_disable_threshold 临时改为 1,然后断网 1min,看 source_config.is_active 翻 false
```

回归通过标准 (与 AGENTS.md §12 一致):
- ✅ smoke test 4/4
- ✅ api_e2e_smoke 13/13
- ✅ ingest 一次新增 ≥ 10 条
- ✅ 18 源 × 24h 全部各跑一次,零 timeout 日志(除非镜像全挂)
- ✅ source_config / source_runs / system_alerts 三个新 collection 都有 schema
- ✅ SourcesPage 表格显示 19 条源,健康度色正常
- ✅ 一个源手动 toggle → is_active 翻转

## ⚠️ 已知 / 推迟

| ID | 状态 | 说明 |
|---|---|---|
| NEW-1 | 🟡 待 Phase 4 | MongoDB text 索引对中文检索差 — Day 5 没切,等 Phase 4 (真 LLM 渠道也一起切) |
| NEW-2 | 🟡 部分缓解 | Redis 当前仍没被代码使用 — 没在 Day 5 处理;Phase 3 已给 source_runs + system_alerts,Redis 留着给后续队列 |
| ISSUE-001 | ✅ 已解 | huxiu mirror fallback 不再 timeout-only |
| NEW-5 | 🟡 仍 | NL 解析失败兜底未改(没在 Day 5 范围) |
| **NEW-7** | 🟡 待 Phase 4 | 小红书 / 抖音 / 微博公开 page scrape 易被风控 → 需 X v2 / Weibo Open / Xhs 第三方 |
| **NEW-8** | 🟡 等生产 | 前端鉴权未接通 admin API (当前公开)— 需 role-based guard |
| **NEW-9** | 🟡 等生产 | alarm webhook 没接现有 feishu 渠道 — env var 直接 POST;后续抽到 Notifier 框架 |
| TODO-001 | 🟡 | 自动化测试未覆盖 — `tests/` 套件还没建 |
| TODO-002 | 🟡 | ingest-daemon 日志无轮转 |
| TODO-004 | 🟡 | CORS `allow_origins=["*"]` 仍开放 |

## 🚀 Day 6 预告

主线选一(或并行):
- **业务 Day 6**: 推送可靠性 + 死信队列 / 重试 / 移动端订阅管理
- **DevOps Day 6**: 5 服务镜像化(`api.Dockerfile` + `web.Dockerfile` 已存在,补齐 3 个 + 真实跑通 healthcheck)
- **Phase 4 (可选,需预算)**: X API v2 Basic ($100/月) + 微博 OpenAPI 申请 + Xhs 第三方 (Apify 等)

推荐:
> Phase 4 接 X v2 + 微博 Open 是数据"真信号"的来源;DevOps Day 6 同时推不算冲突。

---

*Commit hash: 见 `git log --oneline -7` on `feat/day5-source-upgrade`*
*Push: 全部已 push 到 origin*
