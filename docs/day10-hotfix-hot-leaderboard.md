# fastInfo · Day 10 hotfix #2 · 今日排行冲击榜单
日期:2026-07-05 · 状态:✅ 完成

## 🎯 目标

把 `/hot` 从「单条均衡列表」升级为「双榜单 + 高冲击视觉」:
1. **总榜单**:跨类目均衡的 TOP 10,前 3 名加冕(金/银/铜 渐变色 + 大数字水印 + 奖牌)
2. **分榜单**:7 个 L1 类目各自的完整榜单(不受 3 条限制),一次接口拿全
3. **PC + Mobile 双端一致**:复用同一组 API,样式按端型适配

## ✅ 3 件事

### 1. 后端 · `/api/hot` 升级 + 新增 `/api/hot/categories`

**`src/api/routes/hot.py` 重构**:
- 把"每 L1 最多 N 条"的均衡截断抽成参数 `max_per_category`(默认 3)
- 新增 `mode` 参数:
  - `mode=overall`(默认):总榜,跨类均衡
  - `mode=category&category=X`:返回单 L1 完整榜单(不再被 3 条限制)
- 抽出 `_build_hot_pipeline` 公共函数,`hot_endpoint` 从 175 行瘦身到 ~50 行
- 新增 `/api/hot/categories` endpoint:
  - 一次返回 7 个 L1 各自 TOP N
  - 默认 N=10,可通过 `limit` 调(范围 3-20)
  - 响应包含 `category / icon / total_in_window / items`

**核心排序口径**(沿用 v2,不破坏现有行为):
1. 类目内百分位(`cat_percentile` 0~1) — 解决跨类 relevance 量纲不齐
2. 时间衰减 `cat_pct / (age_h + 4)^1.2` — 温和偏向新鲜
3. 总榜模式额外做每类 `max_per_category` 截断 — 防止单类霸榜

### 2. 前端 · HotPage.vue 重做(PC 端)

**`frontend/src/pages/HotPage.vue`**:
- 顶部:`🏆 Trophy` icon 标题 + 时间窗口下拉(`12h/24h/48h/7天`) + 刷新按钮(`RefreshCw` icon,loading 状态 spin)
- **总榜区**:
  - 三列大卡(TOP 1/2/3):金红 / 银灰 / 橙铜 渐变背景,大数字水印(右上角 140px opacity-10),奖牌圆 + 类目 icon + 热度分
  - 4-10 名紧凑列表:左侧序号 + 类目 chip + 来源 + 标题 + 右侧 🔥 热度分
- **分榜汇总区**:
  - 左侧 200px L1 导航栏,active 项青绿渐变 + 数量徽章
  - 右侧该类榜单大卡条 + 8 条完整卡片(数字排名 + L2 类目 + 来源 + 标题 + 摘要预览 + 热度 + 时间)
- 全部 emoji 换成 **lucide-vue-next** icon(`Trophy / RefreshCw / Cpu / Bot / Film / DollarSign / Car / Folder`),跨平台无字体依赖(headless Chrome / Linux / 用户 Windows 都正常)

### 3. 前端 · MobileHot.vue 同步升级(移动端)

**`frontend/src/pages/m/MobileHot.vue`**:
- 顶部紧凑布局(标题 + 时间 select + 刷新按钮)
- **总榜区**:单列卡片,前 3 名顶部带金/银/铜渐变细条,大数字 rank,摘要预览
- **分榜汇总区**:横滑 tab(`<button>` 横排 + `overflow-x-auto` + `sticky`),active 青绿胶囊样式
- 移动端 emoji 也改 lucide icon

## 🛠️ 改动(表)

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/api/routes/hot.py` | 重构 | `_build_hot_pipeline` 抽公共;`mode=category` 支持单类完整榜;新增 `/hot/categories` |
| `frontend/src/pages/HotPage.vue` | 重写 | 总榜单 + 分榜单双区,加 lucide icon 替换 emoji |
| `frontend/src/pages/m/MobileHot.vue` | 重写 | mobile 适配,横滑 tab 切分类 |
| `docs/day10-hotfix-hot-leaderboard.md` | 新增 | 本文档 |
| `AGENTS.md` | 更新 | §1 现状速览 + §9 Day 10 hotfix #2 + §6 endpoint + §11 HF-5/6/7 |

## 📊 当前数据

- `items`:392 条(48h 内 249 条,7 个 L1 全有数据)
- `/api/hot?limit=10` → 总榜 10 条,跨类均衡
- `/api/hot/categories?limit=8` → 7 个类目各 TOP 8
- `/api/hot?mode=category&category=AI&limit=10` → AI 完整榜 10 条(不再被 3 条限制)
- 排序字段 `_hot_score`(百分位 + 时间衰减)在 response 里不直接暴露,前端用 `_rel_norm`(归一化 0-10)显示

## 🧪 验证命令

```powershell
# 1) 后端三端点 smoke
curl "http://127.0.0.1:8000/api/hot?limit=10&hours=48&threshold=0" | python -m json.tool
curl "http://127.0.0.1:8000/api/hot?mode=category&category=AI&limit=10&hours=48" | python -m json.tool
curl "http://127.0.0.1:8000/api/hot/categories?limit=8&hours=48" | python -m json.tool

# 2) 前端 build + 视觉
cd frontend && npx vite build
# 然后访问 http://127.0.0.1:5173/hot  /  /m/hot
```

## ⚠️ 已知 / 推迟

| ID | 内容 | 状态 |
|---|---|---|
| HF-5 | 总榜按"每类 3 条"均衡,某些类目热门内容(>8 条同时高热度)被压到第 4 位 | 已通过 `mode=category` + `/hot/categories` 解决 |
| HF-6 | mobile `/m/*` 路由没包在 `/m` 父路由下,顶 nav 走 PC 版 `DefaultLayout` | 不在 Day 10 hotfix 范围,留作路由重构 |
| HF-7 | 暗色模式未适配(渐变色 + 浅文字对比可能不够) | 后续 |
| NEW-17 | SourcesPage TS 严格性报错 | Day 10+ 主线 |

## 🚀 Day 10+ 预告

- Mobile 路由重构(`/m/*` 嵌套到 `/m` 下,顶 nav 用 MobileLayout)
- SourcesPage.vue `columns` 加类型 cast
- BSON Date 迁移(Day 7 留下的债)
- P-TEST 演练 + LLM prompt 优化(track_entity 剥"动态""最新"等修饰)