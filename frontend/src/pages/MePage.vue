<template>
  <div class="max-w-3xl mx-auto pb-12">
    <!-- 用户头像区 -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6 flex items-center gap-4">
      <div class="w-14 h-14 rounded-full bg-emerald-500 text-white text-2xl font-bold flex items-center justify-center">
        {{ auth.user?.username?.[0]?.toUpperCase() || 'A' }}
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <span class="text-lg font-semibold text-slate-900">{{ auth.user?.username || 'admin' }}</span>
          <n-tag size="small" type="info" :bordered="false">{{ auth.user?.role || 'user' }}</n-tag>
          <n-tag size="small" :bordered="false">套餐: {{ auth.user?.plan || 'free' }}</n-tag>
        </div>
        <div class="text-sm text-slate-500 mt-1">
          📧 {{ auth.user?.email || '未设置邮箱' }}
        </div>
      </div>
    </section>

    <!-- ==================== 区域1: 我的订阅 ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-6 mb-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-slate-900">📡 我的订阅 ({{ subs.length }})</h2>
        <n-button type="primary" size="small" @click="$router.push('/subs/new')">➕ 新增订阅</n-button>
      </div>

      <!-- 订阅列表 -->
      <div v-if="subsLoading" class="text-center text-slate-400 py-6">加载中…</div>

      <div v-else-if="!subs.length" class="text-center py-8">
        <n-empty description="还没有订阅">
          <template #extra>
            <n-button type="primary" @click="$router.push('/subs/new')">创建第一个订阅</n-button>
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
            <n-button size="tiny" @click="runSub(s.id)">▶</n-button>
            <n-popconfirm @positive-click="deleteSub(s.id)">
              <template #trigger>
                <n-button size="tiny" type="error" ghost>删除</n-button>
              </template>
              确定删除这个订阅?
            </n-popconfirm>
          </div>
        </div>
      </div>
    </section>

    <!-- ==================== 区域2: 推送设置 ==================== -->
    <section class="bg-white rounded-xl border border-slate-200 p-6">
      <h2 class="text-lg font-semibold text-slate-900 mb-4">⚙️ 推送设置</h2>

      <!-- 飞书群机器人 (Webhook) -->
      <div class="mb-6 p-4 bg-slate-50 rounded-lg">
        <h3 class="font-semibold text-slate-800 mb-3 flex items-center gap-2">
          🤖 飞书群机器人
          <n-tag v-if="setting.feishu_webhook" type="success" size="small" :bordered="false">✓ 已配置</n-tag>
          <n-tag v-else size="small" :bordered="false">未配置</n-tag>
        </h3>
        <p class="text-xs text-slate-500 mb-3">
          在飞书群中添加「自定义机器人」，获取 Webhook 地址后填入下方。
        </p>
        <n-form-item label="Webhook 地址">
          <n-input
            v-model:value="setting.feishu_webhook"
            placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
          />
        </n-form-item>
        <div class="flex gap-2 mt-2">
          <n-button
            size="small"
            :disabled="!setting.feishu_webhook"
            :loading="testingFeishu"
            @click="testChannel('feishu')"
          >
            测试推送
          </n-button>
        </div>
      </div>

      <!-- 默认推送渠道 -->
      <div class="mb-4">
        <h3 class="font-semibold text-slate-800 mb-3">📡 默认推送渠道（新建订阅时默认勾选）</h3>
        <n-checkbox-group v-model:value="setting.channels">
          <n-space>
            <n-checkbox value="inbox">站内</n-checkbox>
            <n-checkbox value="feishu">飞书群机器人</n-checkbox>
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
import { ref, onMounted } from 'vue'
import {
  NButton, NEmpty, NTag, NSwitch,
  NInput, NFormItem,
  NCheckbox, NCheckboxGroup, NSpace, NPopconfirm, useMessage,
} from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import { api } from '@/lib/api'
import type { Subscription } from '@/types/api'

const auth = useAuthStore()
const msg = useMessage()

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
    msg.error(e?.data?.detail || '加载订阅失败')
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
const setting = ref({
  feishu_webhook: '',
  channels: ['inbox'] as string[],
})
const settingsLoading = ref(false)
const savingSettings = ref(false)
const testingFeishu = ref(false)

async function loadSettings() {
  settingsLoading.value = true
  try {
    const r = await api<any>('/settings')
    setting.value.feishu_webhook = r.feishu_webhook || ''
    setting.value.channels = r.channels || ['inbox']
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
      feishu_webhook: setting.value.feishu_webhook,
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

async function testChannel(name: string) {
  if (name === 'feishu') testingFeishu.value = true
  try {
    const body: Record<string, any> = {
      feishu_webhook: setting.value.feishu_webhook,
      default_channels: setting.value.channels,
    }
    await api<any>('/settings', { method: 'PUT', body })

    const r = await api<any>('/notifier/test', { method: 'POST', body: { channel: name } })
    if (r.ok) {
      msg.success(`飞书群机器人 测试通过`)
    } else {
      msg.error(`测试失败: ${r.message || '请检查配置'}`)
    }
  } catch (e: any) {
    msg.error('测试失败: ' + (e?.data?.detail || e?.message || ''))
  } finally {
    testingFeishu.value = false
  }
}

onMounted(() => {
  loadSubs()
  loadSettings()
})
</script>
