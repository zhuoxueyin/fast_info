# fastInfo · Day 11 交付
日期:2026-07-05 · 状态:✅ 完成(失败源修复 + 同类替换)

## 🎯 目标
把 11:57 那次 ingest 的 3 个失败源(`huxiu` 403/timeout · `cls` 403 · `autohome` 404)处理好 —
能解就修,不能解就同类替换。

## ✅ N 件事

### 1. cls 财联社 — 修复(主页 SSR JSON 抓取)
- **根因**:`rsshub.app` / `rssforever` / `injahow` 三个公共 RSSHub 镜像对 `cls/telegraph` 路径
  全 503/404,官方 `nodeapi` 接口早 418,所有公开 RSS 都失效。
- **解法**:cls.cn 主页是 Next.js SSR,`window.__INITIAL_STATE__` 里 SSR 内嵌了 `hotArticleData` JSON,
  含 `id / title / brief / ctime / readNum / author` 完整字段。
- **新增 fetcher**:`src/crawler/collectors.py::fetch_cls_home`,正则抠 `hotArticleData` 数组
  直接 `json.loads(strict=False)` 解析(strict=False 是为了容 brief 字段里偶尔的真换行符)。
- **路由**:`fetch_all` 里 cls 不再走 RSSHub 镜像 fallback,直接走 `fetch_cls_home`。
- **db**:source_config.cls 的 `url` 同步到 `https://www.cls.cn/`,`consecutive_fails` 重置为 0。

### 2. huxiu 虎嗅 — 替换为 leiphone 雷锋网
- **根因**:huxiu 官方 RSS `https://www.huxiu.com/rss/0.xml` 本机环境持续 timeout,三个公共 RSSHub 镜像
  对 `/huxiu` 路径全 404,无法稳定抓取。
- **同类替换**:leiphone 雷锋网(`https://www.leiphone.com/feed`)— 科技/AI 重叠,实测 RSS 200 +
  600KB+ feed,内容专业度匹配。
- **改动**:
  - `src/crawler/sources.py` 加 `leiphone` 注册项(L1=AI,与 qbitai/x:sama 同类)
  - `SOURCE_L1_DEFAULT` 加 `leiphone: AI`
  - `seed_from_registry()` 自动写 source_config doc
  - `source_config.huxiu` 标 `is_active=False` + 新 disabled_reason(标日期 + 诊断 + 替换说明)

### 3. autohome 汽车之家 — disable + 标记
- **根因**:`https://www.autohome.com.cn/rss/news.xml` 官方 RSS 已 404(下线);
  m 站 `m.autohome.com.cn/news/` 是 SPA,内容由 JS 渲染,SSR HTML 不含 article 链接;
  `ashx/autoajax.ashx` 等公开 API 404。
- **处理**:`is_active=False` + 标 disabled_reason,记录「汽车类低频需求,Phase 4 再评估」。
- **替换**:暂不替换(汽车类目前不是 admin 关注重点),等 Phase 4 接 RSSHub 时补 `autohome`
  route 或评估第三方汽车源。

### 4. 顺手修 `upsert_item_async` _id immutable bug
- **症状**:任何重复 url_hash 走 update 时报 `WriteError: Plan executor error during update ::
  caused by :: Performing an update on the path '_id' would modify the immutable field '_id'`。
- **根因**:pymongo `insert_one` 失败时 mutate 原 dict 加 `_id` 字段;catch 块里直接用
  `update_one({"url_hash":...}, {"$set": item})` 把 mutated dict 整个 set,触发 immutable field 错误。
- **修复**:`src/storage/mongo_writer.py::upsert_item_async` update 前先 pop `_id`。
- **影响范围**:实际生产中,任何源第二次抓相同 url 都会触发(只是以前每天新内容 url_hash 不重,
  没注意到)。修复后 update 路径完全 OK,生产跑 `run_subscription` / `ingest_daemon` 不再假死。

## 🛠️ 改动(表)

| 文件 | 改动 | 行数变化 |
|---|---|---|
| `src/crawler/sources.py` | 加 `leiphone` 注册项 + L1 映射;cls 注释更新 | +5/-1 |
| `src/crawler/collectors.py` | 新增 `fetch_cls_home` fetcher;`fetch_all` 把 cls 路由到新 fetcher | +95/-3 |
| `src/storage/mongo_writer.py` | 修 `upsert_item_async` _id immutable bug | +3/-1 |
| `scripts/` (临时诊断) | `_diag_verify_sources.py` + `_diag_verify_upsert.py`(用完 mavis-trash 掉) | - |
| `src/source_config` (db) | 新增 leiphone;huxiu/autohome 标 disabled + reason;cls url/urls 同步 | - |

## 📊 当前数据

