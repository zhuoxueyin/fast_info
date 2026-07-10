<template>
  <div>
    <!-- 顶部 -->
    <div class="flex items-center gap-2 mb-4">
      <button class="p-1 -ml-1" @click="goBack">
        <ChevronLeft :size="22" />
      </button>
      <h1 class="text-lg font-bold text-slate-900">{{ isEdit ? '编辑订阅' : '新建订阅' }}</h1>
    </div>

    <!-- 步骤指示器 -->
    <div class="flex items-center mb-5 text-xs">
      <span :class="step >= 1 ? 'text-emerald-600 font-medium' : 'text-slate-400'">
        <span class="inline-block w-5 h-5 rounded-full text-center leading-5 mr-1" :class="step >= 1 ? 'bg-emerald-500 text-white' : 'bg-slate-200'">1</span>
        描述意图
      </span>
      <span class="mx-2 text-slate-300 flex-1 border-t border-dashed"></span>
      <span :class="step >= 2 ? 'text-emerald-600 font-medium' : 'text-slate-400'">
        <span class="inline-block w-5 h-5 rounded-full text-center leading-5 mr-1" :class="step >= 2 ? 'bg-emerald-500 text-white' : 'bg-slate-200'">2</span>
        保存
      </span>
    </div>

    <!-- Step 1 -->
    <div v-if="step === 1" class="space-y-4">
      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">
          用一句话描述你想关注的内容<span class="text-rose-500">*</span>
        </label>
        <textarea
          v-model="nl"
          rows="3"
          placeholder="例如:每天 9 点推送 AI 大模型和机器人最新进展"
          class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-300 focus:border-emerald-400 resize-none"
          :disabled="generating"
        ></textarea>
        <p class="text-xs mt-2" :class="nlError ? 'text-rose-500' : 'text-slate-400'">
          {{ nlError || '系统会自动识别时间、关键词、分类和推送频率' }}
        </p>
      </div>

      <div>
        <span class="text-xs text-slate-500 mr-2">试试:</span>
        <div class="flex flex-wrap gap-2 mt-2">
          <button
            v-for="ex in examples"
            :key="ex"
            class="text-xs px-3 py-1 rounded-full border border-slate-200 text-slate-600 active:scale-95"
            :disabled="generating"
            @click="nl = ex"
          >{{ ex }}</button>
        </div>
      </div>

      <button
        class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium active:scale-[0.99]"
        :disabled="generating || !nl.trim()"
        @click="onGenerate"
      >
        {{ generating ? '生成中…' : '生成订阅规则' }}
      </button>
    </div>

    <!-- Step 2 -->
    <div v-if="step === 2" class="space-y-4">
      <div class="bg-emerald-50 rounded-xl border border-emerald-100 p-3 text-sm">
        <span class="font-medium text-emerald-800">已识别:</span>
        <span class="text-slate-700 ml-1">{{ nl }}</span>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">订阅名称</label>
        <input
          v-model="form.title"
          maxlength="30"
          placeholder="给订阅起个名字"
          class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-300"
        />
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">关键词</label>
        <input
          v-model="keywordText"
          placeholder="逗号分隔,如:大模型,机器人,AI"
          class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-300"
        />
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">分类</label>
        <div class="flex flex-wrap gap-1.5 mb-2">
          <button
            v-for="cat in l1List"
            :key="cat"
            class="text-xs px-2.5 py-1 rounded-full transition"
            :class="form.categories_l1.includes(cat) ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-700'"
            @click="toggleL1(cat)"
          >{{ cat }}</button>
        </div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">推送频率</label>
        <div class="flex gap-1.5 mb-3 flex-wrap">
          <button
            v-for="opt in freqOptions"
            :key="opt.value"
            class="text-xs px-3 py-1.5 rounded-full transition"
            :class="form.freq_mode === opt.value ? 'bg-blue-500 text-white' : 'bg-slate-100 text-slate-700'"
            @click="form.freq_mode = opt.value as any"
          >{{ opt.label }}</button>
        </div>
        <div v-if="form.freq_mode === 'daily'" class="flex items-center gap-2 text-sm">
          <span class="text-slate-500">每天</span>
          <input v-model.number="form.hour" type="number" min="0" max="23" class="w-16 px-2 py-1 text-sm border border-slate-200 rounded-lg" />
          <span>:</span>
          <input v-model.number="form.minute" type="number" min="0" max="59" step="5" class="w-16 px-2 py-1 text-sm border border-slate-200 rounded-lg" />
          <span class="text-xs text-slate-500">点</span>
        </div>
        <div v-else-if="form.freq_mode === 'weekly'" class="flex items-center gap-2 text-sm">
          <span class="text-slate-500">每周</span>
          <select v-model.number="form.weeklyDay" class="px-2 py-1 text-sm border border-slate-200 rounded-lg">
            <option :value="1">一</option>
            <option :value="2">二</option>
            <option :value="3">三</option>
            <option :value="4">四</option>
            <option :value="5">五</option>
            <option :value="6">六</option>
            <option :value="0">日</option>
          </select>
          <input v-model.number="form.hour" type="number" min="0" max="23" class="w-16 px-2 py-1 text-sm border border-slate-200 rounded-lg" />
          <span>:</span>
          <input v-model.number="form.minute" type="number" min="0" max="59" step="5" class="w-16 px-2 py-1 text-sm border border-slate-200 rounded-lg" />
        </div>
        <div v-else-if="form.freq_mode === 'interval'" class="flex items-center gap-2 text-sm">
          <span class="text-slate-500">每</span>
          <input v-model.number="form.interval_min" type="number" min="15" step="15" class="w-20 px-2 py-1 text-sm border border-slate-200 rounded-lg" />
          <span class="text-xs text-slate-500">分钟</span>
        </div>
      </div>

      <div class="bg-white rounded-xl border border-slate-200 p-4">
        <label class="text-sm font-medium text-slate-700 mb-2 block">每次最多推送</label>
        <input
          v-model.number="form.max_items"
          type="number"
          min="1"
          max="50"
          class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-300"
        />
        <p class="text-xs text-slate-400 mt-1">单次推送最多包含的文章数</p>
      </div>

      <button
        class="w-full py-3 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium active:scale-[0.99]"
        :disabled="saving"
        @click="onSave"
      >
        {{ saving ? '保存中…' : (isEdit ? '保存修改' : '保存订阅') }}
      </button>

      <button
        class="w-full py-2.5 rounded-xl bg-white border border-slate-200 text-slate-700 text-sm font-medium active:scale-[0.99]"
        :disabled="saving"
        @click="step = 1"
      >返回上一步</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import { api, parseSub, createSub, getSub, patchSub } from '@/lib/api'

