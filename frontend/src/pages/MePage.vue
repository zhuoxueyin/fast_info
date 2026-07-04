<template>
  <div>
    <div class="flex items-center gap-4 mb-6">
      <div class="w-16 h-16 rounded-full bg-emerald-500 text-white text-2xl flex items-center justify-center font-bold">
        {{ auth.user?.username?.[0]?.toUpperCase() || '?' }}
      </div>
      <div>
        <h1 class="text-2xl font-bold text-slate-900">{{ auth.user?.username }}</h1>
        <p class="text-sm text-slate-500">
          {{ auth.user?.role === 'admin' ? '🔧 管理员' : '普通用户' }}
          · {{ auth.user?.plan || 'free' }} 套餐
          · {{ auth.user?.email || '未设置邮箱' }}
        </p>
      </div>
      <div class="ml-auto flex gap-2">
        <n-button @click="$router.push('/me/inbox')">📥 推送</n-button>
        <n-button @click="$router.push('/m/me/inbox')">📱 移动版</n-button>
        <n-button type="primary" @click="$router.push('/subs/new')">➕ 新建</n-button>
      </div>
    </div>

    <!-- 推送渠道配置 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h2 class="text-lg font-semibold mb-2">📡 推送渠道配置</h2>
      <p class="text-xs text-slate-500 mb-4">配置后,在新建/编辑订阅时选择对应渠道即可接收推送。<span class="text-amber-600">邮件推送需管理员配置SMTP,飞书/企微/Webhook由用户自行填入webhook。</span></p>
      <div class="bg-emerald-50 border border-emerald-200 rounded p-3 mb-4 text-sm flex items-center justify-between">
        <div>
          <strong>🚀 想推送到你自己飞书?</strong>
          <span class="text-slate-500 text-xs ml-2">点下面按钮 → 飞书授权 → 以后订阅触发直接发到你手机</span>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="feishuBind.bound" class="text-emerald-600">✓ 已绑定 <code class="text-xs">{{ feishuBind.open_id?.slice(0, 12) }}…</code></span>
          <n-button type="primary" size="small" @click="goBindFeishu">{{ feishuBind.bound ? '重新绑定' : '绑定飞书个人账号' }}</n-button>
          <n-button v-if="feishuBind.bound" size="small" @click="unbindFeishu">解绑</n-button>
        </div>
      </div>

      <div class="grid gap-5 md:grid-cols-2">
        <div class="border border-slate-100 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">📧</span>
            <span class="font-medium">邮件</span>
            <n-tag size="small" :bordered="false" type="success" v-if="profile.email">已配置</n-tag>
            <n-tag size="small" :bordered="false" v-else>未配置</n-tag>
          </div>
          <n-input
            v-model:value="form.email"
            placeholder="your@example.com"
            clearable
            @blur="saveProfile"
          />
          <p class="text-xs text-slate-400 mt-2">需管理员在服务器配置 SMTP_HOST/SMTP_USER/SMTP_PASS 环境变量后生效</p>
        </div>

        <div class="border border-slate-100 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">💬</span>
            <span class="font-medium">飞书群机器人</span>
            <n-tag size="small" :bordered="false" type="success" v-if="profile.feishu_webhook">已配置</n-tag>
            <n-tag size="small" :bordered="false" v-else>未配置</n-tag>
          </div>
          <n-input
            v-model:value="form.feishu_webhook"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
            clearable
            @blur="saveProfile"
          />
          <p class="text-xs text-slate-400 mt-2">飞书群 → 设置 → 群机器人 → 添加自定义机器人 → 复制 webhook 地址</p>
        </div>

        <div class="border border-slate-100 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🏢</span>
            <span class="font-medium">企业微信群机器人</span>
            <n-tag size="small" :bordered="false" type="success" v-if="profile.wechat_webhook">已配置</n-tag>
            <n-tag size="small" :bordered="false" v-else>未配置</n-tag>
          </div>
          <n-input
            v-model:value="form.wechat_webhook"
            placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
            clearable
            @blur="saveProfile"
          />
          <p class="text-xs text-slate-400 mt-2">企微群 → 右上角... → 添加群机器人 → 新建 → 复制 webhook 地址</p>
        </div>

        <div class="border border-slate-100 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-3">
            <span class="text-lg">🔗</span>
            <span class="font-medium">通用 Webhook</span>
            <n-tag size="small" :bordered="false" type="success" v-if="profile.webhook_url">已配置</n-tag>
            <n-tag size="small" :bordered="false" v-else>未配置</n-tag>
          </div>
          <n-input
            v-model:value="form.webhook_url"
            placeholder="https://your-server.com/hook"
            clearable
            @blur="saveProfile"
          />
          <p class="text-xs text-slate-400 mt-2">推送时会 POST JSON {subject, content_html, items[], username} 到此地址</p>
        </div>
      </div>

      <n-button type="primary" class="mt-4" @click="saveProfile" :loading="saving">💾 保存配置</n-button>
    </section>

    <!-- 我的订阅 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6">
      <h2 class="text-lg font-semibold mb-4">📡 我的订阅</h2>
      <n-data-table
        v-if="subs.length"
        :columns="cols"
        :data="subs"
        :pagination="false"
        :bordered="false"
      />
      <n-empty v-else description="还没有订阅,去创建一个吧" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, reactive } from 'vue'
