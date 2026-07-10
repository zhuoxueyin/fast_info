<template>
  <div class="max-w-5xl mx-auto pb-12">
    <!-- 用户头像区(Day 7 三件套: 头像图 / 昵称 / 套餐真值,全部可编辑) -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center gap-4">
        <!-- 头像: URL → 首字母兜底,首字母取 nickname → username -->
        <div class="w-14 h-14 rounded-full overflow-hidden bg-emerald-500 text-white text-2xl font-bold flex items-center justify-center flex-shrink-0">
          <img v-if="auth.user?.avatar_url" :src="auth.user.avatar_url" class="w-full h-full object-cover" referrerpolicy="no-referrer" @error="onAvatarError" />
          <span v-else>{{ avatarInitial }}</span>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <!-- 昵称: nickname → username -->
            <span class="text-lg font-semibold text-slate-900 truncate">{{ displayName }}</span>
            <n-tag size="small" type="info" :bordered="false">{{ auth.user?.role || 'user' }}</n-tag>
            <n-tag size="small" :bordered="false">套餐: {{ planLabel }}</n-tag>
            <!-- admin 用 admin 套餐标识区分,默认 placeholder 是 free -->
          </div>
          <div class="text-xs text-slate-400 mt-1">
            <span class="font-mono">{{ auth.user?.username }}</span>
            <span class="mx-1">·</span>
            📧 {{ auth.user?.email || '未设置邮箱' }}
          </div>
        </div>

        <n-button size="small" @click="openProfileEdit" class="flex-shrink-0">
          ✏️ 编辑资料
        </n-button>
      </div>

      <!-- 资料编辑 Modal(Day 7) -->
      <n-modal v-model:show="showProfileEdit" preset="card" title="编辑个人资料" style="max-width: 500px;">
        <n-form-item label="昵称(留空 = 显示用户名)">
          <n-input v-model:value="profileDraft.nickname" placeholder="例如:小明 / Alice" maxlength="30" show-count />
        </n-form-item>
        <n-form-item label="头像 URL(留空 = 显示首字母)">
          <n-input v-model:value="profileDraft.avatar_url" placeholder="https://example.com/avatar.jpg" />
        </n-form-item>
        <n-form-item label="邮箱(可选,仅做展示)">
          <n-input v-model:value="profileDraft.email" placeholder="your@example.com" />
        </n-form-item>
        <div class="flex gap-2 mt-4 justify-end">
          <n-button @click="showProfileEdit = false">取消</n-button>
          <n-button type="primary" @click="saveProfile" :loading="savingProfile">保存</n-button>
        </div>
      </n-modal>
    </section>

    <!-- ==================== 区域1: 我的频道 ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-slate-900">📚 我的频道 ({{ subs.length }})</h2>
        <n-button type="primary" size="small" @click="$router.push('/subs/new')">➕ 订刊</n-button>
      </div>

      <!-- 频道列表 -->
      <div v-if="subsLoading" class="text-center text-slate-400 py-6">加载中…</div>

      <div v-else-if="!subs.length" class="text-center py-8">
        <n-empty description="还没有频道">
          <template #extra>
            <n-button type="primary" @click="$router.push('/subs/new')">创建第一个频道</n-button>
          </template>
        </n-empty>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="s in subs"
          :key="s.id"
          class="flex items-center justify-between border-b border-slate-100 pb-3 last:border-b-0 last:pb-0"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-slate-900 truncate">{{ s.title }}</span>
              <n-tag :type="s.is_active ? 'success' : 'default'" size="small" :bordered="false">
                {{ s.is_active ? '运行中' : '已暂停' }}
              </n-tag>
            </div>
            <div class="text-xs text-slate-500 mt-1 truncate">
              {{ s.keywords?.join(' · ') || s.nl_query || '无关键词' }}
              <span class="mx-1">·</span>
              {{ s.interval_min ? `每${s.interval_min}分钟` : s.cron_expr }}
              <span class="mx-1">·</span>
              {{ (s.channels || ['inbox']).map((c: string) => chLabel(c)).join(' + ') }}
            </div>
          </div>
          <div class="flex items-center gap-2 ml-4 flex-shrink-0">
            <n-switch :value="s.is_active" size="small" @update:value="(v: boolean) => toggleActive(s, v)" />
            <!-- Day 7:订阅编辑入口,跳到 /subs/edit/:id -->
            <n-button size="tiny" @click="$router.push(`/subs/edit/${s.id}`)" title="编辑规则">✏️</n-button>
            <n-button size="tiny" @click="runSub(s.id)" title="立即运行">▶</n-button>
            <n-popconfirm @positive-click="deleteSub(s.id)">
              <template #trigger>
                <n-button size="tiny" type="error" ghost>删除</n-button>
              </template>
              确定删除这个频道?
            </n-popconfirm>
          </div>
        </div>
      </div>
    </section>

    <!-- ==================== 区域1.5: 推送历史 (Day 9) ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-slate-900 flex items-center gap-2">
          ✉️ 晨报记录
          <n-tag size="small" :bordered="false" v-if="recentPush.total">{{ recentPush.total }}</n-tag>
        </h2>
        <n-button size="small" @click="$router.push('/me/push-history')">
          查看全部 →
        </n-button>
      </div>

      <div v-if="recentPush.loading" class="text-center text-slate-400 py-4 text-sm">加载中…</div>
      <div v-else-if="!recentPush.items.length" class="text-center py-6 text-slate-400 text-sm">
        还没有晨报记录
      </div>
      <ul v-else class="space-y-2">
        <li
          v-for="r in recentPush.items"
          :key="r.id"
          class="flex items-start gap-3 py-2 border-b border-slate-100 last:border-b-0 last:pb-0"
        >
          <span class="text-lg leading-none">{{ triggerIcon(r.trigger) }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm text-slate-900 font-medium truncate">
                {{ r.subscription_title || '(频道已删)' }}
              </span>
              <n-tag size="tiny" :type="triggerTagType(r.trigger)" :bordered="false">
                {{ triggerLabel(r.trigger) }}
              </n-tag>
              <n-tag
                v-for="ch in r.channels_ok"
                :key="'ok-'+ch"
                size="tiny"
                :bordered="false"
                type="success"
              >✓ {{ chLabel(ch) }}</n-tag>
              <n-tag
                v-for="ch in r.channels_fail"
                :key="'fail-'+ch"
                size="tiny"
                :bordered="false"
                type="error"
              >✗ {{ chLabel(ch) }}</n-tag>
            </div>
            <div class="text-xs text-slate-400 mt-1">
              🕒 {{ formatTime(r.sent_at) }} · {{ r.item_count }} 条新情报 ·
              <span v-if="r.operator && r.operator !== 'auto'">由 {{ r.operator }} 触发</span>
              <span v-else>系统自动</span>
            </div>
          </div>
        </li>
      </ul>
    </section>

    <!-- ==================== 区域2: 推送设置 ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-6">
      <h2 class="text-lg font-semibold text-slate-900 mb-4">⚙️ 情报推送设置</h2>

      <!-- 飞书群机器人 (Webhook):支持多群 -->
      <div class="mb-6 p-4 bg-slate-50 rounded-lg">
        <h3 class="font-semibold text-slate-800 mb-3 flex items-center gap-2">
          🤖 飞书群机器人
          <n-tag v-if="setting.feishu_webhooks.length" type="success" size="small" :bordered="false">
            ✓ 已配置 {{ setting.feishu_webhooks.length }} 个群
          </n-tag>
          <n-tag v-else size="small" :bordered="false">未配置</n-tag>
        </h3>
        <p class="text-xs text-slate-500 mb-3">
          在飞书群中添加「自定义机器人」，获取 Webhook 地址后填入下方；可添加多个群同时推送。
        </p>
        <div class="space-y-2 mb-3">
          <div
            v-for="(hook, idx) in setting.feishu_webhooks"
            :key="idx"
            class="flex items-start gap-2 p-3 bg-white rounded-lg border border-slate-200"
          >
            <div class="flex-1 space-y-2">
              <n-input v-model:value="hook.name" placeholder="群名称" size="small" />
              <n-input v-model:value="hook.webhook" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" size="small" />
            </div>
            <div class="flex flex-col gap-1">
              <n-button
                size="tiny"
                type="primary"
                ghost
                :disabled="!hook.webhook"
                :loading="testingFeishuIdx === idx"
                @click="testFeishuGroup(idx)"
              >
                测试
              </n-button>
              <n-button size="tiny" type="error" ghost @click="removeFeishuHook(idx)">删除</n-button>
            </div>
          </div>
        </div>
        <n-button size="small" class="mb-1" @click="addFeishuHook">➕ 添加群</n-button>
        <p class="text-xs text-slate-400">测试按群维度发送,只推到当前这一行的 webhook。</p>
      </div>

      <!-- 默认推送渠道 -->
      <div class="mb-4">
        <h3 class="font-semibold text-slate-800 mb-3 flex items-center gap-2">
          📡 默认推送渠道
          <span class="text-xs text-slate-400 font-normal">未配置的渠道不会显示(与 Settings 单字段一致)</span>
        </h3>
        <n-checkbox-group v-model:value="setting.channels">
          <n-space>
            <n-checkbox
              v-for="ch in availableChannels"
              :key="ch.name"
              :value="ch.name"
            >
              {{ ch.label }}
            </n-checkbox>
          </n-space>
        </n-checkbox-group>
      </div>

      <!-- 保存 -->
      <div class="flex gap-3 pt-2">
        <n-button type="primary" @click="saveSettings" :loading="savingSettings" size="large">
          {{ savingSettings ? '保存中...' : '💾 保存配置' }}
        </n-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NButton, NEmpty, NTag, NSwitch,
  NInput, NFormItem,
  NCheckbox, NCheckboxGroup, NSpace, NPopconfirm,
  NModal, useMessage,
} from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import { api, listPushHistory } from '@/lib/api'
import type { Subscription, PushHistoryRecord } from '@/types/api'

