import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types/api'
import { api } from '@/lib/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username: string, password: string) {
    const r = await api<{ token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: { username, password },
    })
    token.value = r.token
    user.value = r.user
    localStorage.setItem('token', r.token)
    localStorage.setItem('user', JSON.stringify(r.user))
  }

  async function register(username: string, password: string, email = '') {
    const r = await api<{ token: string; user: User }>('/auth/register', {
      method: 'POST',
      body: { username, password, email },
    })
    token.value = r.token
    user.value = r.user
    localStorage.setItem('token', r.token)
    localStorage.setItem('user', JSON.stringify(r.user))
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      user.value = await api<User>('/auth/me')
      localStorage.setItem('user', JSON.stringify(user.value))
    } catch (e) {
      // token 失效
      logout()
    }
  }

  // 启动时如果有 token + cached user,先 hydrate,再后台校验
  const cached = localStorage.getItem('user')
  if (cached) {
    try {
      user.value = JSON.parse(cached)
    } catch {}
  }
  if (token.value) {
    fetchMe()
  }

  return { token, user, isLoggedIn, isAdmin, login, register, logout, fetchMe }
})