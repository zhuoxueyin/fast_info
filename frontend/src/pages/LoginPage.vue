<template>
  <div class="max-w-md mx-auto bg-white rounded-xl border border-slate-200 p-8 mt-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">登录 fastInfo</h1>
    <n-form :model="form" label-placement="top" @submit.prevent="onSubmit">
      <n-form-item label="用户名">
        <n-input v-model:value="form.username" placeholder="alice" />
      </n-form-item>
      <n-form-item label="密码">
        <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="••••••" @keyup.enter="onSubmit" />
      </n-form-item>
      <n-button type="primary" block :loading="loading" @click="onSubmit">登录</n-button>
    </n-form>
    <p class="mt-4 text-sm text-slate-500 text-center">
      还没有账号?
      <router-link to="/register" class="text-emerald-600 hover:underline">立即注册</router-link>
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const msg = useMessage()
const loading = ref(false)
const form = ref({ username: '', password: '' })

async function onSubmit() {
  if (!form.value.username || !form.value.password) {
    msg.warning('请填完整')
    return
  }
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    msg.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    msg.error(e?.data?.detail || e?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>