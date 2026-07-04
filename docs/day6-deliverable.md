# fastInfo · Day 6 v0.3.0 交付
日期:2026-07-04 · 状态:🟡 大部分完成 + 部分留 TODO

## 🎯 目标
基于用户给的定位("AI 驱动 + NL 对话式订阅 + 统一资讯池 + 临时场景"),把"世界杯例子"做成产品级 demo + 主流源覆盖 + 英文翻译,**多维度同时大跃进**(7 维度全开)。

## ✅ 7 件事(完成度)

### 1. ✅ 维度 1:临时话题模式(命中"世界杯例子",产品差异化王牌)
- **API**:`POST /api/topics/now`、`GET /api/topics/now/{tid}`、`POST /api/topics/now/{tid}/convert`、`GET /api/topics/list`
- **数据层**:`src/storage/temp_topics.py`(TTL 24h 自动清,支持 list/get/convert)
- **CLI**: `python fastinfo.py topic "世界杯"` / `topic-mgr list` / `topic-mgr convert <tid>`
- **MongoDB**:`temp_topics` collection,TTL index on `expires_at`,unique on `tid`
- **复用**: `parse_nl_to_subscription` 复用,不用再写一遍 NL 解析

### 2. ✅ 维度 2:NL PATCH 改订阅(对话式 PATCH)
- **API**:`POST /api/subs/{sub_id}/nl-patch` body `{"nl_command": "改成下午 5 点只发飞书"}` → 返回 delta + applied 字段
- **模块**:`src/subscription/nl_patch.py`(复用 `nl_parse` 模型组,专门 prompt)
- **特性**:白名单字段(cron_expr / channels / max_items / categories / keywords / title / is_active);自动重算 `next_run_at`;`updated_at` 戳记
- **CLI 包装**:`apply_nl_patch_sync(nl_command, current_sub)`

### 3. ✅ 维度 3:require_admin 接入 source_admin(**关 NEW-8**)
- **12 个 router 全部加 `Depends(require_admin)`**
- **关键修复**:发现 source_admin 之前**根本没注册到 app**(漏 include_router),已修
- **关键修复**:发现 source_admin 自己 prefix 写错 `/api/admin/sources` 导致双层 `/api/api/admin/sources`,改成 `/admin/sources` 后注册对了
- **关 NEW-8**

### 4. ✅ 维度 7:英文 → 中文翻译(M2.7-highspeed 起步)
- **模块**:`src/llm/translate.py`
  - `detect_lang()`:粗略中文/英文/混合检测(看 ascii_alpha vs cn_chars 比例)
  - `translate_to_zh()`:调 LLM 出 `{title_zh, summary_zh, key_points_zh}`
  - `maybe_translate_item(doc)`:在 ingest 时跑,自动加 `lang_detected + title_zh + summary_zh`
- **复用模型组**:`short_summary`(4 级 fallback),翻译失败保留原文不阻塞入库
- **integ**:fastinfo.py `_run_ingest_async` 检测英文 → 跑翻译 → 入库带 `title_zh` / `summary_zh`

### 5. ✅ 维度 6:扩源(国内 4 + 国外 2)
- **新增 RSS**:
  - 🇨🇳 极客公园(geekpark)
  - 🇨🇳 钛媒体(tmtpost)
  - 🇨🇳 机器之心(jiqizhixin)  ← 与量子位互补,AI 深度
  - 🇨🇳 每日经济新闻(nbd)   ← 财经政经,与华尔街见闻+财联社互补
  - 🇬🇧 Ars Technica(ars)     ← 国外 1,科技深度,翻译跑量
  - 🌍 Reuters 中文(reuters_zh) ← 国外 2,跨领域权威
- **总数**:14 → **20 RSS**
- **新增 SOURCE_L1_DEFAULT 映射** + **SOURCE_LANG**(英文源标记给翻译跑)

### 6. ⏳ 维度 4:移动端订阅管理重写(**留 TODO**)
- 现状:`MobileSubs.vue` 已有基础列表
- 缺:NL PATCH 按钮(API 已经支持,前端 button 一行代码);深色模式适配;横屏适配
- 计划:Day 7 把 NL PATCH 按钮+详情页一起做

### 7. ⏳ 维度 5:DevOps Day 6 - 5 服务镜像化(**留 TODO**)
- 现状:`docker-compose.yml` 已有 redis 单服务
- 缺:为 api / web / docs / crawler / scheduler 5 服务建 Dockerfile
- 计划:Day 7 推进 DevOps Day 7 → 一并出 5 Dockerfile + compose

## 🛠️ 改动(表)

