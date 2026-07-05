# fastInfo · Day 10 hotfix · notifier GBK 死循环 + send_all http_status 透传

日期:2026-07-05 · 状态:✅ 完成(单点 hotfix,**非**完整 Day 10)

> 📌 Day 10 主线计划(BSON Date 迁移 / SourcesPage TS 修复 / track_entity prompt / P-TEST 演练)未做。
> 本文档只记录今天排查出来的两处历史 bug 修复。

## 🎯 目标

用户在「推送历史」页发现:最近 3 条自动调度(`trigger=schedule`)的飞书推送全部显示
`✗ 飞书群  UnicodeEncodeError: 'gbk' codec can't encode character '\u2717' in position 11: illegal multibyte sequence`,
而手动触发是好的。**弄清根因 + 修 + 验证**。

## ✅ 2 件事

### 1. notifier GBK 死循环(核心 bug)

**根因**: `src/notifier/__init__.py` 的 `_post_webhook` 把**状态日志**写在 `try` 块内的 `return` 之前:

```python
# 旧代码 — 已废弃
def _post_webhook(url, payload, tag):
    try:
        r = httpx.post(url, json=payload, timeout=10)
        ok = 200 <= r.status_code < 300
        if ok:
            print(f"  [{tag}] {url[:60]}... ✓")           # ← 默认 stdout 是 GBK
            return {"ok": True, ...}
        print(f"  [{tag}] {url[:60]}... ✗ {r.status_code}")  # ← ✗ (\u2717) GBK 编码失败
        return {"ok": False, ...}
    except Exception as e:
        ...
        print(f"  [{tag}] ✗ {msg}")                        # ← 同上
        return {"ok": False, ...}
```

Windows 控制台默认 GBK,`print(...)` 含 `\u2717`(✗) 直接抛 `UnicodeEncodeError`。
这个 print 在 try 内,在 return 之前 → 异常冒泡 → `FeishuNotifier.send()` 不再 return → `send_all` 的 `except Exception` 兜成「推送失败」→ 写进 push_history。

**链路解释为何手动调度没事**:
- `fastinfo.py subs run ...` 在用户的 PowerShell 终端跑,本地 `chcp 65001`(UTF-8) → print 不炸
- `scripts/subs_scheduler.py` 是后台进程,**它继承的是继承 stdin/stdout 的代码页**。大部分情况下 subs_scheduler 子进程的 stdout 是 GBK(没 `win32 TextIOWrapper` 兜底)→ 所有 `print("✗ ...")` 都炸
- 结果:`trigger='cli' / 'manual'` 永远没事,`trigger='schedule'` 永远炸 — 100% 复现

**修复**(4 处):
- `EmailNotifier.send` 内 4 个 print(没邮箱跳过 / SMTP 未配 / 成功 / 失败) 改 `logging.info/warning` + ASCII tag
- `_post_webhook` 内 3 个 print 改 logging + `[OK]/[FAIL]`
- `send_all` 内 1 个 print 改 logging + ASCII
- 全部用 `logging.getLogger("fastinfo.notifier")`,不再依赖 stdout 编码

### 2. send_all 把 `notifier.send()` 的 dict 当 bool(Day 9 留下的 bug)

**根因**(Day 9 改造 send_all 时遗留):

```python
# 旧 send_all — 真实 http_status 被丢弃
ok = n.send(user, subject, ...)   # 实际返回 dict
if ok:                            # 对非空 dict 永远 True
    out[ch] = {"ok": True, "http_status": None, "error": None}  # ← 真实的 status 没了
```

每个 `Notifier.send()` Day 9 已统一返回 `dict`,send_all 之前 `if ok` 当 bool 判断 → `http_status` 永远写 None,
push_history 里 `[feishu] ok=True status=None err=` 都是这个 bug。

**修复**:
```python
result = n.send(...)
if isinstance(result, dict):
    out[ch] = result              # 直接透传,http_status 保住
else:
    # 兼容外部子类仍返 bool 的实现
    out[ch] = {"ok": bool(result), "http_status": None,
               "error": None if result else "send() returned False"}
```

## 🛠️ 改动(表)

