# Day 12 · 移动端自适应 (mobile-adapt)

> **分支**:`feat/mobile-adapt`(从 master 切出,准备合并回 master)
> **目标**:同一访问地址,手机 UA 自动渲染移动版,桌面 UA 保留桌面版。
> **完成时间**:Day 12, 2026-07-07

---

## 0. 一句话总结

fastInfo 之前已经有 9 个 `/m/*` 移动端页面,但用户**必须手动输 `/m/`** 才能看到。Day 12 加了 UA 检测 + 路由守卫,**同一地址手机自动跳 `/m/`、桌面自动跳回**;并补齐缺失的 4 个 mobile 页面,达到"手机全功能可用"。

---

## 1. 这次改动

### 1.1 新增文件

| 文件 | 行数 | 作用 |
|---|---|---|
| `frontend/src/lib/device.ts` | ~85 | UA + 触屏 + 屏幕宽度综合检测;支持 localStorage 手动覆盖 |
| `frontend/src/pages/m/MobileHome.vue` | ~330 | mobile 首页(搜索 + Banner + L1/L2 tab + 文章流 + 滚动加载) |
| `frontend/src/pages/m/MobileSearch.vue` | ~190 | mobile 搜索(搜索框 + 历史/热门 + 结果 + 关键词高亮) |
| `frontend/src/pages/m/MobileSettings.vue` | ~210 | mobile 设置(用户卡 + 推送渠道 + 视图模式切换 + 退出) |
| `frontend/src/pages/m/MobileNewSub.vue` | ~370 | mobile 新建/编辑订阅(2 步表单,原生 input 无 naive-ui) |
| `docs/day12-mobile-adapt.md` | - | 本文档 |

### 1.2 修改文件

| 文件 | 改动 |
|---|---|
| `frontend/src/router/index.ts` | 重写:加 mobile 路由 6 条 + Guard 2 做 UA 重定向 |
| `frontend/src/pages/m/MobileLayout.vue` | emoji → lucide 图标;清理 |

### 1.3 路由结构

```
Desktop 路由(原有 13 条 + admin 5 条):
  /                 HomePage
  /hot              HotPage
  /search           SearchPage
  /items/:id        ItemDetailPage
  /login            LoginPage
  /me, /me/inbox,
  /me/subs,
  /me/settings,
  /subs/new,
  /subs/edit/:id,
  /me/push-history,
  /topic/:tid,
  /topics           + admin/* 5 条

Mobile 路由(原 9 → 新增 4 → 现 13 条):
  /m                MobileLayout (壳)
  /m/hot            MobileHot  (原)
  /m/search         MobileSearch   (新)
  /m/items/:id      MobileItem  (原)
  /m/topics         MobileTopicsPage (原)
  /m/topic/:tid     MobileTopicDetail (原)
  /m/me             MobileMe  (原)
  /m/me/inbox       MobileInbox  (原)
  /m/me/subs        MobileSubs  (原)
  /m/me/settings    MobileSettings   (新)
  /m/subs/new       MobileNewSub   (新)
  /m/subs/edit/:id  MobileNewSub   (新,共享同一组件)
  /m/login          MobileLogin  (原)
```

### 1.4 UA 检测策略 (`lib/device.ts`)

```
mobile 判定优先级:
  1. localStorage 手动覆盖(用户在 Settings 选过)
  2. User-Agent 关键词 (mobile|android|iphone|ipod|blackberry|...)
  3. 触屏 + 屏幕宽度 ≤ 768px → mobile (iPad Pro 等)
  4. 否则 → desktop
```

可在 Settings → 显示 → 视图模式 选 "强制手机版" / "强制桌面版",写 localStorage `fastinfo.device-override`,刷新生效。

---

## 2. 路由守卫(Guard 2 · 移动端自适应)

```ts
router.beforeEach((to, _from, next) => {
  // admin / 404 / ?desktop=1 不处理
  if (to.path.startsWith('/admin') || to.name === '404') return next()
  if (to.query.desktop === '1') return next()

  const device = detectDevice()

  // 手机访问 desktop 路径 → 重定向到 /m 对应路径
  if (device === 'mobile' && !to.path.startsWith('/m')) {
    const mobilePath = to.path === '/' ? '/m' : `/m${to.path}`
    return next({ path: mobilePath, query: to.query, hash: to.hash, replace: true })
  }

  // 桌面访问 /m/* → 跳回 desktop 版本
  if (device === 'desktop' && to.path.startsWith('/m')) {
    const desktopPath = to.path.replace(/^\/m/, '') || '/'
    return next({ path: desktopPath, query: to.query, hash: to.hash, replace: true })
  }

  next()
})
```

**`replace: true`**:重定向不进 history,用户按返回键不会卡在重定向中间态。

**`?desktop=1`** 强制桌面:debug 场景,绕过 UA 检测。

---

## 3. 验收清单

### 3.1 路由(curl 已测)

