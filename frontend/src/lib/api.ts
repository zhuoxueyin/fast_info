/**
 * fastInfo · API 客户端
 * 用 ofetch 自动带 JWT,所有 API 调用统一走这里。
 */
import { ofetch } from 'ofetch'

const BASE = (import.meta.env.VITE_API_BASE as string) || '/api'

export const api = ofetch.create({
  baseURL: BASE,
  retry: 1,
  timeout: 30000,
  onRequest({ options }) {
    const token = localStorage.getItem('token')
    if (token) {
      const headers = new Headers(options.headers as HeadersInit | undefined)
      headers.set('Authorization', `Bearer ${token}`)
      options.headers = headers
    }
  },
  onResponseError({ response }) {
    if (response.status === 401) {
      // 401 自动跳登录(但不强制清 token,留给 router 处理)
      console.warn('[api] 401 Unauthorized')
    }
  },
})