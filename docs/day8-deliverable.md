# fastInfo · Day 8 交付
日期:2026-07-05 · 状态:✅ 完成(用户三件套 + 订阅二次编辑 + 测试纪律)

## 🎯 目标

Day 7 留下来的三件事一起闭环:
1. 顶部「头像 / 昵称 / 套餐」三件套真能改(原来只有 username,头像写死首字母,套餐还错把 username 显示进去)
2. 订阅卡片加「编辑」入口,二改规则不用删了重建
3. **测试账号纪律**:从此所有诊断/回归脚本只用 `tester` 账号,不许在 admin 库里造数据;规范写进 AGENTS.md

## ✅ 3 件事

### 1. 用户三件套 — 头像 / 昵称 / 套餐真值

**后端**:
- `users` 集合加 `nickname / avatar_url` 两个字段(None / "")
- `UserView` / `UpdateUserRequest` schema 加字段
- `PUT /api/settings` + `PATCH /api/auth/me` 都接受这两个字段
- `_enrich_user`(deps) + `_user_to_view`(auth routes)+ `_to_view`(settings routes)三方都填上,确保响应一致
- `_to_view` 视图里 `nickname` 显式归一为字符串(避免 None → JSON null)

**前端**:
- `types/api.ts:User` 加 `nickname? / avatar_url?`
- `MePage.vue` 顶部重渲染:
  - **头像**:`<img v-if avatar_url>` 否则首字母(`nickname → username` 首字符)兜底;`@error` 自动回退
  - **昵称**:`displayName = nickname || username`,首字母同理
  - **套餐**:加 `PLAN_LABELS` 字典映射(free → 免费版 / pro → Pro 版 / team → 团队版 / admin → 管理员),原来的"套餐: admin" 顺手修掉
- 顶部右上角加「✏️ 编辑资料」按钮 → 弹 `NModal`,三个表单字段(nickname / avatar_url / email),保存调 PATCH /api/auth/me,同步 auth store + localStorage

### 2. 订阅二次编辑

**前端**:
- `MePage.vue` 订阅卡片控制按钮加 `✏️ 编辑`,`@click="$router.push('/subs/edit/' + s.id)"`
- 路由 `/subs/edit/:id`(已经在 `router/index.ts:15` 配好,绑到 `NewSubPage.vue`)
- NewSubPage 早就支持编辑模式(`subId = computed(route.params.id)` + `isEdit`),但要把按钮放到那里去后,实际才能用上

**后端**:
- `PATCH /api/subs/{id}` 已经实现,这一刀没新代码
- schema `SubscribePatch` 已支持 title / channels / cron_expr / interval_min / max_items / categories_l1/l2 / keywords / is_active 全字段
- 走一致性过滤(Day 7 加的),编辑时也照样 1 表 → settings 单源 → 多余渠道静默拒

### 3. 测试账号纪律 — `tester` + AGENTS.md P-TEST 节

**新增**: `scripts/init_tester.py`(幂等可重跑)
- 创建账号 `tester` / 密码 `Tester@2026`
- 不存在则创,已存在则跳过,行为稳定
- 跟 Day 6 改的 admin 密码规则一致(都带 @2026 后缀,方便记忆)

**AGENTS.md §2.3 加 P-TEST 节**(用户明确要求),6 条规则:

| 规则 | 关键 |
|---|---|
| P-TEST-1 | 测试账号只用一个 `tester` / `Tester@2026` |
| P-TEST-2 | 必须用 token 走真实 API,**不许绕过鉴权直接 db.insert** |
| P-TEST-3 | **不许在 admin 库里造数据** |
| P-TEST-4 | 诊断脚本 `_<name>.py` 命名 + `mavis-trash` 清理 |
| P-TEST-5 | 脚本最后 `delete_many({"user_id": tester_id})` 兜底 |
| P-TEST-6 | 发现脚本动了 admin 就立刻停改 tester 重跑 |

