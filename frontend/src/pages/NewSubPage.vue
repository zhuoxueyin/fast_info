<template>
  <div class="max-w-xl mx-auto pb-12">
    <h1 class="text-2xl font-bold text-slate-900 mb-2">新建订阅</h1>

    <!-- Step 1: 说说你想看啥 -->
    <div v-if="step === 1" class="bg-white rounded-xl border border-slate-200 p-6 mt-4">
      <label class="text-sm text-slate-600 mb-2 block">描述你想看什么</label>
      <n-input
        v-model:value="nl"
        type="textarea"
        placeholder="例:每天 9 点看 AI 资讯"
        :autosize="{ minRows: 3, maxRows: 5 }"
      />
      <p class="text-xs text-slate-400 mt-2 mb-4">系统会自动识别时间 / 关键词 / 类目</p>

      <n-button type="primary" block :loading="parsing" @click="onParse">
        下一步
      </n-button>
    </div>

    <!-- Step 2: 确认 & 调整 -->
    <div v-else-if="step === 2 && parsed" class="space-y-4 mt-4">
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <n-form-item label="名称">
          <n-input v-model:value="form.title" placeholder="我的 AI 订阅" />
        </n-form-item>

        <n-form-item label="关键词">
          <n-input v-model:value="form.keywords" placeholder="AI, 大模型, GPT" />
        </n-form-item>

        <!-- 二级类目 -->
        <n-form-item label="分类">
          <div class="w-full">
            <div class="flex flex-wrap gap-1 mb-2">
              <button
                v-for="cat in l1List"
                :key="cat"
                class="text-sm px-3 py-1 rounded-full border transition"
                :class="form.categories_l1.includes(cat)
                  ? 'bg-emerald-500 text-white border-emerald-500'
                  : 'border-slate-300 text-slate-700 hover:border-emerald-400'"
                @click="toggleL1(cat)"
              >
                {{ cat }}
              </button>
            </div>
            <div v-if="form.categories_l1.length" class="flex flex-wrap gap-1 mt-2">
              <button
                v-for="l2 in availableL2"
                :key="l2"
                class="text-xs px-2 py-1 rounded-full border transition"
                :class="form.categories_l2.includes(l2)
                  ? 'bg-blue-500 text-white border-blue-500'
                  : 'border-slate-200 text-slate-600 hover:border-blue-300'"
                @click="toggleL2(l2)"
              >
                {{ l2 }}
              </button>
            </div>
          </div>
        </n-form-item>

        <n-form-item label="推送频率">
          <div class="flex gap-2 items-center w-full">
            <n-select v-model:value="form.freq_mode" :options="freqOptions" class="!w-32" />
            <n-input-number
              v-if="form.freq_mode === 'interval'"
              v-model:value="form.interval_min"
              :min="10" :max="1440"
              class="!w-24"
            />
            <n-input
              v-if="form.freq_mode === 'cron'"
              v-model:value="form.cron_expr"
              placeholder="0 9 * * *"
              class="!w-32"
            />
            <span class="text-xs text-slate-500">{{ freqHint }}</span>
          </div>
        </n-form-item>

        <n-form-item label="最多">
          <div class="flex items-center gap-2">
            <n-input-number v-model:value="form.max_items" :min="1" :max="30" class="!w-24" />
            <span class="text-sm text-slate-600">条 / 次</span>
          </div>
        </n-form-item>

        <n-form-item label="推送渠道">
          <n-checkbox-group v-model:value="form.channels" class="!flex !gap-3">
            <n-checkbox value="inbox">站内</n-checkbox>
            <n-checkbox value="email">邮件</n-checkbox>
            <n-checkbox value="feishu">飞书</n-checkbox>
            <n-checkbox value="wechat">企微</n-checkbox>
            <n-checkbox value="webhook">Webhook</n-checkbox>
          </n-checkbox-group>
        </n-form-item>

        <div class="flex gap-3 mt-6">
          <n-button @click="step = 1">上一步</n-button>
          <n-button type="primary" :loading="saving" @click="onSave">保存订阅</n-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  NInput, NInputNumber, NButton, NFormItem,
  NSelect, NCheckbox, NCheckboxGroup, useMessage,
} from 'naive-ui'
import { useAuthStore } from '@/store/auth'
import { api } from '@/lib/api'

