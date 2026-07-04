<template>
  <div class="max-w-2xl mx-auto pb-12">
    <div class="flex items-center gap-3 mb-6">
      <h1 class="text-2xl font-bold text-slate-900">新增订阅</h1>
      <button class="text-slate-400 hover:text-slate-700 text-xl leading-none" @click="$router.back()">×</button>
    </div>

    <div class="flex items-center mb-8 text-sm">
      <span :class="step >= 1 ? 'text-emerald-600 font-medium' : 'text-slate-400'">1. 描述意图</span>
      <span class="mx-2 text-slate-300">→</span>
      <span :class="step >= 2 ? 'text-emerald-600 font-medium' : 'text-slate-400'">2. 调整规则</span>
      <span class="mx-2 text-slate-300">→</span>
      <span :class="step >= 3 ? 'text-emerald-600 font-medium' : 'text-slate-400'">3. 保存订阅</span>
    </div>

    <!-- Step 1: 描述意图 -->
    <div v-show="step === 1" class="min-h-[320px]">
      <section class="bg-white rounded-xl border border-slate-200 p-6">
        <label class="text-sm font-medium text-slate-700 mb-2 block">
          用一句话描述你想关注的内容<span class="text-rose-500">*</span>
        </label>
        <n-input
          v-model:value="nl"
          type="textarea"
          placeholder="例如：每天 9 点推送 AI 大模型和机器人最新进展"
          :autosize="{ minRows: 3, maxRows: 5 }"
          :status="nlError ? 'error' : undefined"
          :disabled="generating"
        />
        <p class="text-xs mt-2" :class="nlError ? 'text-rose-500' : 'text-slate-400'">
          {{ nlError || '系统会自动识别时间、关键词、分类和推送频率。' }}
        </p>

        <div class="mt-6 flex flex-wrap gap-2">
          <span class="text-xs text-slate-400 self-center">试试：</span>
          <button
            v-for="ex in examples"
            :key="ex"
            class="text-xs px-3 py-1 rounded-full border border-slate-200 text-slate-600 hover:border-emerald-400 hover:text-emerald-600 transition"
            :disabled="generating"
            @click="nl = ex"
          >
            {{ ex }}
          </button>
        </div>
      </section>

      <div class="flex gap-3 mt-6">
        <n-button class="!flex-1" :disabled="generating" @click="$router.back()">取消</n-button>
        <n-button type="primary" class="!flex-1" :loading="generating" @click="onGenerate">生成订阅规则</n-button>
      </div>
      <p v-if="generating" class="text-center text-xs text-slate-400 mt-4">正在理解你的意图，请稍候…</p>
    </div>

    <!-- Step 2: 调整规则 -->
    <div v-show="step === 2" class="min-h-[320px]">
      <section class="bg-emerald-50 rounded-xl border border-emerald-100 p-5 mb-5">
        <div class="text-sm font-medium text-emerald-800 mb-1">已识别你的意图</div>
        <div class="text-slate-700">{{ nl }}</div>
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">订阅名称</label>
        <n-input v-model:value="form.title" placeholder="给订阅起个名字" maxlength="30" show-count />
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">关键词</label>
        <n-input v-model:value="keywordText" placeholder="用逗号分隔多个关键词" />
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-3 block">分类</label>
        <div class="flex flex-wrap gap-2 mb-3">
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
        <div v-if="availableL2.length" class="flex flex-wrap gap-2">
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
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-3 block">推送频率</label>
        <div class="flex gap-2 items-center flex-wrap">
          <n-select v-model:value="form.freq_mode" :options="freqOptions" class="!w-28" />

          <template v-if="form.freq_mode === 'daily'">
            <n-input-number v-model:value="form.hour" :min="0" :max="23" class="!w-20" />
            <span class="text-slate-500">:</span>
            <n-input-number v-model:value="form.minute" :min="0" :max="59" :step="5" class="!w-20" />
            <span class="text-xs text-slate-500">{{ dailyHint }}</span>
          </template>

          <template v-else-if="form.freq_mode === 'weekly'">
            <n-select v-model:value="form.weeklyDay" :options="weekdayOptions" class="!w-24" />
            <n-input-number v-model:value="form.hour" :min="0" :max="23" class="!w-20" />
            <span class="text-slate-500">:</span>
            <n-input-number v-model:value="form.minute" :min="0" :max="59" :step="5" class="!w-20" />
            <span class="text-xs text-slate-500">{{ weeklyHint }}</span>
          </template>

          <template v-else-if="form.freq_mode === 'interval'">
            <n-input-number
              v-model:value="form.interval_min"
              :min="10" :max="1440" :step="10"
              class="!w-24"
            />
            <span class="text-xs text-slate-500">每 {{ form.interval_min }} 分钟一次</span>
          </template>

          <template v-else>
            <span class="text-xs text-slate-500">有新内容立即推送</span>
          </template>
        </div>
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">最多推送</label>
        <div class="flex items-center gap-2">
          <button
            class="w-9 h-9 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            :disabled="form.max_items <= 1"
            @click="form.max_items = Math.max(1, form.max_items - 1)"
          >−</button>
          <span class="w-12 text-center text-lg font-semibold text-slate-900">{{ form.max_items }}</span>
          <button
            class="w-9 h-9 rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-50 disabled:opacity-40"
            :disabled="form.max_items >= 50"
            @click="form.max_items = Math.min(50, form.max_items + 1)"
          >+</button>
          <span class="text-sm text-slate-600">条/次</span>
        </div>
      </section>

      <section class="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <label class="text-sm font-medium text-slate-700 mb-3 block">推送渠道</label>
        <n-checkbox-group v-model:value="form.channels" class="!flex !flex-col !gap-2">
          <n-checkbox value="inbox">站内消息</n-checkbox>
          <n-checkbox value="feishu">飞书群机器人</n-checkbox>
          <n-checkbox value="email">邮件</n-checkbox>
        </n-checkbox-group>
      </section>

      <div class="flex gap-3 mt-6">
        <n-button class="!flex-1" @click="step = 1">上一步</n-button>
        <n-button type="primary" class="!flex-1" :loading="saving" @click="onSave">保存订阅</n-button>
      </div>
    </div>

    <!-- Step 3: 完成 -->
    <div v-show="step === 3" class="text-center py-12 min-h-[320px]">
      <div class="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl mx-auto mb-4">✓</div>
      <h2 class="text-xl font-bold text-slate-900 mb-2">订阅已创建</h2>
      <p class="text-slate-500 mb-8">系统会按你设置的规则自动推送相关内容。</p>
      <div class="flex gap-3 justify-center">
        <n-button @click="$router.push('/me')">查看我的订阅</n-button>
        <n-button type="primary" @click="resetAndNew">再建一个</n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NInput, NInputNumber, NButton, NSelect, NCheckbox, NCheckboxGroup, useMessage,
} from 'naive-ui'
import { parseSub, createSub } from '@/lib/api'

