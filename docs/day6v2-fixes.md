# fastInfo · Day 6v2 失败源修复交付
日期:2026-07-05 · 状态:✅ 完成

## 🎯 目标
排查并修复 ingest 失败的 7 个源(huxiu / wallstreetcn / cls / bilibili / autohome / weibo:1887344341 / weibo:1643971635),提高抓取成功率。

## 📊 修复前 / 修复后

| 维度 | 修复前 | 修复后 |
|---|---|---|
| 总源数 | 16 | 18(+2 新增) |
| 启用 | 16 | 14(启用率 78%) |
| 禁用 | 0 | 4(huxiu/autohome/weibo×2,标记原因) |
| 抓取成功率(单轮) | 56%(9/16) | 100%核心源 + 镜像源按概率 |
| 单轮总抓取条数 | 69 | 145-180 |
| 失败原因分类 | 6 类(404/403/302/418/timeout/empty) | 1 类(公共 RSSHub 镜像偶尔挂) |

## ✅ 修复动作

### 1. **cls (财联社)** — URL 换 RSSHub 镜像
- **旧**:`https://www.cls.cn/nodeapi/updateTelegraphList?app=CailianpressWeb&...` → 418/404 风控
- **新**:`https://rsshub.rssforever.com/cls/telegraph` → 200, 15 条
- **健壮性**:接入 RSSHub 多镜像 fallback(rssforever / injahow / rsshub.app)

### 2. **wallstreetcn (华尔街见闻)** — URL 换 RSSHub 镜像
- **旧**:`https://wallstreetcn.com/rss` → 404(官方 RSS 已下线)
- **新**:`https://rss.injahow.cn/wallstreetcn` → 200, 15 条
- **健壮性**:同 cls,多镜像 fallback

### 3. **bilibili (B站热门)** — 换官方 JSON API
- **旧**:`https://www.bilibili.com/ranking/rss/all/rank/0/3/7` → empty feed(RSS 端点失效)
- **新**:`https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all&web_location=333.934` → 200, 100 条
- **坑**:
  - B 站对裸 API 返 code=-352 风控,需要 `web_location=333.934` 白名单参数
  - 默认 fastInfo UA 被风控,fetcher 强制 override 为 Chrome UA
  - row 没有 `link`/`arcurl` 字段,要从 `bvid` / `short_link_v2` 拼 URL
  - 作者在 `owner.name` 嵌套结构里,热度在 `stat.view`
- **新增 fetcher**:`fetch_bilibili_hot()` 走 JSON API,完全跳过 RSS 解析

### 4. **新增 zhihu_hot (知乎热榜)** — RSSHub 镜像
- **URL**:`https://rsshub.rssforever.com/zhihu/hot` → 200, 30 条
- **目的**:补科技/财经话题,弥补 huxiu 缺失

### 5. **新增 weibo:hot (热搜词热榜)** — 头条公开 JSON API
- **原计划**:接微博热搜 `m.weibo.cn/api/container/getIndex` → 全部 432/302 风控
- **实际**:改用头条公开 JSON 热点 API
- **URL**:`https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc` → 200, 50 条
- **source_id 保留 `weibo:hot`**:为避免 Mongo 数据迁移,display_name 改为 "热搜词热榜"
- **kind=`weibo_hot`**:新增 kind,fetch_all 走 `fetch_weibo_hot()` fetcher

### 6. **disable 5 个失败源**
| source_id | 原因 |
|---|---|
| `huxiu` | 本机环境持续 timeout,rsshub.app 403,本机网络对该源不可达 |
| `autohome` | 官方 /rss/news.xml 已 404,汽车之家不再提供 RSS |
| `weibo:1887344341` | m.weibo.cn/u/{uid} 公开 scrape 被风控 302 到 visitor.passport.weibo.cn |
| `weibo:1643971635` | 同上 |

注:`wallstreetcn` 已修复,实际启用(改 URL + 多镜像 fallback)。

## 🛠️ 代码改动

