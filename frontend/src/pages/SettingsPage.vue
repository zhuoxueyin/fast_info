<template>
  <div class="max-w-3xl mx-auto">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-slate-900">⚙️ 推送设置</h1>
      <n-button @click="$router.push('/me')">← 个人中心</n-button>
    </div>

    <!-- 渠道总览 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h2 class="text-lg font-semibold mb-3">📡 推送渠道</h2>
      <n-data-table
        :columns="channelCols"
        :data="channels"
        :bordered="false"
        :pagination="false"
        size="small"
      />
    </section>

    <!-- 邮箱 SMTP -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h3 class="font-semibold mb-4">📧 邮箱 SMTP</h3>
      <div class="grid grid-cols-2 gap-4">
        <n-form-item label="SMTP 主机">
          <n-input v-model:value="form.smtp_host" placeholder="smtp.qq.com" />
        </n-form-item>
        <n-form-item label="SMTP 端口">
          <n-input-number v-model:value="form.smtp_port" :min="1" :max="65535" />
        </n-form-item>
        <n-form-item label="SMTP 用户(你的邮箱)">
          <n-input v-model:value="form.smtp_user" placeholder="your@qq.com" />
        </n-form-item>
        <n-form-item label="SMTP 授权码">
          <n-input v-model:value="form.smtp_pass" type="password" placeholder="留空 = 不修改" />
        </n-form-item>
        <n-form-item label="收件邮箱" class="col-span-2">
          <n-input v-model:value="form.email" placeholder="your@example.com" />
        </n-form-item>
      </div>
      <p class="text-xs text-slate-400 mt-2">💡 Gmail 用"应用专用密码"，QQ/126 用"授权码"</p>
    </section>

    <!-- 机器人 Webhook -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h3 class="font-semibold mb-4">🤖 机器人 Webhook</h3>
      <div class="space-y-4">
        <n-form-item label="飞书群机器人 Webhook">
          <n-input v-model:value="form.feishu_webhook" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx" />
        </n-form-item>
        <n-form-item label="企业微信机器人 Webhook">
          <n-input v-model:value="form.wechat_webhook" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx" />
        </n-form-item>
        <n-form-item label="通用 Webhook">
          <n-input v-model:value="form.webhook_url" placeholder="https://your-server.example/webhook" />
        </n-form-item>
      </div>
    </section>

    <!-- 默认推送渠道 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <h3 class="font-semibold mb-3">📡 默认推送渠道（新建订阅时默认勾选）</h3>
      <n-checkbox-group v-model:value="form.channels">
        <n-space>
          <n-checkbox value="inbox">站内</n-checkbox>
          <n-checkbox value="email">邮件</n-checkbox>
          <n-checkbox value="feishu">飞书群机器人</n-checkbox>
          <n-checkbox value="wechat">企业微信</n-checkbox>
          <n-checkbox value="webhook">Webhook</n-checkbox>
        </n-space>
      </n-checkbox-group>
    </section>

    <!-- 保存 -->
    <div class="flex gap-3">
      <n-button type="primary" @click="save" :loading="saving" size="large">
        {{ saving ? '保存中...' : '💾 保存配置' }}
      </n-button>
      <n-button @click="load" :loading="loading">🔄 重新加载</n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  NButton, NInput, NInputNumber, NFormItem, NCheckbox, NCheckboxGroup,
  NTag, NSpace, NDataTable, useMessage, type DataTableColumns,
} from 'naive-ui'
import { api } from '@/lib/api'

type PushChannel = {
  name: string
  label: string
  required_fields: string[]
}

const msg = useMessage()
const channels = ref<PushChannel[]>([])
const form = ref({
  email: '', smtp_host: 'smtp.qq.com', smtp_port: 465,
  smtp_user: '', smtp_pass: '',
  feishu_webhook: '', wechat_webhook: '', webhook_url: '',
  channels: ['inbox'] as string[],
})
const loading = ref(false)
const saving = ref(false)
const testing = ref<string | null>(null)

const channelCols: DataTableColumns<PushChannel> = [
  { title: '渠道', key: 'label', width: 150 },
  { title: '需要字段', key: 'required_fields', render: (r: PushChannel) => h('span', { class: 'text-xs text-slate-500' }, r.required_fields.join(', ') || '(自动)') },
  {
    title: '已配置', key: 'name', width: 80,
    render: (r: PushChannel) => isConfigured(r.name)
      ? h('span', { class: 'text-green-600 font-bold' }, '✓')
      : h('span', { class: 'text-slate-300' }, '-'),
  },
  {
    title: '测试', key: 'name', width: 80,
    render: (r: PushChannel) => {
      if (!r.required_fields.length) return h('span', { class: 'text-xs text-slate-300' }, '-')
      return h(NButton, {
        size: 'tiny',
        loading: testing.value === r.name,
        disabled: !isConfigured(r.name),
        onClick: () => testChannel(r.name),
      }, () => '测试')
    },
  },
]

function isConfigured(name: string): boolean {
  if (name === 'inbox') return true
  if (name === 'email') return !!form.value.email && !!form.value.smtp_user && !!form.value.smtp_pass
  if (name === 'feishu') return !!form.value.feishu_webhook
  if (name === 'wechat') return !!form.value.wechat_webhook
  if (name === 'webhook') return !!form.value.webhook_url
  return false
}

async function load() {
  loading.value = true
  try {
    const [cs, me] = await Promise.all([
      api<{ channels: PushChannel[] }>('/notifier/channels'),
      api<any>('/settings'),
    ])
    channels.value = cs.channels
    form.value = { ...form.value, ...me, smtp_pass: '' }
    form.value.channels = me.channels || ['inbox']
  } catch (e: any) {
    msg.error('加载失败: ' + (e?.data?.detail || e?.message || '未知错误'))
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const body: Record<string, any> = {
      email: form.value.email || undefined,
      smtp_host: form.value.smtp_host,
      smtp_port: form.value.smtp_port,
      smtp_user: form.value.smtp_user,
      smtp_pass: form.value.smtp_pass || undefined,
      feishu_webhook: form.value.feishu_webhook,
      wechat_webhook: form.value.wechat_webhook,
      webhook_url: form.value.webhook_url,
      default_channels: form.value.channels,
    }
    const r = await api<any>('/settings', { method: 'PUT', body })
    if (r.ok === false) {
      msg.warning(r.message || '没有字段被更新')
    } else {
      msg.success('推送配置已保存')
      // 保存成功后刷新状态
      await load()
    }
  } catch (e: any) {
    msg.error('保存失败: ' + (e?.data?.detail || e?.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function testChannel(name: string) {
  testing.value = name
  try {
    const r = await api<any>('/notifier/test', { method: 'POST', body: { channel: name } })
    if (r.ok) {
      msg.success(`${name} 测试通过`)
    } else {
      msg.error(`${name} 测试失败: ${r.message || ''}`)
    }
  } catch (e: any) {
    msg.error('测试失败: ' + (e?.data?.detail || e?.message || ''))
  } finally {
    testing.value = null
  }
}

onMounted(load)
</script>