const router = useRouter()
const msg = useMessage()

const step = ref(1)
const nl = ref('')
const generating = ref(false)
const saving = ref(false)

const examples = [
  '每天 9 点推送 AI 大模型和机器人最新进展',
  '每周一早 8 点汇总科技融资资讯',
  '实时推送世界杯相关体育新闻',
  '每天下午 6 点汇总新能源和自动驾驶动态',
]

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

type FreqMode = 'realtime' | 'daily' | 'weekly' | 'interval'

function defaultForm() {
  return {
    title: '',
    keywords: [] as string[],
    categories_l1: [] as string[],
    categories_l2: [] as string[],
    freq_mode: 'daily' as FreqMode,
    hour: 9,
    minute: 0,
    weeklyDay: 1,
    interval_min: 60,
    max_items: 10,
    channels: ['inbox'] as string[],
  }
}

const form = ref(defaultForm())

const freqOptions = [
  { label: '实时', value: 'realtime' },
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '每隔', value: 'interval' },
]

const weekdayOptions = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 0 },
]

const nlError = ref('')
function validateNL() {
  if (!nl.value.trim()) {
    nlError.value = '请输入你想关注的内容'
    return false
  }
  nlError.value = ''
  return true
}
watch(nl, () => { if (nlError.value) validateNL() })

const keywordText = computed({
  get: () => form.value.keywords.join(', '),
  set: (v: string) => {
    form.value.keywords = v.split(/[,，\s]+/).filter(Boolean)
  },
})

const availableL2 = computed(() => {
  const set = new Set<string>()
  for (const l1 of form.value.categories_l1) {
    for (const l2 of l2Map[l1] || []) set.add(l2)
  }
  return Array.from(set)
})

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

const dailyHint = computed(() => `每天 ${pad2(form.value.hour)}:${pad2(form.value.minute)}`)
const weeklyHint = computed(() => {
  const w = weekdayOptions.find(o => o.value === form.value.weeklyDay)?.label || '周一'
  return `每周${w} ${pad2(form.value.hour)}:${pad2(form.value.minute)}`
})

