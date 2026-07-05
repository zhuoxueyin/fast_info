# fastInfo · Day 6 交付
日期:2026-07-05 · 状态:✅ 完成(实时依赖监控)

## 🎯 目标
1. 排查"16 个源 NOT_RAN" 的真因
2. 修掉导火索:ingest_daemon 反复死掉
3. 管理后台加 **实时依赖监控**,所有依赖出问题一目了然 + 自动染色

## ✅ 5 件事
### 1. 找到 ingest_daemon 反复死掉的真因(GBK + 无 stale 兜底)
- **GBK 死循环**:daemon 启动后第一次 `print("✗ ...")` → Windows stdout 默认 GBK → UnicodeEncodeError → 抛到 `asyncio.run` 主程序 → daemon 崩溃。`data/ingest.err.log` 抓到 traceback。
- **无 stale 兜底**:`update_task_run_finished` 在 `run_once` 内部抛异常时不会被执行,`task_runs.running` 永远残留;前端的 read 层有 `_normalize_task_run_status`(标记 stale),但 DB 不写回。
- **启动脚本覆盖了也不生效**:`start.ps1` 启动 daemon PID 15536 成功,但 daemon 立刻被 GBK bug 炸死,PID 死亡,看起来"启动没生效"。

### 2. 修 daemon GBK 死循环
`scripts/ingest_daemon.py`:
- 顶层 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`(windows-platform guard)
- `log_line()` 内部 `print` 包 try/except + UnicodeEncodeError 兜底
- daemon 重启后**第一次**就能 print 成功,跑完一轮后 `sleeping 1800s` 正常写日志

### 3. 新增 `reap_stale_task_runs` 一键清理端点
- 已经存在的 helper(`STALE_RUNNING_THRESHOLD_SEC=1800` = 30 min)现在通过 `/api/admin/tasks/reap-stale` 暴露
- 监控 dashboard 顶部按钮"清理僵尸任务"也是调它
- 顺手在 `get_recent_task_runs` 之前自动 reap(已有)

### 4. 新增 `/api/admin/monitoring` 依赖聚合端点
**`src/monitoring/__init__.py`** — 新模块,聚合 8 类依赖:
| 组件 | 检查方式 | 失败影响 |
|---|---|---|
| `mongo` | `client.admin.command('ping')` + server_info | 致命 |
| `redis` | `redis.Redis(REDIS_URL).ping()` | warn(暂不依赖) |
| `api_server` | `httpx.get('/healthz')` 自检 | 致命 |
| `ingest_daemon` | `data/running.pids` PID + `Get-Process` 存在性 | 致命 |
| `subs_scheduler` | 同上 | 致命 |
| `sources` | `source_config` 聚合 | disabled≥5 → warn |
| `tasks` | `task_runs` 当前 running / 24h fail_rate / reap 计数 | fail_rate>30% → fail |
| `llm` | `registry.groups[*].providers[*]` 内部状态,不动真 LLM | circuit_open → warn |

返回统一格式 `{status, detail, latency_ms, extra}`,整体 `overall` 取最差。附带两个新操作端点:
- `POST /api/admin/source/{id}/enable` — 重启用 disabled 源
- `POST /api/admin/source/{id}/restart-daemon` — 手动重启 ingest_daemon(PID 杀 + 子进程 spawn)

### 5. 前端 MonitoringPage + AdminTabs 集成
- `frontend/src/pages/admin/MonitoringPage.vue` — 卡片网格,5 秒自动刷新,顶部 4 颗按钮(刷新/清理/重启/重启用)
- `frontend/src/components/DependencyCard.vue` — 单组件,边框+徽章三态(绿/黄/红)+ 慢延迟提示
- `frontend/src/components/AdminTabs.vue` 加 "实时监控" tab
- `frontend/src/router/index.ts` 加 `/admin/monitoring` 路由
- 下方额外展开:
  - 当前 running 任务列表(显示 trigger / 已跑多久)
  - disabled 源清单(每个一键"重启用")
  - LLM provider 全表(已配置 key / 熔断 / 失败计数 / 所在 group)

## 🛠️ 改动(表)
| 文件 | 变更 |
|---|---|
| `scripts/ingest_daemon.py` | GBK 兜底 + log_line print 包 try/except |
| `src/monitoring/__init__.py` | 新模块(8 组件健康聚合) |
| `src/api/routes/admin.py` | +4 endpoint:monitoring / reap-stale / enable / restart-daemon |
| `frontend/src/pages/admin/MonitoringPage.vue` | 新页面 |
| `frontend/src/components/DependencyCard.vue` | 新组件 |
| `frontend/src/components/AdminTabs.vue` | +"实时监控" tab |
| `frontend/src/router/index.ts` | +路由 |

## 📊 当前数据
- MongoDB:ok · API:ok · LLM(5 provider):ok
- ingest_daemon:**ok · PID 26320 alive**(daemon 已存活验证,跑完一轮发现 8 条新增 items)
- subs_scheduler:ok · PID 30084 alive
- redis:warn(business-not-blocking · Docker 容器健康,但连接 127.0.0.1:6379 超时 · AGENTS.md §1 noted "Redis 当前没被代码使用")
- sources:warn(10 启用 / 6 禁用,disabled 是因历史连续失败 ≥5)
- tasks:**fail** · 当前 0 僵尸但 24h fail_rate 73%(因为昨日多次 daemon 崩溃,24h 内的 failed 任务都堆积;等时间衰减后会恢复 ok)

## 🧪 验证命令
```powershell
# 1. 后端聚合
python scripts/final_snapshot.py
# 或
$tok = (Get-Content data/.session.json -Raw).Trim()
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/admin/monitoring `
  -Headers @{Authorization="Bearer $tok"} -UseBasicParsing

# 2. 前端页面
# 浏览器: http://127.0.0.1:5173/admin/monitoring
# 登录: admin / Admin@2026!

# 3. 重启用 disabled 源
# 浏览器点击 "重启用" 按钮,或:
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/admin/source/huxiu/enable `
  -Headers @{Authorization="Bearer $tok"} -Method POST
```

## ⚠️ 已知 / 推迟
- **24h fail_rate 历史 bad**:今天凌晨 daemon 反复崩溃,24h 内 16 个 failed task,导致 tasks 显示 fail。等明天窗口滚动后会自然消失,或手动 `python scripts/reset_delivered.py` + 清理 task_runs(不推荐)。
- **redis 警告是设计内**:fastInfo 暂不用 Redis,容器健康 ≠ API 可达(端口未映射)。
- **6 个 disabled 源**(huxiu/wallstreetcn/cls/bilibili/autohome/weibo:1887344341/weibo:1643971635)**:不要马上全启用** — 它们都已 consecutive_fails=5,启用后还会立刻再失败。建议先人工看一次失败 reason(`source_runs.error_msg`),再决定要不要真启用。
- 监控的 daemon health check 依赖 `data/running.pids` 的 PID 字段;用 `python scripts/ingest_daemon.py --once` 这种前台跑不会被记录(但下次启动 start.ps1 写的 PID 会被捕获)。

## 🚀 Day 7 预告
按用户当前节奏,接下来两个方向任选其一(或都做):
- **Day 7-A**:disabled 源用 X-API / Apify 替换实现,真正复活(reduce 7 disabled → 0)
- **Day 7-B**:推送可靠性工程(死信队列 + 重试 + 通知失败汇总)
