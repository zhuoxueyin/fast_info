# CHANGELOG.md 维护约定

> 这份文件说**怎么维护 `docs/CHANGELOG.md`**,防止文档与代码漂移。

## 何时更新

每次 commit 前 / commit 后,**必须**做的事:

```
git commit -m "..." 前:
1. 看 docs/CHANGELOG.md 顶部 [Unreleased] 区
2. 加本次 commit 的改动到对应 ### Added / ### Changed / ### Fixed
3. commit message 中引用 CHANGELOG(可选)
```

或者**批量模式**:每天工作结束时,把今天所有 commit 的改动一次性整合到 `[Unreleased]`。

## 版本号什么时候升

| 触发 | 版本号 |
|---|---|
| 加新端点 / 新模块 / 用户可见功能 | minor(v0.4.0 → v0.5.0)|
| 修复 bug(不改 API) | patch(v0.4.0 → v0.4.1)|
| 加新接口 / 改变 API 行为 / 改 schema | major(v0.x → v1.0,**警告!**)|

## 怎么"发布"新版本

```bash
# 1. 把 [Unreleased] 内容移到 [v{next}] 块,加日期
# 编辑 docs/CHANGELOG.md:
#   - 顶部 [Unreleased] / v0.4.x 改成新版本块 [v0.5.0] - YYYY-MM-DD
#   - 新加一个 [Unreleased] / v0.5.x 占位

# 2. 同步更新 AGENTS.md §1 现状速览(把版本号同步刷新)

# 3. 同步更新 docs/CHANGELOG.md 顶部"当前"指示

# 4. 单独 commit:
git add docs/CHANGELOG.md AGENTS.md docs/day{N}-deliverable.md
git commit -m "docs: release v0.5.0 - 描述新功能"
```

## 一致性约束

| 文档 | 内容 | 不能 |
|---|---|---|
| `CHANGELOG.md` | 跨版本变更轨迹 | 改前版本内容;放当前状态; |
| `day{N}-deliverable.md` | 当天交付细节 | 跨天 trace(用 CHANGELOG 替代)|
| `AGENTS.md §1` | 当前状态速览 | 详细 commit 列表(用 CHANGELOG)|
| `git log` | 精确元数据 | 详细 business 描述(用 CHANGELOG)|

## 自动化建议(可选,Phase 2)

后续可以加脚本 `scripts/sync_changelog.py`:
- 读 `git log` 最近 N 个 commit
- 自动按 conventional commits 格式生成 CHANGELOG 块
- 不取代人工,但能减少手写

短期:**人工更新**(本文件)**即可**,禁止自动工具未审计替换人工内容。

## 提交规范(commit message 风格)

参考本仓库既有 commit 风格:
```
feat: Day X v0.Y - 主标题

- 子项 1
- 子项 2

详见 docs/CHANGELOG.md v0.Y
```

或 keep conventional commits:`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`。

## 例子:本次 commit 的更新范例

```bash
# 在 commit 之前,改 docs/CHANGELOG.md:
# 在 [Unreleased] / v0.4.2 段加:
### Fixed
- changelog docs setup (DAY 7 沉淀 metadata)
```