function parseCronToFreq(cron: string | undefined | null): {
  mode: FreqMode
  hour: number
  minute: number
  weeklyDay: number
  interval_min: number
} {
  const fallback = { mode: 'daily' as FreqMode, hour: 9, minute: 0, weeklyDay: 1, interval_min: 60 }
  if (!cron || typeof cron !== 'string') return fallback
  const c = cron.trim()
  // */5 * * * * → 实时
  const m1 = c.match(/^\*\/(\d+)\s+\*\s+\*\s+\*\s+\*$/)
  if (m1) {
    return { mode: 'realtime', hour: 9, minute: 0, weeklyDay: 1, interval_min: parseInt(m1[1]) || 5 }
  }
  // * * * * * → 间隔 60 分钟
  if (c === '* * * * *') {
    return { mode: 'interval', hour: 9, minute: 0, weeklyDay: 1, interval_min: 60 }
  }
  // 0 */N * * * → 每 N 小时 → 间隔 N*60 分钟
  const m2 = c.match(/^(\d+)\s+\*\/(\d+)\s+\*\s+\*\s+\*$/)
  if (m2) {
    const stepHours = parseInt(m2[2]) || 1
    return { mode: 'interval', hour: 0, minute: parseInt(m2[1]) || 0, weeklyDay: 1, interval_min: stepHours * 60 }
  }
  // 标准 5 段
  const parts = c.split(/\s+/)
  if (parts.length === 5) {
    const mm = parseInt(parts[0])
    const hh = parseInt(parts[1])
    const dow = parts[4]
    if (Number.isNaN(mm) || Number.isNaN(hh)) return fallback
    if (dow === '*') {
      return { mode: 'daily', hour: hh, minute: mm, weeklyDay: 1, interval_min: 60 }
    }
    const dowNum = parseInt(dow)
    if (!Number.isNaN(dowNum)) {
      return { mode: 'weekly', hour: hh, minute: mm, weeklyDay: dowNum, interval_min: 60 }
    }
  }
  return fallback
}

function buildCronExpr(): string {
  const h = Number.isFinite(form.value.hour) ? form.value.hour : 9
  const m = Number.isFinite(form.value.minute) ? form.value.minute : 0
  if (form.value.freq_mode === 'realtime') {
    return '*/5 * * * *'
  }
  if (form.value.freq_mode === 'daily') {
    return `${m} ${h} * * *`
  }
  if (form.value.freq_mode === 'weekly') {
    return `${m} ${h} * * ${form.value.weeklyDay}`
  }
  // interval: 用每分钟跑的兜底 cron，真正间隔由 interval_min 控制
  return '* * * * *'
}

function buildIntervalMin(): number {
  if (form.value.freq_mode === 'interval') return form.value.interval_min || 60
  if (form.value.freq_mode === 'realtime') return form.value.interval_min || 5
  return 0
}

function toggleL1(cat: string) {
  const i = form.value.categories_l1.indexOf(cat)
  if (i >= 0) {
    form.value.categories_l1.splice(i, 1)
    form.value.categories_l2 = form.value.categories_l2.filter(
      l2 => !(l2Map[cat] || []).includes(l2),
    )
  } else {
    form.value.categories_l1.push(cat)
  }
}
function toggleL2(l2: string) {
  const i = form.value.categories_l2.indexOf(l2)
  if (i >= 0) form.value.categories_l2.splice(i, 1)
  else form.value.categories_l2.push(l2)
}

function applyParsed(parsed: any) {
  const safe = parsed && typeof parsed === 'object' ? parsed : {}
  const freq = parseCronToFreq(safe.cron_expr)
  const next = defaultForm()
  next.title = typeof safe.title === 'string' ? safe.title : ''
  next.keywords = Array.isArray(safe.keywords) ? safe.keywords.map(String) : []
  next.categories_l1 = Array.isArray(safe.categories_l1) ? safe.categories_l1.map(String) : []
  next.categories_l2 = Array.isArray(safe.categories_l2) ? safe.categories_l2.map(String) : []
  next.freq_mode = freq.mode
  next.hour = freq.hour
  next.minute = freq.minute
  next.weeklyDay = freq.weeklyDay
  next.interval_min = Number.isFinite(safe.interval_min) && safe.interval_min > 0
    ? Number(safe.interval_min)
    : freq.interval_min
  next.max_items = Number.isFinite(safe.max_items) ? Number(safe.max_items) : 10
  // channels 保留用户已在页面上选好的（来自 default_channels），不被 AI 解析覆盖
  next.channels = form.value.channels && form.value.channels.length
    ? [...form.value.channels]
    : ['inbox']
  form.value = next
}

async function onGenerate() {
  if (!validateNL()) return
  generating.value = true
  try {
    let parsed: any
    try {
      parsed = await parseSub(nl.value.trim())
    } catch (e: any) {
      console.error('[NewSubPage] parseSub failed:', e)
      msg.error(e?.data?.detail || e?.message || '生成失败，请重试')
      return
    }
    if (!parsed || typeof parsed !== 'object') {
      msg.error('解析结果异常，请重试')
      return
    }
    applyParsed(parsed)
    step.value = 2
  } finally {
    generating.value = false
  }
}

async function onSave() {
  if (!form.value.title.trim()) {
    msg.warning('请给订阅起个名字')
    return
  }
  saving.value = true
  try {
    const body = {
      title: form.value.title,
      nl_query: nl.value.trim(),
      keywords: form.value.keywords,
      categories_l1: form.value.categories_l1,
      categories_l2: form.value.categories_l2,
      max_items: form.value.max_items,
      channels: form.value.channels,
      cron_expr: buildCronExpr(),
      interval_min: buildIntervalMin(),
    }
    await createSub(body)
    step.value = 3
  } catch (e: any) {
    msg.error(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function resetAndNew() {
  nl.value = ''
  form.value = defaultForm()
  step.value = 1
}
</script>