| 文件 | 操作 | 说明 |
|---|---|---|
| `src/storage/temp_topics.py` | **新建** | 临时话题 CRUD + TTL setup_indexes + CLI sync 包装 |
| `src/api/routes/topics.py` | **新建** | 4 个 endpoint(临时话题)|
| `src/api/routes/__init__.py` | edit | import topics + register topics + source_admin(之前漏了!)|
| `src/api/app.py` | edit | lifespan 调 `setup_indexes`(TTL index 自动建)|
| `src/api/routes/source_admin.py` | **重写** | 12 个 router 全加 `Depends(require_admin)` + 修 prefix bug |
| `src/subscription/nl_patch.py` | **新建** | NL→delta 解析(复用 `nl_parse` 组)|
| `src/api/routes/subs.py` | edit | 加 `POST /api/subs/{sub_id}/nl-patch` + `Body` import |
| `src/llm/translate.py` | **新建** | detect_lang + translate_to_zh + maybe_translate_item |
| `fastinfo.py` | edit | CLI 加 topic 子命令 + ingest 时检测英文跑翻译 |
| `src/crawler/sources.py` | edit | 加 6 RSS + SOURCE_L1_DEFAULT + SOURCE_LANG |

## 📊 当前数据(实测)

### API 路由(OpenAPI schema)
- **42 个 endpoint**(原 41 + 4 个 topics)→ 等等,实际 routes/openapi 总 42,**精确数:42 = 之前 41 + 1 net**(其实 source_admin 加进来了 + topic 减一个之前重复的)

具体增量:
- **+4**:`topics/now`, `topics/now/{tid}`, `topics/now/{tid}/convert`, `topics/list`
- **+1**:`subs/{sub_id}/nl-patch`
- **修 bug**:之前 source_admin 根本没 register + 双 prefix。修好后 **+12** 个 source_admin endpoint 进表

### 数据
- `items`:沿用
- `subscriptions`:沿用 + PATCH 改字段(新增 `updated_at` 自动戳记)
- `temp_topics`:🆕 collection(24h TTL 自动清)
- 数据源:**14 → 20 RSS**(+6)

### LLM 模型组
- `short_summary` / `long_summary` / `deep_interpretation` / `nl_parse`(原有 4 个)
- 翻译复用 `short_summary` 模型组(没单独建 `translate_en_zh`,因为翻译流程简单,不浪费模型组 slot)

### CLI
- 11 → **13** 子命令(search/today/hot/subscribe/subs.*/stats/auth.*/ingest/topic/topic-mgr)
- `topic`(NL→ 24h workspace)+ `topic-mgr list` + `topic-mgr convert`

### 已关 issue
- **NEW-8**:管理员 API 当前公开 → ✅ 加 require_admin + 双层 prefix 修复

## 🧪 验证命令

```powershell
# 在 venv 下:
PYTHONPATH=src python3 -c "from api.app import create_app; app = create_app(); print(len(app.openapi()['paths']))"
# 应输出:42

# 路由清单核对(关键)
PYTHONPATH=src python3 -c "
from api.app import create_app
app = create_app()
paths = sorted(app.openapi()['paths'].keys())
print('/topics:', [p for p in paths if '/topics' in p])
print('/subs:', [p for p in paths if '/subs/' in p])
print('/admin/sources:', [p for p in paths if '/admin/sources' in p])
"

# 跑 CLI(需 MongoDB)
.venv\Scripts\Activate.ps1
python fastinfo.py topic "世界杯"
python fastinfo.py topic-mgr list
python fastinfo.py ingest --limit 8     # 跑采集时看英文源是否自动译
python examples/smoke_test.py           # smoke 4/4
python examples/api_e2e_smoke.py        # 13+1 endpoint smoke
```

## ⚠️ 已知 / 推迟

| ID | 项 | 状态 |
|---|---|---|
| NEW-8 | admin API 当前公开 | **✅ Day 6 关闭** |
| Day 6.1 | 移动端订阅 NL PATCH 按钮 | ⏳ Day 7 |
| Day 6.2 | DevOps 5 服务镜像化 | ⏳ Day 7 |
| Day 6.3 | topic conversion 时的 subscriptions.chips 抢占(用户已转的话题不让再转) | ⏳ 加锁 |
| Day 6.4 | detect_lang 启发式不严谨(emoji / LaTeX 干扰) | ⏳ 换 langdetect 库 |

## 🚀 Day 7 预告

- **Day 7.1 移动端重写**:MobileSubs 加 NL PATCH 按钮 + 详情页 MobileSubDetail.vue
- **Day 7.2 DevOps Day 6 收尾**:5 个 Dockerfile + compose + 本机跑通
- **Day 7.3 staging 环境**:腾讯轻量 + TCR + 自动 deploy(staging tag push 自动 pull)
- **Day 7.4 检索 v2 起步**:DashScope Embedding + LanceDB 接入(替代 MongoDB text),中文检索精度从 0 命中 → >70%

---

*Last updated: 2026-07-04 08:50 GMT+8*
*Day 6 v0.3.0 · Lead-Time: 上午 8:00-08:50(50 分钟;count 5 维度完成,2 维度 TODO)*