```
source_config 当前状态(2026-07-05 12:13):

✅ 启用的源 (active=True):
  36kr              (科技)  https://36kr.com/feed
  bilibili          (娱乐)  B 站排行 JSON
  cls               (财经)  https://www.cls.cn/  ← 改为主页 JSON 抓取
  douban            (娱乐)  https://www.douban.com/feed/review/movie
  espn_soccer       (体育)  ESPN RSS
  ifanr             (科技)  爱范儿 RSS
  infoq             (科技)  InfoQ RSS
  ithome            (科技)  IT 之家 RSS
  leiphone          (AI  )  https://www.leiphone.com/feed  ← 新增
  qbitai            (AI  )  量子位 RSS
  sspai             (科技)  少数派 RSS
  wallstreetcn      (财经)  RSSHub 多镜像
  weibo:hot         (其他)  头条热榜 JSON
  weibo:1887344341  (财经)  微博 KOL(disabled scrape,等 OpenAPI)
  weibo:1643971635  (其他)  微博 KOL(disabled scrape,等 OpenAPI)
  x:sama            (AI  )  X KOL via nitter mirrors
  zhihu_hot         (科技)  知乎热榜 via RSSHub 多镜像

❌ disabled 的源 (active=False):
  huxiu      2026-07-05 官方 RSS timeout + 公共 RSSHub 全死 → 替换为 leiphone
  autohome   2026-07-05 官方 RSS 404 + 官网 SPA + API 封闭 → Phase 4 再评估

📰 items 新增:
  cls (3 条 stub):
    - 多股应声涨停!A股中报行情开启,12家上市公司净利最高同比预增超 150%
    - 加码玻璃基板!三星电机、住友化工合资公司落地 预计2027年下半年投产
    - 【早报】证监会征求意见,事关上市公司再融资;A股存储龙头半年报净利最高预增740倍
  leiphone (3 条 stub):
    - 生数科技发布 Vidu S1,推动视频生成迈向"实时交互"新时代
    - 谷歌为什么做不好「AI 编程」?
    - 独家丨猛士下款新车将进军泛越野,预计售价 20-25 万
```

## 🧪 验证命令

```powershell
# 1. 看 source_config 当前态
.\scripts\activate.ps1
python -c "import sys; sys.path.insert(0,'src'); from storage.source_config import list_sources; [print(f'{d[\"source_id\"]:30} active={d[\"is_active\"]}') for d in list_sources()]"

# 2. 验证 cls fetcher
$env:HTTP_PROXY=''; $env:HTTPS_PROXY=''
python -c "import sys,asyncio; sys.path.insert(0,'src'); from crawler.collectors import fetch_cls_home; import httpx; from crawler.rss_collector import USER_AGENT; print(len(asyncio.run(fetch_cls_home(httpx.AsyncClient(headers={'User-Agent':USER_AGENT}, timeout=20.0), 'cls', 'cls', 'https://www.cls.cn/', limit=5))))"

# 3. 验证 leiphone fetcher
python -c "import sys,asyncio; sys.path.insert(0,'src'); from crawler.collectors import fetch_rss_with_fallback; import httpx; from crawler.rss_collector import USER_AGENT; items=asyncio.run(fetch_rss_with_fallback(httpx.AsyncClient(headers={'User-Agent':USER_AGENT}, timeout=20.0), 'leiphone', '雷锋网', ['https://www.leiphone.com/feed'], limit=5)); print(f'leiphone {len(items)} 条'); [print(f'  - {it.title[:50]}') for it in items]"

# 4. 全源 ingest(legacy 模式,会触发 LLM 摘要)
python scripts/ingest_daemon.py --legacy

# 5. 跑 ingest daemon (默认 scheduler,只跑 due)
python scripts/ingest_daemon.py --once
```

## ⚠️ 已知 / 推迟

| ID | 项 | 状态 |
|---|---|---|
| NEW-20 | **car.autohome.com.cn/rss 备用链接 / 汽车 RSS 第三方源评估**(易车、盖世、汽车之家新能源板块等) | 推迟 — admin 不强需求,Phase 4 评估 |
| NEW-21 | **cls 主页面页结构变化风险**(Next.js 升级改 schema,正则失效) | 接受 — 抓取 fail 会自动计入 source_runs.consecutive_fails,5 次自动 disable |
| NEW-22 | **`feishu` / `wechat` / `webhook` 推送 4 个 channel 的 `_post_webhook` 等还有 53 处 print 含 ✗/✓ 未统一改 logging**(Day 10 hotfix 修了 notifier GBK 但 CLI / smoke / admin_sources 还有遗留) | 推迟 — 用户手动跑这些脚本时控制台才会喷,生产 daemon 不受影响 |
| NEW-23 | **公共 RSSHub 镜像 2026-07-05 大面积死**(rsshub.app/injahow/rssforever 大量 path 404) | 长期观察 — 自建 RSSHub instance 或转投付费 / 私有源是 Phase 4 工作 |

## 🚀 Day 12 预告

- Day 12 主线:把 NEW-22 的 53 处 print 改 logging + ASCII 收尾(HF-1 清理)
- 可选:Day 9+ 留下的 BSÓN Date 迁移(HF-2) / SourcesPage TS 修复(NEW-17)
- 可选:评估 P-TEST-6 admin 跑过的脚本改用 tester 重跑(纯 hygiene,无功能影响)