const auth = useAuthStore()
const msg = useMessage()

// ==================== Day 7 用户三件套 ====================

const PLAN_LABELS: Record<string, string> = {
  free: '免费版',
  pro: 'Pro 版',
  team: '团队版',
  admin: '管理员',
}

const displayName = computed(() => {
  const nick = auth.user?.nickname?.trim()
  return nick || auth.user?.username || 'admin'
})

const avatarInitial = computed(() => {
  const c = displayName.value || ''
  return (c[0] || 'A').toUpperCase()
})

const planLabel = computed(() => {
  const p = auth.user?.plan || 'free'
  return PLAN_LABELS[p] ?? p
})

// 编辑资料
const showProfileEdit = ref(false)
const savingProfile = ref(false)
const profileDraft = ref({
  nickname: '',
  avatar_url: '',
  email: '',
})

function openProfileEdit() {
  profileDraft.value = {
    nickname: auth.user?.nickname ?? '',
    avatar_url: auth.user?.avatar_url ?? '',
    email: auth.user?.email ?? '',
  }
  showProfileEdit.value = true
}

function onAvatarError(e: Event) {
  // 图片加载失败,把 src 清掉,显示首字母兜底
  if (auth.user) (auth.user as any).avatar_url = null
}

async function saveProfile() {
  savingProfile.value = true
  try {
    const r: any = await api('/auth/me', {
      method: 'PATCH',
      body: {
        nickname: profileDraft.value.nickname,
        avatar_url: profileDraft.value.avatar_url,
        email: profileDraft.value.email,
      },
    })
    // 同步到 auth store
    auth.user = { ...auth.user, ...r }
    localStorage.setItem('user', JSON.stringify(auth.user))
    msg.success('已保存')
    showProfileEdit.value = false
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    savingProfile.value = false
  }
}