| 路径 | 状态 |
|---|---|
| `/m` | 200 |
| `/m/hot` | 200 |
| `/m/search` | 200 |
| `/m/me/settings` | 200 |
| `/m/subs/new` | 200 |
| `/m/items/xxx` | 200(SPA 通配) |
| `/m/me/inbox` | 200 |

### 3.2 视觉验收(浏览器)

- [ ] iPhone Safari 访问 `http://47.80.13.232/` → 自动跳 `/m` → 看到 mobile 首页
- [ ] Chrome DevTools 切手机模式 → 看到 mobile 布局
- [ ] 桌面 Chrome 访问 `/m` → 自动跳 `/`(验证反向重定向)
- [ ] Settings → 视图模式 → "强制桌面版" → 立即刷新页面看桌面版
- [ ] 所有底 tab(推荐/热门/推送/话题/我的)都能点
- [ ] 搜索框 → 输入 → 跳 `/m/search?q=xxx` → 看到高亮结果
- [ ] 登录态 → 新建订阅 → 2 步走通 → 跳回订阅列表

### 3.3 后端契约(无变化)

`/api/*` 路径不变,前端请求复用,无需改后端。

---

## 4. 已知限制

| 限制 | 说明 | 后续 |
|---|---|---|
| mobile 简版 Settings 仅 5 个渠道 | 后端 `/notifier/channels` 返回的 channel 全显示,无 user 维度过滤 | Day 13 |
| MobileNewSub 简化了 cron 表达式 | 只支持 daily/weekly/interval/realtime,没还原 desktop 的 cron expr 解析 | Day 13+ |
| MobileHome 用 `/api/items` 分页 | desktop 用 `today` + `feed_mode=personalized`,mobile 简单按时间倒序 | Day 13:复用 today API |
| `parseSub` 解析不出所有 desktop 字段 | desktop 用 naive-ui 表单可手动调;mobile 直接采用 parseSub 返回值 | Day 13:对齐 |
| mobile 版 admin 入口未提供 | desktop `/admin/*` 在 mobile 下默认跳 desktop(因为 admin 路径跳过 Guard 2) | Phase 4 |

---

## 5. 设计原则(对齐 P1/P2/P3)

- **P1 不写兼容旧数据**:mobile/desktop 共用同一份 API,同一份 mongo 数据
- **P2 唯一链路**:mobile 路由直接走 desktop 的 API 路径,没有 mobile 专属 API
- **P3 admin 唯一业务用户**:mobile 首页 Banner/文章流对 admin 也一样展示,不区分

---

## 6. 与现有 mobile 页面的关系

| 现有 mobile 页面 | 状态 |
|---|---|
| MobileLayout.vue | ✏️ emoji → lucide,清理 |
| MobileHot.vue | ✅ 不动(Day 10 hotfix 已是高质量实现) |
| MobileLogin.vue | ✅ 不动 |
| MobileMe.vue | ✅ 不动 |
| MobileSubs.vue | ✅ 不动 |
| MobileInbox.vue | ✅ 不动 |
| MobileTopicsPage.vue | ✅ 不动 |
| MobileTopicDetail.vue | ✅ 不动 |
| MobileItem.vue | ✅ 不动 |
| **MobileHome.vue** | 🆕 新增 |
| **MobileSearch.vue** | 🆕 新增 |
| **MobileSettings.vue** | 🆕 新增 |
| **MobileNewSub.vue** | 🆕 新增 |

**总计 13 个 mobile 页面**,覆盖 web 全部核心入口(admin 除外)。

---

## 7. 部署注意事项

- **无需重新构建后端镜像**:改动全在 `frontend/`
- **vite dev 会自动 hot-reload**:改了任意 .vue 文件,所有客户端自动刷新
- **生产部署**:以后 `npm run build` 会出 `frontend/dist/`,nginx web 容器挂载即可;web 镜像之前构建失败是因为 OOM,本次没改 Dockerfile,部署侧问题另议

---

## 8. 测试建议(明早起来)

1. **真机测试**:拿手机扫 `http://47.80.13.232/` 二维码,看 mobile 首页
2. **横竖屏切换**:iPad 横屏 → 仍判定 mobile(max-width 1366 > 768 但触屏优先)
3. **跨设备登出/登录**:手机登录后换桌面,token 复用
4. **手动覆盖**:Settings → "强制桌面版" → 立即生效;清 localStorage 恢复自动

---

## 9. 后续(Day 13+)

- [ ] MobileSettings 拉后端 `/notifier/channels` 动态展示
- [ ] MobileHome 用 desktop 相同的 today API + 个人化排序
- [ ] MobileNewSub 加 track_mode / duration_days 短期话题支持
- [ ] PWA(渐进式 Web App):manifest.json + service worker,加桌面图标 / 离线缓存

---

📌 **本文件必须随 day-end 迭代回填**(AGENTS.md §13)。