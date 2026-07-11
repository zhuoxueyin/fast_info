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
        <div class="text-xs text-slate-500 truncate">{{ form.email || '未设置邮箱' }}</div>
      </div>
      <span v-if="user.role === 'admin'" class="text-[10px] px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 font-medium">ADMIN</span>
    </div>

    <!-- 渠道凭证:配置后才能在订阅里勾选 -->
    <section class="mb-4">
      <h2 class="text-xs font-medium text-slate-500 mb-2 px-1 flex items-center gap-1">
        <Bell :size="12" />
        渠道凭证
      </h2>
      <p class="text-[11px] text-slate-400 px-1 mb-2">
        这里配置的是「能用的渠道」。每个订阅在创建/编辑时再单独勾选推到哪里。
      </p>

      <!-- 邮件 -->
      <div class="bg-white rounded-xl border border-slate-200 p-3.5 mb-2">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center">
            <Mail :size="14" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">邮件</div>
            <div class="text-[11px] text-slate-500">{{ emailReady ? '已就绪' : '需填收件邮箱 + SMTP 账号' }}</div>
          </div>
        </div>
        <div class="space-y-2">
          <input v-model="form.email" placeholder="收件邮箱" class="field" />
          <input v-model="form.smtp_user" placeholder="SMTP 用户(常同邮箱)" class="field" />
          <input v-model="form.smtp_pass" type="password" :placeholder="form.smtp_pass_set ? '已保存,留空不改' : 'SMTP 授权码'" class="field" />
        </div>
      </div>

      <!-- 飞书多群 -->
      <div class="bg-white rounded-xl border border-slate-200 p-3.5 mb-2">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-8 h-8 rounded-lg bg-cyan-500 flex items-center justify-center">
            <MessageSquare :size="14" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">飞书群机器人</div>
            <div class="text-[11px] text-slate-500">
              {{ form.feishu_webhooks.length ? `已配置 ${form.feishu_webhooks.length} 个群` : '添加 webhook 后可在订阅里挑选' }}
            </div>
          </div>
          <button type="button" class="text-xs text-emerald-600 font-medium" @click="addFeishu">+ 添加</button>
        </div>
        <div v-if="form.feishu_webhooks.length" class="space-y-2">
          <div
            v-for="(hook, idx) in form.feishu_webhooks"
            :key="idx"
            class="rounded-lg bg-slate-50 p-2.5 space-y-1.5"
          >
            <div class="flex gap-2">
              <input v-model="hook.name" placeholder="群名称" class="field flex-1" />
              <button type="button" class="text-xs text-rose-500 px-1" @click="removeFeishu(idx)">删</button>
            </div>
            <input v-model="hook.webhook" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." class="field" />
          </div>
        </div>
        <p v-else class="text-[11px] text-slate-400">点「+ 添加」从群机器人拿到 webhook 填入</p>
      </div>

      <!-- 企微 -->
      <div class="bg-white rounded-xl border border-slate-200 p-3.5 mb-2">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-8 h-8 rounded-lg bg-green-500 flex items-center justify-center">
            <SendIcon :size="14" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">企业微信</div>
            <div class="text-[11px] text-slate-500">{{ form.wechat_webhook ? '已就绪' : '填群机器人 webhook' }}</div>
          </div>
        </div>
        <input v-model="form.wechat_webhook" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/..." class="field" />
      </div>

      <!-- Webhook -->
      <div class="bg-white rounded-xl border border-slate-200 p-3.5 mb-2">
        <div class="flex items-center gap-2 mb-2">
          <span class="w-8 h-8 rounded-lg bg-purple-500 flex items-center justify-center">
            <Globe :size="14" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">通用 Webhook</div>
            <div class="text-[11px] text-slate-500">{{ form.webhook_url ? '已就绪' : 'POST JSON 到你的接口' }}</div>
          </div>
        </div>
        <input v-model="form.webhook_url" placeholder="https://..." class="field" />
      </div>

      <button
        class="w-full py-2.5 rounded-xl bg-emerald-500 text-white text-sm font-medium active:scale-[0.99] disabled:opacity-50"
        :disabled="savingCreds"
        @click="saveCredentials"
      >
        {{ savingCreds ? '保存中…' : '保存渠道凭证' }}
      </button>
      <p v-if="credMsg" class="text-xs mt-1.5 px-1" :class="credOk ? 'text-emerald-600' : 'text-rose-500'">{{ credMsg }}</p>
    </section>

    <!-- 新建订阅默认勾选的渠道(仅默认值,可在每个订阅里改) -->
    <section class="mb-4">
      <h2 class="text-xs font-medium text-slate-500 mb-2 px-1 flex items-center gap-1">
        <Inbox :size="12" />
        新建订阅默认渠道
      </h2>
      <p class="text-[11px] text-slate-400 px-1 mb-2">只影响新建时的默认勾选,每个订阅仍可单独改。</p>
      <div class="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
        <label
          v-for="ch in channelMeta"
          :key="ch.key"
          class="flex items-center gap-3 p-3.5"
          :class="ch.available ? 'active:bg-slate-50' : 'opacity-45'"
        >
          <span class="inline-flex items-center justify-center w-9 h-9 rounded-lg" :class="ch.bg">
            <component :is="ch.icon" :size="16" class="text-white" />
          </span>
          <div class="flex-1">
            <div class="text-sm font-medium text-slate-900">{{ ch.name }}</div>
            <div class="text-[11px] text-slate-500">
              {{ ch.available ? ch.desc : (ch.key === 'inbox' ? ch.desc : '凭证未配置') }}
            </div>
          </div>
          <input
            type="checkbox"
            :checked="selected[ch.key]"
            :disabled="!ch.available"
            class="w-5 h-5 accent-emerald-500"
            @change="toggleDefaultChannel(ch.key)"
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

    <div class="text-center text-[10px] text-slate-400 pt-2">fastInfo · 订阅渠道按实例配置</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronLeft, ChevronRight, Bell, Monitor, Send, History, LogOut,
  Inbox, Mail, MessageSquare, Send as SendIcon, Globe,
} from 'lucide-vue-next'
import { api } from '@/lib/api'
import { useAuthStore } from '@/store/auth'
import { setDeviceOverride, detectDevice } from '@/lib/device'
import type { User } from '@/types/api'

