<template>
  <div class="container mx-auto p-6 max-w-3xl">
    <h1 class="text-2xl font-bold mb-6">⚙️ 推送配置 / Settings</h1>

    <!-- Feishu OAuth binding (Day 7 v0.4.1) -->
    <div class="bg-white shadow rounded p-4 mb-4">
      <h2 class="font-semibold mb-3 flex items-center gap-2">
        🧜‍ 飞书绑定 (OAuth)
        <span v-if="feishu.bound" class="text-green-600 text-sm">✓ 已绑定</span>
        <span v-else class="text-gray-400 text-sm">未绑定</span>
      </h2>
      <div v-if="feishu.bound" class="text-sm">
        <p><strong>{{ feishu.name || '(未设名)' }}</strong> <span class="text-gray-500">{{ feishu.email }}</span></p>
        <p class="text-xs text-gray-400 font-mono break-all">{{ feishu.open_id }}</p>
        <p class="text-xs text-gray-400">绑定时间: {{ feishu.bind_at }}</p>
        <button @click="unbind" class="mt-2 px-3 py-1 bg-red-50 text-red-600 rounded text-sm">
          解绑
        </button>
      </div>
      <div v-else>
        <p class="text-sm text-gray-600 mb-3">绑定后可开启“飞书个人单聊”推送,无需手填 open_id。</p>
        <button @click="bindFeishu" :disabled="binding" class="bg-blue-600 text-white px-4 py-2 rounded">
          {{ binding ? '正在跳转飞书...' : '🔵 绑定飞书账号' }}
        </button>
      </div>
    </div>

    <div v-if="msg" :class="msgClass" class="p-3 rounded mb-4">{{ msg }}</div>

    <!-- Channels overview -->
    <div class="bg-white shadow rounded p-4 mb-4">
      <h2 class="font-semibold mb-3">5 个推送渠道</h2>
      <table class="w-full text-sm">
        <thead><tr class="text-left border-b">
          <th class="py-2">渠道</th><th>需要字段</th><th>已配</th><th>测试</th>
        </tr></thead>
        <tbody>
          <tr v-for="ch in channels" :key="ch.name" class="border-b">
            <td class="py-2 font-medium">{{ ch.label }}<br><span class="text-xs text-gray-400">{{ ch.name }}</span></td>
            <td class="text-xs text-gray-600">
              <code v-for="f in ch.required_fields" :key="f" class="mr-1">{{ f }}</code>
              <span v-if="!ch.required_fields.length" class="text-gray-400">(自动)</span>
            </td>
            <td>
              <span v-if="isConfigured(ch.name)" class="text-green-600">✓</span>
              <span v-else class="text-gray-400">-</span>
            </td>
            <td>
              <button
                v-if="ch.required_fields.length"
                @click="testChannel(ch.name)"
                :disabled="testing === ch.name"
                class="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded disabled:opacity-50">
                {{ testing === ch.name ? '...' : '测试' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- SMTP Email -->
    <!-- Feishu DM(Day 7 v0.4.0) -->
    <div class="bg-white shadow rounded p-4 mb-4">
      <h3 class="font-semibold mb-3">🧜‍ 飞书个人单聊 (feishu_dm)</h3>
      <p class="text-xs text-gray-500 mb-3">直接推到你的飞书手机客户端，不需要加群。需 LARK_APP_ID+LARK_APP_SECRET 环境变量以及 app <code>im:message</code> 权限。</p>
      <label class="block text-sm">你的飞书 open_id（留空 = 默认当前用户）
        <input v-model="form.feishu_open_id" class="border rounded w-full px-2 py-1 font-mono" placeholder="ou_留空自动 / ou_xxxxxxx 手填" />
      </label>
    </div>

    <div class="bg-white shadow rounded p-4 mb-4">
      <h3 class="font-semibold mb-3">📧 邮箱 SMTP （QQ / 126 / Gmail）</h3>
      <div class="grid grid-cols-2 gap-3 text-sm">
        <label>SMTP 主机<input v-model="form.smtp_host" class="border rounded w-full px-2 py-1" /></label>
        <label>SMTP 端口<input v-model.number="form.smtp_port" type="number" class="border rounded w-full px-2 py-1" /></label>
        <label>SMTP 用户(你的邮箱)<input v-model="form.smtp_user" class="border rounded w-full px-2 py-1" /></label>
        <label>SMTP 授权码(不是密码!)<input v-model="form.smtp_pass" type="password" class="border rounded w-full px-2 py-1" placeholder="留空 = 不改" /></label>
        <label class="col-span-2">收件邮箱<input v-model="form.email" type="email" class="border rounded w-full px-2 py-1" /></label>
      </div>
      <p class="text-xs text-gray-500 mt-2">💡 Gmail 用"应用专用密码",QQ/126 用"授权码"</p>
    </div>

    <!-- Webhooks -->
    <div class="bg-white shadow rounded p-4 mb-4">
      <h3 class="font-semibold mb-3">🤖 机器人 Webhook</h3>
      <div class="space-y-3 text-sm">
        <label class="block">飞书机器人 webhook
          <input v-model="form.feishu_webhook" class="border rounded w-full px-2 py-1 font-mono" placeholder="https://open.feishu.cn/hook/..." />
        </label>
        <label class="block">企业微信机器人 webhook
          <input v-model="form.wechat_webhook" class="border rounded w-full px-2 py-1 font-mono" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/..." />
        </label>
        <label class="block">通用 webhook
          <input v-model="form.webhook_url" class="border rounded w-full px-2 py-1 font-mono" placeholder="https://your-server.example/webhook" />
        </label>
      </div>
    </div>

    <!-- Channels default -->
    <div class="bg-white shadow rounded p-4 mb-4">
      <h3 class="font-semibold mb-3">📡 默认推送渠道(订阅触发时用)</h3>
      <div class="flex gap-4 flex-wrap">
        <label v-for="ch in ['inbox','email','feishu','wechat','webhook']" :key="ch" class="flex items-center gap-1">
          <input type="checkbox" :value="ch" v-model="form.channels" />
          {{ ch }}
        </label>
      </div>
    </div>

    <button @click="save" :disabled="saving" class="bg-blue-600 text-white px-6 py-2 rounded disabled:opacity-50">
      {{ saving ? '保存中...' : '保存配置' }}
    </button>

    <p class="text-xs text-gray-400 mt-4">
      改完 → 点"测试"按钮验证渠道是否通 → 通过后下次订阅触发就会真的推到这里。
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ofetch } from 'ofetch'

const channels = ref([])
const feishu = ref({ bound: false, name: '', open_id: '', bind_at: '', email: '' })
const form = ref({
  email: '', smtp_host: 'smtp.qq.com', smtp_port: 465,
  smtp_user: '', smtp_pass: '',
  feishu_webhook: '', wechat_webhook: '', webhook_url: '',
  channels: ['inbox']
})
const msg = ref('')
const binding = ref(false)
const msgClass = ref('bg-yellow-50 text-yellow-800')
const msgClass = ref('bg-yellow-50 text-yellow-800')
const saving = ref(false)
const testing = ref(null)

async function bindFeishu() {
  binding.value = true
  try {
    const r = await ofetch('/api/auth/feishu/bind')
    window.location.href = r.oauth_url
  } catch (e) {
    binding.value = false
    showMsg('绑定启动失败:' + (e.data || e.message), 'bg-red-50 text-red-800')
  }
}

async function unbind() {
  if (!confirm('解绑后 feishu_dm 推送会失败,确定?')) return
  try {
    await ofetch('/api/auth/feishu/unbind', { method: 'POST' })
    await load()
    showMsg('✓ 已解绑', 'bg-green-50 text-green-800')
  } catch (e) {
    showMsg('解绑失败:' + e.message, 'bg-red-50 text-red-800')
  }
}

function isConfigured(name) {
  if (name === 'inbox') return true
  if (name === 'email') return !!form.value.email && !!form.value.smtp_user && !!form.value.smtp_pass
  if (name === 'feishu') return !!form.value.feishu_webhook
  if (name === 'wechat') return !!form.value.wechat_webhook
  if (name === 'webhook') return !!form.value.webhook_url
  return false
}

async function load() {
  try {
    const [cs, me, fb] = await Promise.all([
      ofetch('/api/notifier/channels'),
      ofetch('/api/settings'),
      ofetch('/api/auth/feishu/status'),
    ])
    channels.value = cs.channels
    form.value = { ...form.value, ...me, smtp_pass: '' }
    form.value.channels = me.channels || ['inbox']
    feishu.value = { ...feishu.value, ...fb }
    // 如果已绑定，自动启用 feishu_dm
    if (fb.bound && !form.value.channels.includes('feishu_dm')) {
      form.value.channels.push('feishu_dm')
    }
    // 处理 callback 参数
    const u = new URL(window.location.href)
    if (u.searchParams.get('feishu_bind') === '1') {
      showMsg('✓ 飞书绑定成功,feishu_dm 已启用', 'bg-green-50 text-green-800')
      u.searchParams.delete('feishu_bind')
      window.history.replaceState({}, '', u.pathname)
    }
  } catch (e) { showMsg('加载失败:' + e.message, 'bg-red-50 text-red-800') }
}

async function save() {
  saving.value = true
  try {
    await ofetch('/api/settings', { method: 'PUT', body: form.value })
    showMsg('✓ 已保存', 'bg-green-50 text-green-800')
  } catch (e) { showMsg('保存失败:' + e.message, 'bg-red-50 text-red-800') }
  finally { saving.value = false }
}

async function testChannel(name) {
  testing.value = name
  try {
    const r = await ofetch('/api/notifier/test', { method: 'POST', body: { channel: name } })
    showMsg(`${name}: ${r.ok ? '✓ 成功' : '✗ ' + r.message}`, r.ok ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800')
  } catch (e) { showMsg('测试失败:' + e.message, 'bg-red-50 text-red-800') }
  finally { testing.value = null }
}

function showMsg(m, cls) {
  msg.value = m
  msgClass.value = cls
  setTimeout(() => { msg.value = '' }, 4000)
}

onMounted(load)
</script>