// ==================== 推送历史 (Day 9) ====================
const recentPush = ref({ items: [] as PushHistoryRecord[], loading: false, total: 0 })

async function loadRecentPush() {
  recentPush.value.loading = true
  try {
    const r = await listPushHistory({ limit: 5 })
    recentPush.value = { items: r.items, loading: false, total: r.total }
  } catch {
    recentPush.value.loading = false
  }
}

const TRIGGER_META: Record<string, { label: string; icon: string; tagType: 'default' | 'info' | 'success' | 'warning' }> = {
  manual:   { label: '手动',   icon: '🖱', tagType: 'info' },
  schedule: { label: '调度',   icon: '⏰', tagType: 'success' },
  test:     { label: '测试',   icon: '🧪', tagType: 'warning' },
  cli:      { label: 'CLI',   icon: '💻', tagType: 'default' },
  unknown:  { label: '未知',   icon: '❔', tagType: 'default' },
}

function triggerLabel(t: string) { return TRIGGER_META[t]?.label ?? t }
function triggerIcon(t: string)  { return TRIGGER_META[t]?.icon ?? '❔' }
function triggerTagType(t: string) { return TRIGGER_META[t]?.tagType ?? 'default' }

function formatTime(iso?: string | null) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

// ==================== 我的订阅 ====================
const subs = ref<Subscription[]>([])
const subsLoading = ref(true)

function chLabel(c: string): string {
  return { inbox: '站内', feishu: '飞书群' }[c] || c
}

async function loadSubs() {
  subsLoading.value = true
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    subs.value = r.items
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载频道失败')
  } finally {
    subsLoading.value = false
  }
}

async function runSub(id: string) {
  try {
    const r = await api<{ delivered: number; matched: number; scanned: number }>(`/subs/${id}/run`, { method: 'POST' })
    msg.success(`扫描 ${r.scanned} / 命中 ${r.matched} / 推送 ${r.delivered}`)
    loadSubs()
  } catch (e: any) {
    const detail = e?.data?.detail || e?.message || '运行失败'
    msg.error(typeof detail === 'string' ? detail : '运行失败，请检查后端日志')
  }
}