并把 P3 原文从"admin 就是唯一用户"改成"admin 就是唯一**业务**用户",跟测试账号分开层次。

## 🛠️ 改动(表)

| 文件 | 改动 |
|---|---|
| `src/api/schemas.py` | `UserView` + `UpdateUserRequest` 各 +2 字段(nickname / avatar_url) |
| `src/api/routes/auth.py` | `_user_to_view` + `update_me_endpoint` 加字段 |
| `src/api/routes/settings.py` | `_to_view` + `SettingsUpdate` 加字段,PUT 归一化空字符串 |
| `src/api/deps.py` | `_enrich_user` 加 nickname / avatar_url(供所有 require_user 路由用) |
| `frontend/src/types/api.ts` | `User` 加 `nickname? / avatar_url?` |
| `frontend/src/pages/MePage.vue` | 顶部三件套重渲染 + 「✏️ 编辑资料」Modal + 订阅卡片「✏️」编辑按钮 |
| `scripts/init_tester.py` | **新增**测试账号初始化脚本 |
| `AGENTS.md` | §2.3 加 P-TEST 6 条规则,P3 措辞调整,代码审查检查点加 P-TEST-3 |
| `docs/day8-deliverable.md` | **新增**本文档 |

## 📊 当前数据

- users:`admin`(admin / Admin@2026!)+ **`tester`(tester / Tester@2026)** — 2 条
- tester 验证后清零:subscriptions=0 / delivered=0,完全无污染
- admin 数据维持原状:4 订阅 / 26 delivered(Day 7 回填脚本的 5 + 历史)
- users 集合新增字段:`nickname`(tester 试过值"Test 小明"已清)+ `avatar_url`(tester 试过 dicebear URL 已清);admin 这两个字段为 None

## 🧪 验证命令

```powershell
# 0) 启动后端
python scripts\api_server.py     # 或用 data\_start_api.bat

# 1) 创建测试账号(只第一次)
python scripts\init_tester.py

# 2) 完整回归(全 tester 账号,自动清尾)
python _day7v2_reg.py             # 临时脚本,验证完 mavis-trash 掉
```

**实测**:8 步全过
- login tester(nickname=None,avatar=None,plan=free)✓
- PATCH /auth/me 设昵称 + 头像 + 邮箱 ✓
- GET /auth/me + GET /settings 都回 ✓
- POST /subs 不传 channels → fallback ✓
- PATCH /subs/{id} 改 title + keywords + channels + cron ✓
- 改 nickname 为空字符串 → 前端回退显示 username ✓
- DELETE 自己造的订阅清理 ✓
- 最终 admin 一丝不染 + tester 归零 ✓

## ⚠️ 已知 / 推迟

- **SourcesPage.vue 类型报错**(vue-tsc 严格模式):不是我改动引入的,Day 5 升级时未解。本日 vite build 仍能过(只 ESbuild,跳 TS),功能正常。下次有维护动作时一并修(`columns` 加 `as DataTableColumns<SourceConfigHealth>` cast)
- **Mobile 端 MePage / SubsPage 同步**:Day 8 没动 `/m/me` `MobileSubs.vue`,后续 Day 9 把头像/编辑入口同步过去
- **头像上传**:现在只支持 URL,不支持本地上传。优先级低,后续如要加可走 `POST /api/uploads/avatar` 独立文件

## 🚀 Day 9 预告

按用户当前节奏推:
1. Mobile 端 MePage / MobileSubs 同步 Day 8 的头像 + 编辑入口
2. SourcesPage.vue 类型修复(横切清理)
3. 用户消息里"新增订阅时分类选项漏掉 'AI'",看一下 L2 列表是不是真有
4. 若用户继续提,接着做 P-TEST-2 全链路鉴权演练(把 _verify_clean 之类的脚本再统一规整)

<media src="D:\WORK\trae\fast_info\scripts\init_tester.py" caption="新增测试账号初始化脚本,幂等" />
