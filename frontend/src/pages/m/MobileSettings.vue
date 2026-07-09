<template>
  <div>
    <div class="flex items-center gap-2 mb-4">
      <button class="p-1 -ml-1" @click="goBack">
        <ChevronLeft :size="22" />
      </button>
      <h1 class="text-lg font-bold text-slate-900">设置</h1>
    </div>

    <!-- 用户卡片 -->
    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-4 flex items-center gap-3">
      <div class="w-12 h-12 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 text-white flex items-center justify-center text-lg font-bold">
        {{ initial }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="font-semibold text-slate-900 truncate">{{ user.username }}</div>
        <div class="text-xs text-slate-500 truncate">{{ user.email || '未设置邮箱' }}</div>
      </div>
      <span v-if="user.role === 'admin'" class="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">ADMIN</span>
    </div>

    <!-- 推送渠道 -->
    <section class="mb-4">
      <h2 class="text-xs font-medium text-slate-500 mb-2 px-1 flex items-center gap-1">
        <Bell :size="12" />
        推送渠道
      </h2>
      <div class="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
        <label v-for="ch in channels" :key="ch.key" class="flex items-center gap-3 p-3.5 active:bg-slate-50">
          <span class="inline-flex items-center justify-center w-9 h-9 rounded-lg" :class="ch.bg">
            <component :is="ch.icon" :size="16" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">{{ ch.name }}</div>
            <div class="text-[11px] text-slate-500">{{ ch.desc }}</div>
          </div>
          <input
            type="checkbox"
            :checked="selected[ch.key]"
            class="w-5 h-5 accent-emerald-500"
            @change="toggleChannel(ch.key)"
          />
        </label>
      </div>
    </section>

    <!-- 显示设置 -->
    <section class="mb-4">
      <h2 class="text-xs font-medium text-slate-500 mb-2 px-1 flex items-center gap-1">
        <Monitor :size="12" />
        显示
      </h2>
      <div class="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
        <div class="p-3.5">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-sm font-medium text-slate-900">视图模式</div>
              <div class="text-[11px] text-slate-500">强制桌面或跟随系统</div>
            </div>
            <select
              v-model="deviceOverride"
              class="text-xs border border-slate-200 rounded-lg px-2 py-1.5 bg-white"
              @change="onDeviceChange"
            >
              <option value="auto">跟随系统</option>
              <option value="mobile">强制手机版</option>
              <option value="desktop">强制桌面版</option>
            </select>
          </div>
        </div>
      </div>
    </section>

    <!-- 危险操作 -->
    <section class="mb-4">
      <h2 class="text-xs font-medium text-slate-500 mb-2 px-1">账户</h2>
      <div class="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
        <button class="w-full p-3.5 text-left flex items-center gap-3 active:bg-slate-50" @click="testInbox">
          <Send :size="16" class="text-slate-500" />
          <div class="flex-1 text-sm text-slate-900">测试推送通知</div>
          <ChevronRight :size="16" class="text-slate-300" />
        </button>
        <router-link to="/m/me/push-history" class="w-full p-3.5 flex items-center gap-3 active:bg-slate-50">
          <History :size="16" class="text-slate-500" />
          <div class="flex-1 text-sm text-slate-900">推送历史</div>
          <ChevronRight :size="16" class="text-slate-300" />
        </router-link>
        <button class="w-full p-3.5 text-left flex items-center gap-3 active:bg-red-50" @click="onLogout">
          <LogOut :size="16" class="text-red-500" />
          <div class="flex-1 text-sm text-red-600">退出登录</div>
        </button>
      </div>
    </section>

    <div class="text-center text-[10px] text-slate-400 pt-2">fastInfo · Day 12 · mobile-adapt</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronLeft, ChevronRight, Bell, Monitor, Send, History, LogOut, Inbox, Mail, MessageSquare, Send as SendIcon, Globe } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { setDeviceOverride, detectDevice } from '@/lib/device'
import type { User } from '@/types/api'

const router = useRouter()
const auth = useAuthStore()

const user = computed<User>(() => auth.user || { id: '', username: '' })
const initial = computed(() => (user.value.username || 'U')[0].toUpperCase())

const channels = [
  { key: 'inbox',  name: '站内',     desc: '在 /me/inbox 查看',       icon: Inbox,         bg: 'bg-emerald-500' },
  { key: 'email',  name: '邮件',     desc: '发送至注册邮箱',          icon: Mail,          bg: 'bg-blue-500' },
  { key: 'feishu', name: '飞书',     desc: '机器人推送',              icon: MessageSquare, bg: 'bg-cyan-500' },
  { key: 'wechat', name: '微信',     desc: '需先扫码绑定',            icon: SendIcon,      bg: 'bg-green-500' },
  { key: 'webhook', name: 'Webhook', desc: 'POST 到你的接口',         icon: Globe,         bg: 'bg-purple-500' },
]

const selected = ref<Record<string, boolean>>({})

const deviceOverride = ref<'auto' | 'mobile' | 'desktop'>('auto')

function onDeviceChange() {
  if (deviceOverride.value === 'auto') {
    setDeviceOverride(null)
  } else {
    setDeviceOverride(deviceOverride.value)
  }
  // 强制刷新路由
  router.replace({ path: '/m/me/settings', query: { _: Date.now().toString() } })
}

async function loadSettings() {
  try {
    const r = await api<any>('/settings')
    const channels = r?.channels || r?.default_channels || []
    // channels 是字符串数组,转成 {channel: boolean} 映射
    selected.value = { ...selected.value }
    channels.forEach((c: string) => { selected.value[c] = true })
  } catch {
    // ignore
  }
}

async function saveSettings() {
  try {
    const defaultChannels = channels
      .filter(ch => selected.value[ch.key])
      .map(ch => ch.key)
    await api('/settings', {
      method: 'PUT',
      body: { default_channels: defaultChannels.length ? defaultChannels : ['inbox'] },
    })
  } catch {
    // ignore
  }
}

function toggleChannel(key: string) {
  selected.value[key] = !selected.value[key]
  saveSettings()
}

async function testInbox() {
  try {
    await api('/notifier/test', { method: 'POST', body: { channel: 'inbox' } })
    alert('测试推送已发送')
  } catch (e: any) {
    alert(e?.data?.detail || '测试失败')
  }
}

function onLogout() {
  if (!confirm('确定要退出登录吗?')) return
  auth.logout()
  router.push('/m')
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/m/me')
}

onMounted(() => {
  loadSettings()
  // 加载用户信息
  auth.fetchMe().catch(() => {})

  // 读取 device override
  const cur = detectDevice()
  try {
    const stored = localStorage.getItem('fastinfo.device-override')
    if (stored === 'mobile' || stored === 'desktop') deviceOverride.value = stored
    else deviceOverride.value = 'auto'
  } catch {}
})
</script>