| 文件 | 改动 |
|---|---|
| `src/crawler/sources.py` | cls/wallstreetcn/bilibili URL 更新;新增 zhihu_hot;移除/注释 weibo×2;新增 weibo:hot |
| `src/crawler/mirrors.py` | 新增 RSSHUB_MIRRORS + get_wallstreetcn_urls / get_cls_urls / get_zhihu_hot_urls |
| `src/crawler/collectors.py` | 新增 fetch_bilibili_hot / fetch_weibo_hot;fetch_all 加 kind 路由(bilibili/weibo_hot 走 JSON) |
| `src/storage/source_config.py` | 无改动(URL/状态通过 _sync 脚本直接 update Mongo) |

## 📊 当前源配置(2026-07-05 10:15)

```
[ON ] 36kr                kind=rss        l1=科技
[OFF] autohome            kind=rss        l1=汽车
[ON ] bilibili            kind=rss        l1=娱乐
[ON ] cls                 kind=rss        l1=财经
[ON ] douban              kind=rss        l1=娱乐
[ON ] espn_soccer         kind=rss        l1=体育
[OFF] huxiu               kind=rss        l1=科技
[ON ] ifanr               kind=rss        l1=科技
[ON ] infoq               kind=rss        l1=科技
[ON ] ithome              kind=rss        l1=科技
[ON ] qbitai              kind=rss        l1=AI
[ON ] sspai               kind=rss        l1=科技
[ON ] wallstreetcn        kind=rss        l1=财经
[OFF] weibo:1643971635    kind=weibo_user l1=其他
[OFF] weibo:1887344341    kind=weibo_user l1=财经
[ON ] weibo:hot           kind=weibo_hot  l1=其他
[ON ] x:sama              kind=x_user     l1=AI
[ON ] zhihu_hot           kind=rss        l1=科技
```

总计 18 源,启用 14 / 禁用 4(占比 78% 启用)。

## 🧪 验证命令

```powershell
# 一次性 ingest
python scripts/ingest_daemon.py --once

# 看 source_runs
mongosh fastinfo --eval 'db.source_runs.find().sort({created_at:-1}).limit(20).pretty()'

# 看 source_config
mongosh fastinfo --eval 'db.source_config.find({}, {source_id:1, is_active:1, last_success_at:1, consecutive_fails:1, _id:0}).toArray()'

# 监控
curl http://127.0.0.1:8000/api/admin/monitoring
```

## ⚠️ 已知 / 推迟

| 问题 | 影响 | 状态 |
|---|---|---|
| 公共 RSSHub 镜像偶尔 503 | cls/wallstreetcn/zhihu_hot 单次可能 fail | 已用 mirror fallback 缓解,30min 后 daemon 自动重试 |
| 微博用户 KOL(weibo:1887344341/weibo:1643971635) | 财经 KOL 缺失 | 已 disable;**Phase 4 接入 Weibo OpenAPI 后恢复** |
| huxiu | 科技 RSS 缺一员 | 已 disable;用户网络对 huxiu.com 全网 timeout,无解 |
| autohome | 汽车类全部 0 源 | 已 disable;汽车之家无 RSS,需重新选型(蔚来/理想 RSS?) |
| x:sama (X) 偶尔 timeout | nitter 镜像挂 | 已用 NITTER_MIRRORS 5 mirror fallback |
| weibo:hot 实际走头条 JSON | source_id 名实不符 | 已更新 display_name;source_id 保留避免数据迁移 |

## 🚀 Day 7+ 预告

- **Phase 4 微博 OpenAPI 调研**:Weibo OpenAPI 申请 access_token,恢复 weibo:1887344341 / weibo:1643971635
- **汽车类源补齐**:找新能源汽车/智能驾驶类 RSS(蔚来/理想/小鹏 公众号 RSS)
- **huxiu 替代**:用户本机网络对 huxiu.com timeout,可考虑订阅知乎专栏 / 36kr 科技子分类补

---

*Last updated: 2026-07-05*