const route = useRoute()
const router = useRouter()

const subId = computed(() => (route.params.id as string) || '')
const isEdit = computed(() => !!subId.value)

const step = ref(1)
const nl = ref('')
const nlError = ref('')
const generating = ref(false)
const saving = ref(false)

const examples = [
  '每天 9 点推送 AI 大模型和机器人最新进展',
  '每周一早 8 点汇总科技融资资讯',
  '实时推送世界杯相关体育新闻',
  '每天下午 6 点汇总新能源和自动驾驶动态',
]

const l1List = ['科技', 'AI', '体育', '娱乐', '财经', '汽车', '其他']

const freqOptions = [
  { label: '实时', value: 'realtime' },
  { label: '每天', value: 'daily' },
  { label: '每周', value: 'weekly' },
  { label: '每隔', value: 'interval' },
]

const form = ref({
  title: '',
  categories_l1: [] as string[],
  freq_mode: 'daily' as 'realtime' | 'daily' | 'weekly' | 'interval',
  hour: 9,
  minute: 0,
  weeklyDay: 1,
  interval_min: 60,
  max_items: 10,
})

const keywordText = ref('')

function goBack() {
  if (step.value === 2 && !isEdit.value) {
    step.value = 1
    return
  }
  if (window.history.length > 1) router.back()
  else router.push('/m/channels')
}

