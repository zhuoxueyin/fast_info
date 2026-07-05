# fastInfo · Day 6 增强 — 实时监控重构 + 跨页同步
日期:2026-07-05 · 状态:✅ 完成

## 🎯 目标
Day 6 第一轮 SourcesPage 增强完工后,用户反馈 3 个新问题:
1. **监控页 8 个 `?0/?1` 卡片是啥意思** — 前端 cache 显示过期,后端实际是 dict
2. **监控维度不对** — 缺 web/docs;僵尸任务应该自动清理(去掉手动按钮)
3. **数据源"重启"后必须刷新才更新** — 跨页状态不同步(MonitoringPage 上 enable 不通知 SourcesPage)

## ✅ 6 件事

### 1. 后端 monitoring 加 `check_web` + `check_docs`
`src/monitoring/__init__.py`:
- 新增 `_check_http_endpoint(url, label, timeout)` 通用 HTTP 端点检查
- `check_web()` — 候选端口 5173 (vite dev) / 18080 (docker nginx) / 8080 / `FASTINFO_WEB_URL` env,失败 = warn(web 不是强依赖)
- `check_docs()` — 5174 (vitepress dev) / 18080/docs/ / `FASTINFO_DOCS_URL` env
- 新增 `check_daemon()` — 聚合 ingest_daemon + subs_scheduler 一个卡片(Day 7 用户期望)

### 2. 后端 `collect_monitoring()` 重构 — 三组结构
返回结构改成::
```
{
  "overall": "ok|warn|fail",
  "checked_at": "...",
  "groups": {
    "services": { web, api_server, docs, mongo, daemon },  # 5 项核心
    "tasks":    { tasks },                                  # 1 项,自动 reap
    "resources": { redis, sources, llm }                    # 3 项,次要
  },
  "components": { ...所有 9 个平铺,给老前端兼容 }
}
```
- overall 只看 services + tasks 两组(核心),resources 走 warn 不影响整体红绿
- 兼容旧版:顶层 `components` 保留,前端可平滑过渡

### 3. 前端 MonitoringPage — 三段式布局
`frontend/src/pages/admin/MonitoringPage.vue`:
- **🛰️ 核心服务** — 5 项(影响当前使用,直接卡片展示 + 自定义 extras)
- **⚙️ 任务运行** — 1 项(僵尸自动 reap,显示 "本轮自动清理 N 个" + 失败率 + running_now 列表)
- **▶ 其他资源** — 默认折叠(redis/sources/llm)
- **去掉手动"清理僵尸任务"按钮** — 后端 check_tasks() 已经在每次监控拉取时自动 reap_stale_task_runs()
- daemon 卡片 extras 展开 ingest/scheduler 子状态

### 4. DependencyCard 加 web/docs/daemon 映射
`frontend/src/components/DependencyCard.vue`:
- `titles` 加 `web: '前端 Web' / docs: '文档站' / daemon: '后台 Daemon'`
- `icons` 加 `·WEB / ·DOC / ·DAM`

### 5. SourcesPage — 跨页自动刷新
`frontend/src/pages/admin/SourcesPage.vue`:
- onMounted: 监听 `window.focus` + `document.visibilitychange` + 自定义事件 `fastinfo:sources-changed`
- onBeforeUnmount: 清理监听
- 从 MonitoringPage 切回 / 切到本页面 / 广播事件都会自动 refreshAll()

### 6. MonitoringPage 广播事件
- `enableSource()` 成功后 `window.dispatchEvent(new CustomEvent('fastinfo:sources-changed', ...))`
- SourcesPage 监听后自动 refresh — 解决跨页状态不同步

## 🛠️ 改动(5 个文件)

| 文件 | 改动 |
|---|---|
| `src/monitoring/__init__.py` | +`check_web` +`check_docs` +`check_daemon` +`collect_monitoring` 三组结构 |
| `frontend/src/pages/admin/MonitoringPage.vue` | 完全重写:三段式 + 去 reap 按钮 + 广播事件 |
| `frontend/src/components/DependencyCard.vue` | +web/docs/daemon title/icon |
| `frontend/src/pages/admin/SourcesPage.vue` | +visibilitychange/focus/sources-changed 自动刷新 |

零新增依赖,零 DB migration。

## 📊 当前数据(2026-07-05 09:48)
monitoring 接口返回(curl 实测):
```
overall: fail  (tasks fail: 24h fail rate 66%)
groups.services: api_server(ok) / daemon(ok) / docs(ok) / mongo(ok) / web(ok)
groups.tasks:    tasks(fail) — 19 failed / 7 done / 3 null
groups.resources: llm / redis(warn — 本地没起) / sources(ok)
```

## 🧪 验证命令

```powershell
# 1. 强刷浏览器 (Ctrl+Shift+R)
http://127.0.0.1:8000/admin/monitoring

# 应该看到:
#   - 顶部 "🛰️ 核心服务" 5 个卡片:Web / API / Docs / Mongo / Daemon
#   - "⚙️ 任务运行" 1 个卡片 + 自动清理状态
#   - "▶ 其他资源 (3 项)" 折叠按钮,点开展开 redis/sources/llm

# 2. 跨页刷新验证
#   在监控页底部"已禁用的源"点"重启用"
#   切回数据源页 → 自动刷新(无需点刷新按钮)

# 3. 后端监控接口
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/admin/monitoring | jq .overall, .groups.services | head -30
```

## ⚠️ 已知 / 推迟

| ID | 项 | 备注 |
|---|---|---|
| NEW-13 | web/docs 检查只在端口可达性,没验证页面内容 | 暂用 status 200 即可 |
| NEW-14 | monitoring 默认 5s 轮询,浏览器切到后台会被节流 | OK,不影响 |
| NEW-15 | 资源组展开的"已禁用源"列表和 MonitoringPage 底部列表会重复 | 后续去掉底部列表 |

## 🚀 Day 7 预告
- 推送可靠性 + 死信队列
- /m 移动端订阅管理
- Phase 4 KOL API 调研