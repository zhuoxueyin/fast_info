<template>
  <div class="pt-8">
    <h1 class="text-2xl font-bold text-center mb-6">登录 fastInfo</h1>
    <div class="bg-white rounded-lg border p-4">
      <input v-model="username" type="text" placeholder="用户名" class="w-full border rounded px-3 py-2 mb-3" />
      <input v-model="password" type="password" placeholder="密码" class="w-full border rounded px-3 py-2 mb-3" @keyup.enter="onLogin" />
      <button class="w-full bg-emerald-500 text-white rounded py-2" :disabled="loading" @click="onLogin">
        {{ loading ? '登录中…' : '登录' }}
      </button>
      <p v-if="error" class="text-red-500 text-sm mt-2 text-center">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onLogin() {
  if (!username.value || !password.value) {
    error.value = '请填完整'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/m/me')
  } catch (e: any) {
    error.value = e?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>