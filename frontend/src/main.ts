import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 动态 import 失败时给用户可见反馈(之前点「管理」静默无反应)
router.onError((err) => {
  const msg = String(err?.message || err || '')
  const isChunkFail =
    /Failed to fetch dynamically imported module|Loading chunk|Loading CSS chunk|Importing a module script failed/i.test(msg)
  if (isChunkFail) {
    console.error('[router] chunk load failed:', err)
    // 强制刷新一次拉新 index/hash;若已带 _reload 则不再循环
    const url = new URL(window.location.href)
    if (!url.searchParams.has('_reload')) {
      url.searchParams.set('_reload', String(Date.now()))
      window.location.replace(url.toString())
      return
    }
    window.alert('页面资源加载失败,请强制刷新(Ctrl+F5)后重试')
  } else {
    console.error('[router] navigation error:', err)
  }
})

app.mount('#app')