const router = useRouter()
const auth = useAuthStore()
const msg = useMessage()

const step = ref(1)
const nl = ref('每天 9 点看 AI 资讯')
const parsing = ref(false)
const saving = ref(false)
const parsed = ref<any>(null)

const l1List = ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他']
const l2Map: Record<string, string[]> = {
  科技: ['互联网', '硬件', '数码评测', '科技融资', '开源'],
  AI: ['大模型', 'AI芯片', 'AI应用', 'AI框架', '机器人'],
  体育: ['足球', '篮球', '电竞'],
  娱乐: ['影视', '音乐', '综艺', '动漫'],
  财经: ['宏观', 'A股', '美股', '港股', '币圈', '创业'],
  汽车: ['新能源', '自动驾驶', '新势力', '传统车企'],
  其他: ['其他'],
}

const form = ref({
  title: '',
  keywords: '',
  categories_l1: [] as string[],
  categories_l2: [] as string[],
  freq_mode: 'cron' as 'cron' | 'interval',
  cron_expr: '0 9 * * *',
  interval_min: 60,
  max_items: 10,
  channels: ['inbox'],
})

const freqOptions = [
  { label: '定时', value: 'cron' },
  { label: '每 N 分钟', value: 'interval' },
]

const availableL2 = computed(() => {
  const set = new Set<string>()
  for (const l1 of form.value.categories_l1) {
    for (const l2 of l2Map[l1] || []) set.add(l2)
  }
  return Array.from(set)
})

const freqHint = computed(() => {
  if (form.value.freq_mode === 'interval') return `每 ${form.value.interval_min} 分钟一次`
  return '默认每天 9 点(可改 cron)'
})

function toggleL1(cat: string) {
  const i = form.value.categories_l1.indexOf(cat)
  if (i >= 0) {
    form.value.categories_l1.splice(i, 1)
    // 同步移除其 L2
    form.value.categories_l2 = form.value.categories_l2.filter(l2 => !(l2Map[cat] || []).includes(l2))
  } else {
    form.value.categories_l1.push(cat)
  }
}
function toggleL2(l2: string) {
  const i = form.value.categories_l2.indexOf(l2)
  if (i >= 0) form.value.categories_l2.splice(i, 1)
  else form.value.categories_l2.push(l2)
}

async function onParse() {
  if (!nl.value.trim()) {
    msg.warning('先写一句话描述吧')
    return
  }
  parsing.value = true
  try {
    const r = await api<any>('/subs/parse', { method: 'POST', body: { nl_query: nl.value } })
    parsed.value = r
    form.value.title = r.title || nl.value.slice(0, 15)
    form.value.keywords = (r.keywords || []).join(', ')
    form.value.categories_l1 = r.categories_l1 || []
    form.value.categories_l2 = r.categories_l2 || []
    form.value.cron_expr = r.cron_expr || '0 9 * * *'
    form.value.max_items = r.max_items || 10
    form.value.channels = r.channels || ['inbox']
    if (r.interval_min) {
      form.value.freq_mode = 'interval'
      form.value.interval_min = r.interval_min
    }
    step.value = 2
  } catch (e: any) {
    msg.warning('自动解析失败,直接填表即可')
    parsed.value = { fallback: true }
    form.value.title = nl.value.slice(0, 15)
    form.value.keywords = nl.value.replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, ' ').split(/\s+/).filter(Boolean).slice(0, 5).join(', ')
    step.value = 2
  } finally {
    parsing.value = false
  }
}

async function onSave() {
  if (!form.value.title.trim()) {
    msg.warning('起个名字')
    return
  }
  saving.value = true
  try {
    const body: any = {
      title: form.value.title,
      nl_query: nl.value,
      keywords: form.value.keywords.split(/[,，\s]+/).filter(Boolean),
      categories_l1: form.value.categories_l1,
      categories_l2: form.value.categories_l2,
      max_items: form.value.max_items,
      channels: form.value.channels,
    }
    if (form.value.freq_mode === 'interval') {
      body.interval_min = form.value.interval_min
      body.cron_expr = '* * * * *'
    } else {
      body.cron_expr = form.value.cron_expr
      body.interval_min = 0
    }
    await api('/subs', { method: 'POST', body })
    msg.success('已创建')
    router.push('/me')
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>