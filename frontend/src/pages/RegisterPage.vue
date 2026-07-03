<template>
  <div class="max-w-md mx-auto bg-white rounded-xl border border-slate-200 p-8 mt-8">
    <h1 class="text-2xl font-bold text-slate-900 mb-6">注册账号</h1>
    <n-form :model="form" label-placement="top" @submit.prevent="onSubmit">
      <n-form-item label="用户名">
        <n-input v-model:value="form.username" placeholder="3-20 位字母 / 数字 / 下划线" />
      </n-form-item>
      <n-form-item label="邮箱(可选)">
        <n-input v-model:value="form.email" placeholder="alice@example.com" />
      </n-form-item>
      <n-form-item label="密码">
        <n-input v-model:value="form.password" type="password" show-password-on="click" placeholder="≥ 6 位" />
      </n-form-item>
      <n-button type="primary" block :loading="loading" @click="onSubmit">注册</n-button>
    </n-form>
    <p class="mt-4 text-sm text-slate-500 text-center">
      已有账号?
      <router-link to="/login" class="text-emerald-600 hover:underline">去登录</router-link>
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NForm, NFormItem, NInput, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()
const msg = useMessage()
const loading = ref(false)
const form = ref({ username: '', email: '', password: '' })

async function onSubmit() {
  if (!form.value.username || !form.value.password) {
    msg.warning('请填完整')
    return
  }
  loading.value = true
  try {
    await auth.register(form.value.username, form.value.password, form.value.email)
    msg.success('注册成功,已自动登录')
    router.push('/me')
  } catch (e: any) {
    msg.error(e?.data?.detail || e?.message || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>