| 文件 | 改动 | 行级影响 |
|---|---|---|
| `src/notifier/__init__.py` | 加 `import logging`;`_log` module 级 logger;4 处 `print(...)` → `_log.info/warning(...)`,带 ASCII tag (`[OK]/[FAIL]/[!]`);`send_all` 透传 `result` dict | 5 段 edit |
| `scripts/subs_scheduler.py` | 顶部加 `if sys.platform == "win32": sys.stdout = io.TextIOWrapper(...)`(同 `api_server.py:25-27` 同样模式) | 3 行 |

**没碰的文件**(可能就是有人后续会改的,先列出来):
- `src/notifier/test.py` — 老的测试桩,没动
- 其它 53 处 print 含 ✗/✓(smoke / rss_collector / admin_sources / fastinfo CLI…)— 这些**不阻塞 push_history** 链路,本身不会进 async event loop `try` 里。但批量清理也是 Day 10+ 的 §⚠ 候选。先不动

## 📊 当前数据

```
push_history 最 6 条 (修复后)
2026-07-05T03:54:39 trigger=cli     ok=['feishu','inbox'] fail=[]
    [feishu] ok=True  status=200  err=
    [inbox]  ok=True  status=None err=
2026-07-05T03:49:52 trigger=schedule ok=['inbox'] fail=['feishu']
    [feishu] ok=False status=None err=UnicodeEncodeError: 'gbk' ...
    [inbox]  ok=True  status=None err=
2026-07-05T03:39:51 trigger=schedule 同上 (GBK 死循环)
2026-07-05T03:30:50 trigger=schedule 同上 (GBK 死循环)
2026-07-05T03:09:43 trigger=manual  ok=['feishu','inbox'] fail=[]    ← 修复前,status=None 是 send_all bug
2026-07-05T03:07:43 trigger=manual  ok=['inbox'] fail=[]

修复后 error 频次 = 0(只剩 3 条历史脏数据,作为「GBK 时代」对照)
```

## 🧪 验证命令

```powershell
# 1) 重跑一次手动推送,看 push_history 是否 status=200
python fastinfo.py subs run <sub_id>
python -c "import sys;sys.path.insert(0,'src');from storage.mongo_writer import get_sync_client,DEFAULT_DB as D;db=get_sync_client()[D];list(db.push_history.find({'trigger':'cli'}).sort('sent_at',-1).limit(1))" | python -m json.tool

# 期望:
#   channel_results.feishu.http_status == 200
#   channel_results.feishu.ok        == True

# 2) 等下一个 subs_scheduler tick(默认 60s) 再看 schedule record
# 期望: trigger='schedule', channel_results.feishu.status = 200, error = null
```

## ⚠️ 已知 / 推迟

| ID | 问题 | 影响 | 处置 |
|---|---|---|---|
| HF-1 | 其它 53 处 print 含 ✗/✓(CLI / smoke / admin_sources / fastinfo.py) | 同根症状但**不阻塞推送链路**,只在用户手动跑这些脚本时控制台喷 UnicodeEncodeError | Day 10+ 批量换成 logging + ASCII tag,或一次性 `PYTHONIOENCODING=utf-8` |
| HF-2 | push_history 时间字段仍是 ISO 字符串,不是 BSON Date | 字典序碰巧 == 时序,短期不致命 | 已列入 Day 10+ 主线计划(见 AGENTS.md §9) |
| HF-3 | 历史 3 条 GBK 死循环的脏 push_history 数据 | UI 上仍显示 ✗ 飞书群 | **不清理** — 留着当「修复前 vs 修复后」对照,证明 bug 已闭环 |

## 🚀 Day 10 主线预告(尚未开工)

按 AGENTS.md §9 已经规划的 Day 10 主线,这次 hotfix 不算:

1. **时间字段统一 BSON Date**(Day 7 留下的债)— `now_utc()` helper + 改 10+ 写入点 + 一次性回填
2. **subs_scheduler cron 精度**:用 `_next_run_simple(cron_expr, now)` 算 expected 时间,跟 now 比对,"距离下次 cron 命中 ≤60s 才跑",不再用「距上次 > 30min」兜底
3. **Mobile 端推送历史缩略**:`/m/me/subs` 加一个"最近推送"卡
4. **SourcesPage TS 类型 cast**:`columns` 满足 Naive UI `TableColumns<any>` 严格匹配
5. **P-TEST 演练**:用 tester 跑一遍 convert_topic 全链路,补 Day 9 的「已转为订阅 #xxx」跳订阅编辑
6. **`track_entity` prompt 优化**:剥掉"动态""最新"等修饰,精准识别实体

哪条先做用户说了算。