const router = useRouter()
const auth = useAuthStore()

const user = computed<User>(() => auth.user || { id: '', username: '' })
const initial = computed(() => (user.value.username || 'U')[0].toUpperCase())

type FeishuHook = { name: string; webhook: string }

const form = ref({
  email: '',
  smtp_user: '',
  smtp_pass: '',
  smtp_pass_set: false,
  feishu_webhooks: [] as FeishuHook[],
  wechat_webhook: '',
  webhook_url: '',
})

const selected = ref<Record<string, boolean>>({ inbox: true })
const availableSet = ref<Set<string>>(new Set(['inbox']))
const savingCreds = ref(false)
const credMsg = ref('')
const credOk = ref(false)

const emailReady = computed(() => !!(form.value.email && form.value.smtp_user))

const channelMeta = computed(() => {
  const list = [
    { key: 'inbox',  name: '站内',     desc: '收件箱回看',     icon: Inbox,         bg: 'bg-emerald-500' },
    { key: 'email',  name: '邮件',     desc: '发送至配置邮箱', icon: Mail,          bg: 'bg-blue-500' },
    { key: 'feishu', name: '飞书',     desc: '群机器人推送',   icon: MessageSquare, bg: 'bg-cyan-500' },
    { key: 'wechat', name: '企业微信', desc: '群机器人推送',   icon: SendIcon,      bg: 'bg-green-500' },
    { key: 'webhook', name: 'Webhook', desc: 'POST 到你的接口', icon: Globe,        bg: 'bg-purple-500' },
  ]
  return list.map(ch => ({
    ...ch,
    available: availableSet.value.has(ch.key),
  }))
})

const deviceOverride = ref<'auto' | 'mobile' | 'desktop'>('auto')

function onDeviceChange() {
  if (deviceOverride.value === 'auto') {
    setDeviceOverride(null)
  } else {
    setDeviceOverride(deviceOverride.value)
  }
  router.replace({ path: '/m/me/settings', query: { _: Date.now().toString() } })
}

function addFeishu() {
  form.value.feishu_webhooks.push({ name: `群${form.value.feishu_webhooks.length + 1}`, webhook: '' })
}

function removeFeishu(idx: number) {
  form.value.feishu_webhooks.splice(idx, 1)
}

