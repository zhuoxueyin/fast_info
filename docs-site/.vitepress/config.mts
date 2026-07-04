import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'fastInfo · 文档',
  description: '个人化 AI 情报中枢 · API 与使用指南',
  cleanUrls: true,
  base: '/docs/',
  lang: 'zh-CN',
  head: [
    ['meta', { name: 'theme-color', content: '#10B981' }],
    ['link', { rel: 'icon', href: '/favicon.svg', type: 'image/svg+xml' }],
  ],
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '快速开始', link: '/guide/getting-started' },
      { text: 'API 文档', link: '/api/' },
      { text: 'Swagger UI', link: 'http://127.0.0.1:8000/docs' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '指南',
          items: [
            { text: '快速开始', link: '/guide/getting-started' },
            { text: '概念', link: '/guide/concepts' },
            { text: '鉴权', link: '/guide/auth' },
            { text: 'NL 订阅', link: '/guide/subscriptions' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API 端点',
          items: [
            { text: '总览', link: '/api/' },
            { text: '认证 · /api/auth', link: '/api/auth' },
            { text: '资讯 · /api/search|today|hot|items', link: '/api/items' },
            { text: '订阅 · /api/subs', link: '/api/subs' },
            { text: 'Banner · /api/banner', link: '/api/banner' },
            { text: 'Inbox · /api/inbox', link: '/api/inbox' },
            { text: '管理员 · /api/admin', link: '/api/admin' },
          ],
        },
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/' },
    ],
    footer: {
      message: 'fastInfo · 个人化 AI 情报中枢',
      copyright: 'MIT',
    },
  },
})