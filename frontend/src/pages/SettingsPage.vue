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
        <!-- 飞书群机器人:支持多群 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="text-sm font-medium">飞书群机器人</label>
            <n-button size="tiny" @click="addFeishuHook">➕ 添加群</n-button>
          </div>
          <div
            v-for="(hook, idx) in form.feishu_webhooks"
            :key="idx"
            class="flex items-start gap-2 mb-2 p-3 bg-slate-50 rounded-lg"
          >
            <div class="flex-1 space-y-2">
              <n-input
                v-model:value="hook.name"
                placeholder="群名称(如: 技术早报群)"
                size="small"
              />
              <n-input
                v-model:value="hook.webhook"
                placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
                size="small"
              />
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
          <p v-if="!form.feishu_webhooks.length" class="text-xs text-slate-400">
            暂无飞书群机器人,点击上方按钮添加。
          </p>
          <p v-else class="text-xs text-slate-400">测试按群维度发送,只推到当前这一行的 webhook。</p>
        </div>
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
      <div class="flex items-baseline justify-between mb-3">
        <h3 class="font-semibold">📡 默认推送渠道（新建订阅时默认勾选）</h3>
        <span class="text-xs text-slate-400">未配置的渠道不会显示</span>
      </div>
      <n-checkbox-group v-model:value="form.channels">
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
      <p v-if="!availableChannels.length" class="text-xs text-slate-400 mt-2">
        💡 先在上面填好 webhook / SMTP 账号,这里就会出现对应渠道。
      </p>
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
  available: boolean
}

type FeishuHook = {
  name: string
  webhook: string
}

const msg = useMessage()
const channels = ref<PushChannel[]>([])        // 渠道总览表(全)
const availableChannels = ref<PushChannel[]>([])  // 仅 available=true,默认渠道勾选用
const form = ref({
  email: '', smtp_host: 'smtp.qq.com', smtp_port: 465,
  smtp_user: '', smtp_pass: '',
  feishu_webhooks: [] as FeishuHook[],
  wechat_webhook: '', webhook_url: '',
  channels: ['inbox'] as string[],
})
const loading = ref(false)
const saving = ref(false)
const testing = ref<string | null>(null)
/** 正在测试的飞书群下标 */
const testingFeishuIdx = ref<number | null>(null)

function addFeishuHook() {
  form.value.feishu_webhooks.push({ name: '', webhook: '' })
}

function removeFeishuHook(idx: number) {
  form.value.feishu_webhooks.splice(idx, 1)
}

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
    title: '测试', key: 'name', width: 100,
    render: (r: PushChannel) => {
      if (!r.required_fields.length) return h('span', { class: 'text-xs text-slate-300' }, '-')
      // 飞书改为上方「按群」测试,表格行只提示
      if (r.name === 'feishu') {
        return h('span', { class: 'text-xs text-slate-400' }, '按群测')
      }
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
  if (name === 'feishu') return form.value.feishu_webhooks.some(h => !!h.webhook)
  if (name === 'wechat') return !!form.value.wechat_webhook
  if (name === 'webhook') return !!form.value.webhook_url
  return false
}

function normalizeFeishuHooks(me: any): FeishuHook[] {
  if (Array.isArray(me?.feishu_webhooks) && me.feishu_webhooks.length) {
    return me.feishu_webhooks.filter((h: any) => h?.webhook)
  }
  // 兼容旧单字段
  if (me?.feishu_webhook) {
    return [{ name: '默认群', webhook: me.feishu_webhook }]
  }
  return []
}

async function load() {
  loading.value = true
  try {
    const [cs, me] = await Promise.all([
      api<{ channels: PushChannel[] }>('/notifier/channels'),
      api<any>('/settings'),
    ])
    channels.value = cs.channels
    // Day 7:默认推送渠道复选框只显示 available=true 的,跟 settings 一致
    availableChannels.value = (cs.channels || []).filter(c => c.available)
    form.value = { ...form.value, ...me, smtp_pass: '' }
    form.value.channels = me.channels || ['inbox']
    // Day 12:多飞书群机器人
    form.value.feishu_webhooks = normalizeFeishuHooks(me)
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
      feishu_webhooks: form.value.feishu_webhooks.filter(h => !!h.webhook),
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

/** 按群维度测试飞书:只推当前行 webhook */
async function testFeishuGroup(idx: number) {
  const hook = form.value.feishu_webhooks[idx]
  if (!hook?.webhook) {
    msg.warning('请先填写该群的 Webhook')
    return
  }
  testingFeishuIdx.value = idx
  try {
    // 先保存配置,避免测通后刷新丢失
    await api<any>('/settings', {
      method: 'PUT',
      body: {
        feishu_webhooks: form.value.feishu_webhooks.filter(h => !!h.webhook),
        default_channels: form.value.channels,
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
      await load()
    } else {
      msg.error(`群「${label}」测试失败: ${r.message || '请检查 webhook'}`)
    }
  } catch (e: any) {
    msg.error('测试失败: ' + (e?.data?.detail || e?.message || ''))
  } finally {
    testingFeishuIdx.value = null
  }
}

onMounted(load)
</script>