async function toggleActive(row: Subscription, v: boolean) {
  try {
    await api(`/subs/${row.id}`, { method: 'PATCH', body: { is_active: v } })
    row.is_active = v
    msg.success(v ? '已启用' : '已暂停')
  } catch (e: any) {
    msg.error(e?.data?.detail || '更新失败')
  }
}

async function deleteSub(id: string) {
  try {
    await api(`/subs/${id}`, { method: 'DELETE' })
    msg.success('已删除')
    loadSubs()
  } catch (e: any) {
    msg.error(e?.data?.detail || '删除失败')
  }
}

// ==================== 推送设置 ====================
// Day 7:从后端 /notifier/channels 取 available 列表,跟 settings 真同步
type BackendChannel = {
  name: string
  label: string
  required_fields: string[]
  available: boolean
}

type FeishuHook = {
  name: string
  webhook: string
}

const setting = ref({
  feishu_webhooks: [] as FeishuHook[],
  channels: ['inbox'] as string[],
})
const availableChannels = ref<BackendChannel[]>([])
const settingsLoading = ref(false)
const savingSettings = ref(false)
/** 正在测试的飞书群下标;null=空闲 */
const testingFeishuIdx = ref<number | null>(null)

function normalizeFeishuHooks(me: any): FeishuHook[] {
  if (Array.isArray(me?.feishu_webhooks) && me.feishu_webhooks.length) {
    return me.feishu_webhooks.filter((h: any) => h?.webhook)
  }
  if (me?.feishu_webhook) {
    return [{ name: '默认群', webhook: me.feishu_webhook }]
  }
  return []
}

function addFeishuHook() {
  setting.value.feishu_webhooks.push({ name: '', webhook: '' })
}

function removeFeishuHook(idx: number) {
  setting.value.feishu_webhooks.splice(idx, 1)
}

async function loadSettings() {
  settingsLoading.value = true
  try {
    const [cs, me] = await Promise.all([
      api<{ channels: BackendChannel[] }>('/notifier/channels'),
      api<any>('/settings'),
    ])
    availableChannels.value = (cs.channels || []).filter(c => c.available)
    setting.value.feishu_webhooks = normalizeFeishuHooks(me)
    setting.value.channels = me.channels || ['inbox']
  } catch (e: any) {
    msg.error('加载设置失败: ' + (e?.data?.detail || ''))
  } finally {
    settingsLoading.value = false
  }
}

async function saveSettings() {
  savingSettings.value = true
  try {
    const body: Record<string, any> = {
      feishu_webhooks: setting.value.feishu_webhooks.filter(h => !!h.webhook),
      default_channels: setting.value.channels,
    }
    const r = await api<any>('/settings', { method: 'PUT', body })
    if (r.ok === false) {
      msg.warning(r.message || '没有字段被更新')
    } else {
      msg.success('推送配置已保存')
    }
  } catch (e: any) {
    msg.error('保存失败: ' + (e?.data?.detail || e?.message || '未知错误'))
  } finally {
    savingSettings.value = false
  }
}

/** 按群维度测试飞书:只推当前这一行的 webhook,可测未保存输入 */
async function testFeishuGroup(idx: number) {
  const hook = setting.value.feishu_webhooks[idx]
  if (!hook?.webhook) {
    msg.warning('请先填写该群的 Webhook')
    return
  }
  testingFeishuIdx.value = idx
  try {
    // 先落盘全部配置,避免测通后刷新丢失
    await api<any>('/settings', {
      method: 'PUT',
      body: {
        feishu_webhooks: setting.value.feishu_webhooks.filter(h => !!h.webhook),
        default_channels: setting.value.channels,
      },
    })
    const r = await api<any>('/notifier/test', {
      method: 'POST',
      body: {
        channel: 'feishu',
        feishu_webhook: hook.webhook,
        feishu_name: hook.name || `群${idx + 1}`,
        feishu_index: idx,
      },
    })
    const label = hook.name || `群${idx + 1}`
    if (r.ok) {
      msg.success(`群「${label}」测试通过${r.message ? ': ' + r.message : ''}`)
    } else {
      msg.error(`群「${label}」测试失败: ${r.message || '请检查 webhook'}`)
    }
  } catch (e: any) {
    msg.error('测试失败: ' + (e?.data?.detail || e?.message || ''))
  } finally {
    testingFeishuIdx.value = null
  }
}

onMounted(() => {
  loadSubs()
  loadSettings()
  loadRecentPush()
})
</script>