function toggleL1(cat: string) {
  const arr = form.value.categories_l1
  if (arr.includes(cat)) form.value.categories_l1 = arr.filter(c => c !== cat)
  else form.value.categories_l1 = [...arr, cat]
}

async function onGenerate() {
  const text = nl.value.trim()
  if (text.length < 4) {
    nlError.value = '请至少输入 4 个字描述你的需求'
    return
  }
  nlError.value = ''
  generating.value = true
  try {
    const parsed = await parseSub(text)
    if (parsed?.title) form.value.title = parsed.title
    if (Array.isArray(parsed?.keywords)) keywordText.value = parsed.keywords.join(', ')
    if (Array.isArray(parsed?.categories_l1)) form.value.categories_l1 = parsed.categories_l1
    if (typeof parsed?.max_items === 'number') form.value.max_items = parsed.max_items
    if (parsed?.freq_mode) form.value.freq_mode = parsed.freq_mode
    if (typeof parsed?.hour === 'number') form.value.hour = parsed.hour
    if (typeof parsed?.minute === 'number') form.value.minute = parsed.minute
    if (typeof parsed?.weeklyDay === 'number') form.value.weeklyDay = parsed.weeklyDay
    if (typeof parsed?.interval_min === 'number') form.value.interval_min = parsed.interval_min
    step.value = 2
  } catch (e: any) {
    nlError.value = e?.data?.detail || '生成失败,请重试'
  } finally {
    generating.value = false
  }
}

async function onSave() {
  if (!form.value.title.trim()) {
    alert('请给订阅起个名字')
    return
  }
  saving.value = true
  const payload = {
    title: form.value.title.trim(),
    nl_query: nl.value,
    keywords: keywordText.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean),
    categories_l1: form.value.categories_l1,
    freq_mode: form.value.freq_mode,
    hour: form.value.hour,
    minute: form.value.minute,
    weeklyDay: form.value.weeklyDay,
    interval_min: form.value.freq_mode === 'interval' ? form.value.interval_min : 0,
    max_items: form.value.max_items,
    channels: ['inbox'],
  }
  try {
    if (isEdit.value) {
      await patchSub(subId.value, payload)
    } else {
      await createSub(payload)
    }
    router.push('/m/channels')
  } catch (e: any) {
    alert(e?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  // 从今日「一句话订刊」带入
  const qNl = typeof route.query.nl === 'string' ? route.query.nl.trim() : ''
  if (qNl && !isEdit.value) {
    nl.value = qNl
  }

  if (isEdit.value) {
    try {
      const sub: any = await getSub(subId.value)
      nl.value = sub.nl_query || ''
      form.value.title = sub.title || ''
      if (Array.isArray(sub.keywords)) keywordText.value = sub.keywords.join(', ')
      if (Array.isArray(sub.categories_l1)) form.value.categories_l1 = sub.categories_l1
      if (typeof sub.max_items === 'number') form.value.max_items = sub.max_items
      if (sub.cron_expr) {
        // 简单解析: m h * * * → daily h:m
        const m = /(\d+) (\d+) \* \* \*/.exec(sub.cron_expr || '')
        if (m) {
          form.value.freq_mode = 'daily'
          form.value.minute = parseInt(m[1])
          form.value.hour = parseInt(m[2])
        }
      }
      if (typeof sub.interval_min === 'number' && sub.interval_min > 0) {
        form.value.freq_mode = 'interval'
        form.value.interval_min = sub.interval_min
      }
      step.value = 2
    } catch (e: any) {
      alert(e?.data?.detail || '加载订阅失败')
      router.replace('/m/channels')
    }
  }
})
</script>