function refreshAvailable() {
  const s = new Set<string>(['inbox'])
  if (form.value.email && form.value.smtp_user) s.add('email')
  if (form.value.feishu_webhooks.some(h => h.webhook?.trim())) s.add('feishu')
  if (form.value.wechat_webhook?.trim()) s.add('wechat')
  if (form.value.webhook_url?.trim()) s.add('webhook')
  availableSet.value = s
  // 去掉不可用的默认勾选
  for (const k of Object.keys(selected.value)) {
    if (selected.value[k] && !s.has(k)) selected.value[k] = false
  }
  if (!Object.values(selected.value).some(Boolean)) selected.value.inbox = true
}

async function loadSettings() {
  try {
    const [settings, channels] = await Promise.all([
      api<any>('/settings'),
      api<any>('/notifier/channels'),
    ])
    form.value.email = settings?.email || ''
    form.value.smtp_user = settings?.smtp_user || ''
    form.value.smtp_pass = ''
    form.value.smtp_pass_set = !!settings?.smtp_pass_set
    form.value.feishu_webhooks = Array.isArray(settings?.feishu_webhooks)
      ? settings.feishu_webhooks.filter((h: any) => h?.webhook).map((h: any) => ({
          name: h.name || '默认群',
          webhook: h.webhook,
        }))
      : []
    form.value.wechat_webhook = settings?.wechat_webhook || ''
    form.value.webhook_url = settings?.webhook_url || ''

    availableSet.value = new Set(
      Array.isArray(channels?.available) ? channels.available : ['inbox'],
    )
    const defaults: string[] = Array.isArray(channels?.default_channels)
      ? channels.default_channels
      : (settings?.channels || ['inbox'])
    selected.value = {}
    for (const c of defaults) selected.value[c] = true
    if (!selected.value.inbox && !defaults.length) selected.value.inbox = true
  } catch {
    // ignore
  }
}

async function saveCredentials() {
  savingCreds.value = true
  credMsg.value = ''
  try {
    const body: Record<string, unknown> = {
      email: form.value.email,
      smtp_user: form.value.smtp_user,
      feishu_webhooks: form.value.feishu_webhooks.filter(h => h.webhook?.trim()),
      wechat_webhook: form.value.wechat_webhook,
      webhook_url: form.value.webhook_url,
      default_channels: Object.entries(selected.value)
        .filter(([, on]) => on)
        .map(([k]) => k),
    }
    if (form.value.smtp_pass) body.smtp_pass = form.value.smtp_pass
    await api('/settings', { method: 'PUT', body })
    form.value.smtp_pass = ''
    form.value.smtp_pass_set = true
    refreshAvailable()
    // 再拉一次权威 available
    try {
      const ch = await api<any>('/notifier/channels')
      availableSet.value = new Set(Array.isArray(ch?.available) ? ch.available : ['inbox'])
    } catch { /* ignore */ }
    credOk.value = true
    credMsg.value = '渠道凭证已保存'
  } catch (e: any) {
    credOk.value = false
    credMsg.value = e?.data?.detail || '保存失败'
  } finally {
    savingCreds.value = false
  }
}

async function saveDefaultChannels() {
  try {
    const defaultChannels = Object.entries(selected.value)
      .filter(([, on]) => on)
      .map(([k]) => k)
    await api('/settings', {
      method: 'PUT',
      body: { default_channels: defaultChannels.length ? defaultChannels : ['inbox'] },
    })
  } catch {
    // ignore
  }
}

function toggleDefaultChannel(key: string) {
  if (!availableSet.value.has(key)) return
  selected.value[key] = !selected.value[key]
  // 至少 inbox
  if (!Object.values(selected.value).some(Boolean)) selected.value.inbox = true
  saveDefaultChannels()
}

async function testInbox() {
  try {
    await api('/notifier/test', { method: 'POST', body: { channel: 'inbox' } })
    alert('测试推送已发送(站内)')
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
  auth.fetchMe().catch(() => {})
  try {
    const stored = localStorage.getItem('fastinfo.device-override')
    if (stored === 'mobile' || stored === 'desktop') deviceOverride.value = stored
    else deviceOverride.value = 'auto'
  } catch {
    deviceOverride.value = 'auto'
  }
  detectDevice()
})
</script>

<style scoped>
.field {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.5rem;
  outline: none;
  background: #fff;
}
.field:focus {
  border-color: #34d399;
  box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.25);
}
</style>