import { NButton, NDataTable, NEmpty, useMessage, NPopconfirm, NSwitch, NTag, NInput, type DataTableColumns } from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import { api, startFeishuBind, getFeishuBindStatus, unbindFeishu } from '@/lib/api'
import type { Subscription, User } from '@/types/api'

const auth = useAuthStore()
const msg = useMessage()
const subs = ref<Subscription[]>([])
const saving = ref(false)
const profile = reactive<User>({ id: '', username: '', email: '', feishu_webhook: '', wechat_webhook: '', webhook_url: '' })
const form = reactive({ email: '', feishu_webhook: '', wechat_webhook: '', webhook_url: '' })

const cols: DataTableColumns<Subscription> = [
  { title: '标题', key: 'title', width: 160 },
  { title: 'NL', key: 'nl_query', ellipsis: { tooltip: true }, width: 180 },
  {
    title: '关键词', key: 'keywords', width: 180,
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      row.keywords.slice(0, 4).map(k => h(NTag, { type: 'success', size: 'small' }, () => k))),
  },
  {
    title: '类目', key: 'categories_l1',
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      (row.categories_l1 || []).map(c => h(NTag, { size: 'small', type: 'info' }, () => c))),
  },
  {
    title: '频率', key: 'freq', width: 90,
    render: (row: Subscription) => row.interval_min
      ? `每 ${row.interval_min}m`
      : (row.cron_expr || '0 9 * * *'),
  },
  {
    title: '渠道', key: 'channels', width: 100,
    render: (row: Subscription) => h('div', { class: 'flex flex-wrap gap-1' },
      (row.channels || ['inbox']).map(c => h(NTag, { size: 'small' }, () => chLabel(c)))),
  },
  {
    title: '启用', key: 'is_active', width: 80,
    render: (row: Subscription) => h(NSwitch, {
      value: row.is_active,
      onUpdateValue: (v: boolean) => toggleActive(row, v),
    }),
  },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row: Subscription) => h('div', { class: 'flex gap-2' }, [
      h(NButton, { size: 'small', onClick: () => runSub(row.id) }, () => '▶ 跑'),
      h(NPopconfirm, {
        onPositiveClick: () => deleteSub(row.id),
      }, {
        trigger: () => h(NButton, { size: 'small', type: 'error' }, () => '删'),
        default: () => '确定删除?',
      }),
    ]),
  },
]

function chLabel(c: string): string {
  return { inbox: '站内', email: '邮件', feishu: '飞书', wechat: '企微', webhook: 'Webhook' }[c] || c
}

async function load() {
  try {
    const r = await api<{ items: Subscription[] }>('/subs')
    subs.value = r.items
  } catch (e: any) {
    msg.error(e?.data?.detail || '加载失败')
  }
}

async function loadProfile() {
  try {
    const u = await api<User>('/auth/me')
    Object.assign(profile, u)
    form.email = u.email || ''
    form.feishu_webhook = u.feishu_webhook || ''
    form.wechat_webhook = u.wechat_webhook || ''
    form.webhook_url = u.webhook_url || ''
    if (auth.user) {
      Object.assign(auth.user, u)
    }
  } catch {}
}

// ===== 飞书 OAuth 单聊绑定 (Day 7 v0.4.1) =====
const feishuBind = ref<{ bound: boolean; open_id?: string; name?: string; avatar?: string; bind_at?: string }>({ bound: false })

async function loadFeishuBind() {
  try {
    const s = await getFeishuBindStatus()
    feishuBind.value = s as any
  } catch {}
}

async function goBindFeishu() {
  try {
    const r = await startFeishuBind()
    window.location.href = r.oauth_url
  } catch (e: any) {
    msg.error(e?.data?.detail || '跳转失败,去 /settings 页绑定')
  }
}

async function unbindFeishuAction() {
  if (!confirm('解绑后,个人单聊推送会失败,确定吗?')) return
  try {
    await unbindFeishu()
    await loadFeishuBind()
    msg.success('已解绑')
  } catch (e: any) {
    msg.error(e?.data?.detail || '解绑失败')
  }
}

async function saveProfile() {
  saving.value = true
  try {
    const u = await api<User>('/auth/me', {
      method: 'PATCH',
      body: {
        email: form.email || undefined,
        feishu_webhook: form.feishu_webhook || '',
        wechat_webhook: form.wechat_webhook || '',
        webhook_url: form.webhook_url || '',
      },
    })
    Object.assign(profile, u)
    if (auth.user) Object.assign(auth.user, u)
    msg.success('配置已保存')
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function runSub(id: string) {
  try {
    const r = await api<{ delivered: number; matched: number; scanned: number }>(`/subs/${id}/run`, { method: 'POST' })
    msg.success(`扫描 ${r.scanned} / 命中 ${r.matched} / 推送 ${r.delivered}`)
    load()
  } catch (e: any) {
    msg.error(e?.data?.detail || '运行失败')
  }
}

async function deleteSub(id: string) {
  try {
    await api(`/subs/${id}`, { method: 'DELETE' })
    msg.success('已删除')
    load()
  } catch (e: any) {
    msg.error(e?.data?.detail || '删除失败')
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

onMounted(() => {
  load()
  loadProfile()
  loadFeishuBind()
})
</script>
