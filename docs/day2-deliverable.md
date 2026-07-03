# fastInfo · Day 2 交付
日期:2026-07-02 · 状态:✅ 完成

## 🎯 目标
把 fastInfo 从「能跑 CLI 的 MVP1」升级为「**CLI + FastAPI + 后台 daemon 三端可用**」,FastAPI 化全量接通,带端到端 smoke 回归。

## ✅ N 件事
1. **FastAPI 全量接通**(15 endpoint)
   - 公开:healthz / stats / search / today / hot / items/{id} / items?ids=
   - 鉴权:auth/register / auth/login / auth/me
   - 鉴权写:subs(POST/GET) / subs/{id}/run(POST) / subs/{id}(DELETE) / ingest/run(POST)
2. **JWT 鉴权流跑通**(register → login → Bearer token → 受保护接口)
3. **端到端 smoke 13/13 通过**(`examples/api_e2e_smoke.py`,新增)
4. **AGENTS.md 跟代码同步**(§1/§3/§4/§6/§7/§9/§11/§12/§13 共 9 处)
5. **启动 / 验证 / 重启 流程文档化**

## 🛠️ 改动(表)

| 路径 | 类型 | 说明 |
|---|---|---|
| [src/api/app.py](file:///d:/WORK/trae/fast_info/src/api/app.py) | 修改 | `from api.routes import get_api_router` → `register_routes(app)`(避免两层 include 的 `_IncludedRouter` 嵌套问题) |
| [src/api/routes/__init__.py](file:///d:/WORK/trae/fast_info/src/api/routes/__init__.py) | 重写 | 暴露 `register_routes(app)` 函数,直接 `app.include_router(child, prefix="/api")` 一次性挂载 |
| [examples/api_e2e_smoke.py](file:///d:/WORK/trae/fast_info/examples/api_e2e_smoke.py) | 新增 | 5 阶段 13 步 smoke:健康检查 / 公开读 / 鉴权流 / 订阅写 / ingest(可选) |
| [scripts/api_server.py](file:///d:/WORK/trae/fast_info/scripts/api_server.py) | 已存在 | 启动入口(无需改) |
| [AGENTS.md](file:///d:/WORK/trae/AGENTS.md) | 同步 | §1 现状 / §3 技术栈 / §4 目录 / §6 用法 / §7 模型组 / §9 路线 / §11 问题 / §12 测试 全部对齐代码 |

## 📊 当前数据(2026-07-02 实测)

| 集合 | 条数 |
|---|---|
| `items` | **49** |
| `subscriptions` | **6** |
| `users` | **3**(alice / bob / demo) |
| `subscriptions_delivered` | **10** |
| `fastInfo API paths` | **15**(`/healthz` + `/` + 13 个 `/api/*`) |
| `api_e2e_smoke` | **13/13 ✓** |

## 🧪 验证命令(每个都跑过)

```powershell
# 0) 启动 API
python scripts/api_server.py               # 监听 127.0.0.1:8000

# 1) 端到端 smoke(13/13)
python examples/api_e2e_smoke.py --no-ingest
python examples/api_e2e_smoke.py            # 含真实 ingest(会调 LLM)

# 2) 单 endpoint 验
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/api/stats
curl "http://127.0.0.1:8000/api/search?q=AI"

# 3) 鉴权流
$body = @{username="alice";password="p@ss"} | ConvertTo-Json
$tok  = (curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d $body | ConvertFrom-Json).token
curl http://127.0.0.1:8000/api/auth/me -H "Authorization: Bearer $tok"

# 4) CLI 链路(回归 Day 1)
python fastinfo.py hot --limit 5
python fastinfo.py subs list
python fastinfo.py subs run <id> -v
```

### 实际 smoke 输出

```
============================================================
 fastInfo · API 端到端 smoke  (port=8000)
============================================================

[1] 健康检查
  ✓ /healthz          status=200 body={"status":"ok","mongo_version":"8.2.6"}
  ✓ /                 status=200
  ✓ /api/stats        items=49

[2] 公开读
  ✓ /api/search?q=AI              hits=3
  ✓ /api/today?limit=3            items=3
  ✓ /api/hot?limit=3              items=0
  ✓ /api/items?ids= (空)          items=0
  ✓ /api/items?ids=6a43e1da...    items=1

[3] 鉴权流
  ✓ register(smoke_ewobfx)        status=200
  ✓ login                         status=200
  ✓ /api/auth/me                  user=smoke_ewobfx

[4] 鉴权写
  ✓ POST /api/subs (NL)           status=200
  ✓ GET /api/subs                 total=1

[5] ingest (skipped)

============================================================
 [结果] passed=13  failed=0
============================================================
```

## ⚠️ 已知 / 推迟
- **NEW-1**:MongoDB text 索引对中文检索差("量子位" 0 命中),Day 4 切 BGE-M3
- **NEW-2**:Redis 当前没被代码使用,Day 5+ 真用上时再接
- **NEW-3**:LLM 摘要 prompt 在 3 处各写,Day 3 抽到 `src/llm/prompts.py`
- **NEW-4**:CLI 与 API 鉴权体感割裂,Day 5+ 写统一前端收口
- **TODO-001**:自动化测试未覆盖(auth / subscription / api),Day 3 加 pytest 套件
- **TODO-002**:ingest-daemon 日志无轮转,Day 3
- **TODO-006**:无限频 / IP 黑洞名单,Day 3+

## 🚀 Day 3 预告
- 抓取扩源:RSS(掘金/V2EX/HN/IT 桔子)+ 热搜 API(Tavily/七牛云/微博)
- **`subs_scheduler.py` 真 scheduler daemon**:`next_run_at` 到点自动触发 `run_subscription`,`subs run` 不再依赖人肉
- **systemd unit 文件**:`fastinfo-ingest.service` + `fastinfo-api.service`(精准按 `CommandLine` 拉起,不杀全局)
- **pytest 套件**:`tests/test_auth.py` / `test_subscription.py` / `test_api.py`,跟着 smoke 走
- LLM 摘要 prompt 抽到 `src/llm/prompts.py` 单一来源
