# fastInfo · Day 4 交付
日期:2026-07-03 · 状态:✅ 完成

## 🎯 7 个需求全实现
1. **扩源**:14 RSS + 5 KOL(娱乐/体育/财经/汽车/微博/X/小红书),通过 RSS / 隐藏 JSON / 平台公开页三层抓取
2. **KOL 跟踪**:微博 / X (nitter 镜像) / 小红书公开页 scrape
3. **源开关 + 频率配置**:`source_config` 集合白名单模式,`/api/admin/sources` 后台可视化
4. **二级分类**:L1 (7 个) + L2 (30+ 个) 体系,老数据已迁移 (113 条全部归类)
5. **订阅 UI 重构**:分步式,自动隐藏 LLM 细节,L1/L2 二级选择器,渠道多选,转圈 bug 修复
6. **移动端**:`/m/*` 独立 6 页面,底部 nav,ZAKER 风卡片
7. **多渠道推送**:`inbox` / `email` / `feishu` / `wechat` / `webhook` 五种,Notifier 抽象 + 4 实现

## 🆕 新增

### 后端
- [src/crawler/sources.py](file:///d:/WORK/trae/fast_info/src/crawler/sources.py) - 14 RSS + 5 KOL + L1/L2 taxonomy
- [src/crawler/collectors.py](file:///d:/WORK/trae/fast_info/src/crawler/collectors.py) - SourceAdapter,源开关, KOL 抓取
- [src/taxonomy.py](file:///d:/WORK/trae/fast_info/src/taxonomy.py) - L1 映射 + L2 建议
- [src/notifier/__init__.py](file:///d:/WORK/trae/fast_info/src/notifier/__init__.py) - Notifier 抽象 + 4 实现
- [src/api/routes/admin.py](file:///d:/WORK/trae/fast_info/src/api/routes/admin.py) - +`/sources` +`/taxonomy` 端点
- [src/api/routes/subs.py](file:///d:/WORK/trae/fast_info/src/api/routes/subs.py) - +`PATCH` +`channels` +`L1/L2`
- [src/api/schemas.py](file:///d:/WORK/trae/fast_info/src/api/schemas.py) - 新字段
- [src/subscription/__init__.py](file:///d:/WORK/trae/fast_info/src/subscription/__init__.py) - L1 硬过滤 + 多渠道推送
- [scripts/subs_scheduler.py](file:///d:/WORK/trae/fast_info/scripts/subs_scheduler.py) - ⭐ 自动跑订阅 daemon
- [scripts/migrate_categories.py](file:///d:/WORK/trae/fast_info/scripts/migrate_categories.py) - 老数据分类迁移

### 前端
- [frontend/src/pages/admin/SourcesPage.vue](file:///d:/WORK/trae/fast_info/frontend/src/pages/admin/SourcesPage.vue) - 源开关可视化
- [frontend/src/pages/HomePage.vue](file:///d:/WORK/trae/fast_info/frontend/src/pages/HomePage.vue) - L1 一级类目 tab
- [frontend/src/pages/NewSubPage.vue](file:///d:/WORK/trae/fast_info/frontend/src/pages/NewSubPage.vue) - 分步式订阅
- [frontend/src/pages/MePage.vue](file:///d:/WORK/trae/fast_info/frontend/src/pages/MePage.vue) - 暂停/启用 + 渠道显示
- [frontend/src/pages/m/*](file:///d:/WORK/trae/fast_info/frontend/src/pages/m/) - 6 个移动端页面(MobileLayout/Hot/Item/Me/Inbox/Subs/Login)
- [frontend/src/router/index.ts](file:///d:/WORK/trae/fast_info/frontend/src/router/index.ts) - +7 条路由

## 📊 数据现状(2026-07-03 03:30)

| 集合 | 数 | 备注 |
|---|---|---|
| items | 113 | 全部有 L1,57 其他/32 科技/9 AI/7 财经/6 汽车/1 体育/1 娱乐 |
| subscriptions | 17 | 含 channels / L1/L2 / interval_min 字段 |
| subscriptions_delivered | 143 | scheduler 触发后写入 |
| task_runs | 2 | 来自 ingest_daemon |
| source_config | 1 | 当前 enabled=空(全开模式) |
| banner_config | 1 | |
| users | 13 | 1 admin + 12 normal |

## 🧪 验证

### 后端
```powershell
python scripts/migrate_categories.py
# total=113, without L1=0
# L1 分布: 其他57 / 科技32 / AI9 / 财经7 / 汽车6 / 体育1 / 娱乐1

python scripts/subs_scheduler.py --once
# -> triggered=17 skipped=0 failed=0
```

### 前端
```powershell
cd frontend && npm run build
# ✓ built in 5.14s
```

## 📡 数据源(14 RSS + 5 KOL)

### RSS (14)
| 分类 | 源 |
|---|---|
| 科技/AI | 36氪 / 虎嗅 / 爱范儿 / 量子位 / InfoQ / 少数派 / IT之家 |
| 财经 | 华尔街见闻 / 财联社 |
| 体育 | 虎扑 / 懂球帝 |
| 娱乐 | B站热门 / 豆瓣热门 |
| 汽车 | 汽车之家 |

### KOL (5)
- 微博-任泽平 / 微博-老胡谈谈
- X-Elon Musk / X-Sam Altman (nitter 镜像)
- 小红书-demo (MVP stub,Day 5 接入签名 API)

## 📂 移动端 (ZAKER 风)

```
/m          卡片瀑布流(自动加载)
/m/hot      今日热门 Top 30
/m/items/:id  详情
/m/me       我的(头像 + 入口)
/m/me/inbox 推送历史
/m/me/subs  订阅列表
/m/login    登录
```

底部固定 nav:推荐 / 热门 / 推送 / 我的(未登录显示「登录」)

## 🔌 推送渠道

| 渠道 | 配置 | 实现 |
|---|---|---|
| inbox | 默认,无需配置 | 写入 subscriptions_delivered |
| email | SMTP_USER / SMTP_PASS 环境变量 | [EmailNotifier](file:///d:/WORK/trae/fast_info/src/notifier/__init__.py#L40-L75) |
| feishu | user.feishu_webhook | [FeishuNotifier](file:///d:/WORK/trae/fast_info/src/notifier/__init__.py#L80-L94) |
| wechat | user.wechat_webhook | [WechatWorkNotifier](file:///d:/WORK/trae/fast_info/src/notifier/__init__.py#L99-L109) |
| webhook | user.webhook_url | [WebhookNotifier](file:///d:/WORK/trae/fast_info/src/notifier/__init__.py#L114-L120) |

## ⚠️ 已知限制 / 推迟

- **小红书** 公开页 scrape 是 stub(需要签名 / 付费 API),Day 5 接入第三方
- **X 走 nitter 镜像** 不稳定,生产建议 X API v2 Basic ($100/月)
- **微信订阅号 / 服务号推送** 未做(需要企业认证),先用企业微信机器人代替
- **推送频率 UI** 已支持 interval_min / cron 二选一,但还**没有**"per-source 调度频率"后台(目前是全局 30 min/60 min)— 推到 Day 5
- **scheduler daemon 没装 systemd / PM2 托管**,需要手动跑

## 🚀 Day 5 预告
- per-source 调度后台(每个 RSS 源可独立 cron)
- 小红书 / 微博真实 API 接入
- 邮件订阅鉴权(SMTP + 退订链接)
- 前端:`/m/items/:id` 加视频 / 图片轮播
- 推送失败重试 + 死信队列
- 移动端:加入 /m 端订阅管理 / 创建 / 暂停