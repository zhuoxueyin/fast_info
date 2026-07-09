---
layout: home
title: fastInfo · 个人化 AI 情报中枢
hero:
  name: fastInfo
  text: 把资讯变成情报
  tagline: RSS 抓取 · LLM 摘要 · 个性化订阅 · 一站式 Web 平台
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/getting-started
    - theme: alt
      text: 查看 API
      link: /api/
    - theme: alt
      text: Swagger UI
      link: http://127.0.0.1:8000/docs
features:
  - title: 📡 多源抓取
    details: 内置 7 个 RSS 源(36kr / huxiu / ifanr / qbitai / infoq / sspai / ithome),每日自动抓取 + LLM 摘要入库
  - title: 🤖 四级 LLM fallback
    details: MiniMax M2.7-highspeed / M2.7 / M3 → Kimi K2.6,熔断 + 冷却 + 自动 fallback,稳定可控
  - title: 🎯 自然语言订阅
    details: 输入「每天 9 点看 AI 资讯」自动解析为 cron + 关键词,无需手写配置
  - title: 🌐 Web 平台
    details: 用户视角看热门 / 搜索 / 个人推送
  - title: 🔌 REST API
    details: 15+ 个 endpoint 全部带 Swagger UI,前端 / 脚本 / 第三方都能对接
  - title: 📚 完整文档
    details: 所有 API 使用说明 + cURL 示例 + 中文教程,新人 5 分钟跑通
---

## 你能做什么?

### 🔍 游客能做的
- 浏览公域首页:按类目 Banner / 今日热门 Top 10 / 最新 30 条
- 今日最热:按类目查看该类目今日高相关度内容
- 全局搜索:标题 / 摘要 / 关键点命中
- 阅读文档

### 👤 注册用户能做的
- 自然语言创建订阅,自动转 cron + 关键词
- 立即跑 / 暂停 / 删除订阅
- 查看个人推送 inbox,按热度 / 时间 / 类目 / 订阅名筛选
- 一键注册(用户名 + 密码,5 秒搞定)

### 🔧 管理员能做的
- 看 7 个 RSS 源 24h 抓取状态
- 看抓取时间线(最近 20 次)
- 看 LLM 模型组 × provider 配置
- 看汇总统计:总数据量 / 源分布 / 类目分布 / LLM 调用分布
- 配置公域 Banner 类目
- 手动触发全站 ingest

## 立刻试试

打开主页开始浏览,或去 [API 文档](/api/) 查看全部接口。