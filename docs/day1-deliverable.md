# fastInfo · Day 1 交付

日期:2026-06-30 · 状态:✅ 完成

## 🎯 目标
解决**架构混乱**:之前 `subs run` 自己抓 RSS、自己摘要、写库,慢且重复。
今天把链路解耦:**`ingest` 负责抓+摘要(管理员视角,后台)**;**`subs run` 只读库过滤推送(用户视角,快)**。

## ✅ 三件事

### 1. 架构解耦 — `subs run` 不再 fetch_all
- 之前:`run_subscription` 每次都调用 `fetch_all` 抓网络,慢
- 现在:从 MongoDB `items` 表读最近 N 小时 + 关键词过滤 + 标记 `subscriptions_delivered` 去重
- 性能:从分钟级 → **毫秒级**
- 新增文件函数:`run_subscription`(async)、`run_subscription_sync`(给 CLI)
- 关键 bug 修复:
  - `categories` 用 `$in` 严格匹配不上 LLM 给的细分类 → 改为软 boost 权重
  - keyword 匹配命中 12 条,但 categories 二次过滤全砍 → 改为只 keywords 硬过滤,categories 软提权重
  - cmd_subs_run 用了 `asyncio.run(run_subscription(...))` 而 run_subscription 是 async 包 → 改用 `run_subscription_sync`

### 2. 调度自动化 — `scripts/ingest_daemon.py`
- 独立后台进程,跟 CLI / 订阅 / API 解耦
- 默认每 30 分钟跑一次,日志到 `data/ingest-daemon.log`
- 单次测试:`python scripts/ingest_daemon.py --once`
- 生产部署建议:systemd timer / Windows Task Scheduler 兜底(可选)

### 3. 今日热点 CLI — `fastinfo.py hot`
- 按 `relevance ≥ 0.7` 排序
- 默认看最近 24h,可调 `--hours`、`--threshold`
- 支持 `--category` 二次过滤
- 实测显示 5 条热点(sspai 派评、ithome 比亚迪海豹、汽车票房、谱星航天融资、音频分析)

## 🛠️ 改动

| 文件 | 改动 |
|---|---|
| `src/subscription/__init__.py` | 重写 `run_subscription` 走读库,加 `run_subscription_sync` |
| `src/storage/mongo_writer.py` | 加 `subscriptions_delivered` 表的 2 个索引 |
| `fastinfo.py` | 加 `cmd_hot` 子命令 + 修 `cmd_subs_run` 走 `run_subscription_sync` + 加 `-v` verbose |
| `scripts/ingest_daemon.py` | 新建 — 后台抓取守护进程 |
| `scripts/test_sub_run.py` / `scripts/trace_sub.py` / `scripts/debug_subs.py` / `scripts/reset_delivered.py` | debug + 测试用 |

## 📊 当前数据(MongoDB `fastinfo`)
- `items`: 49 条(抓自 6 个 RSS 源:36kr/ithome/ifanr/sspai/infoq/qbitai)
- `subscriptions`: 2 条(AI资讯速递 / AI资讯日报)
- `subscriptions_delivered`: 10 条(本次推送)
- `users`: 1 个(本地账号)
- 索引齐:`ux_url_hash`、`ix_source`、`ix_cat`、`ix_fetched`、`ux_sub_item`、`ix_user_delivered`、`ux_username`

## 🧪 验证命令
```bash
# 1) 后台抓一次
python scripts/ingest_daemon.py --once

# 2) 今日热点
python fastinfo.py hot --limit 5

# 3) 跑订阅(快,因为从库读)
python fastinfo.py subs run 6a43dca58d9ebd69e9eb6dce -v

# 4) 清 delivered 重跑(测去重)
python scripts/reset_delivered.py
python fastinfo.py subs run 6a43dca58d9ebd69e9eb6dce -v
```

## ⚠️ 已知 / 推迟
- **huxiu RSS 持续 ReadTimeout** — 暂时不被 subs run 命中(订阅里 sources 包含 huxiu 也走不到那条)
- **categories 软匹配** — 临时方案,Day 4 改 LLM prompt 让它输出固定二级标签(["AI","科技","财经","汽车","娱乐","体育","其他"])
- **没有真正的 scheduler daemon** — `ingest_daemon.py` 自己轮询;后续可挂 Task Scheduler / systemd

## 🚀 Day 2 预告
- 把所有 CLI 命令包成 FastAPI(JSON endpoints)
- 接口:`/search /today /hot /subscribe /items /stats`
- 给前端(HTML 单页)+ 移动端复用

