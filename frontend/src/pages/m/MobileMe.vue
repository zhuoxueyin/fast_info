<template>
  <div class="pb-2">
    <!-- 身份卡 -->
    <section
      class="rounded-3xl p-5 text-white mb-4 shadow-md"
      style="background: linear-gradient(145deg,#0f172a,#134e4a)"
    >
      <div class="flex items-center gap-3">
        <div class="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur flex items-center justify-center text-2xl font-bold">
          {{ initial }}
        </div>
        <div class="min-w-0">
          <div class="text-lg font-bold truncate">{{ displayName }}</div>
          <div class="text-[11px] text-white/65 truncate">{{ auth.user?.email || '未设置邮箱' }}</div>
          <div class="text-[10px] text-emerald-300/90 mt-1">3 分钟情报 · 个人中枢</div>
        </div>
      </div>
    </section>

    <!-- 快捷宫格 -->
    <div class="grid grid-cols-2 gap-2.5 mb-4">
      <router-link
        v-for="tile in tiles"
        :key="tile.to"
        :to="tile.to"
        class="rounded-2xl bg-white border border-slate-200/80 p-3.5 shadow-sm active:scale-[0.98] transition"
      >
        <div
          class="w-9 h-9 rounded-xl flex items-center justify-center mb-2"
          :style="{ background: tile.bg, color: tile.fg }"
        >
          <component :is="tile.icon" :size="18" />
        </div>
        <div class="text-sm font-semibold text-slate-900">{{ tile.title }}</div>
        <div class="text-[10px] text-slate-400 mt-0.5">{{ tile.sub }}</div>
      </router-link>
    </div>

    <!-- 列表入口 -->
    <section class="rounded-2xl bg-white border border-slate-200/80 overflow-hidden shadow-sm mb-4">
      <router-link
        v-for="row in rows"
        :key="row.to"
        :to="row.to"
        class="flex items-center gap-3 px-4 py-3.5 border-b border-slate-100 last:border-0 active:bg-slate-50"
      >
        <component :is="row.icon" :size="16" class="text-slate-400" />
        <span class="flex-1 text-sm text-slate-800">{{ row.title }}</span>
        <ChevronRight :size="15" class="text-slate-300" />
      </router-link>
    </section>

    <p class="text-center text-[10px] text-slate-400 px-4 leading-relaxed">
      不是更大的信息流，而是更少、更准、可推送到飞书的个人简报。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ChevronRight,
  Mail,
  Library,
  Radar,
  Settings,
  History,
  Flame,
  Plus,
} from 'lucide-vue-next'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '用户',
)
const initial = computed(() => (displayName.value[0] || '?').toUpperCase())

const tiles = [
  { to: '/m/me/inbox', title: '晨报信封', sub: '推送回看', icon: Mail, bg: '#ecfdf5', fg: '#059669' },
  { to: '/m/channels', title: '我的频道', sub: '订阅杂志', icon: Library, bg: '#eff6ff', fg: '#2563eb' },
  { to: '/m/radar', title: '情报雷达', sub: '盯人盯事', icon: Radar, bg: '#f5f3ff', fg: '#7c3aed' },
  { to: '/m/hot', title: '冲击榜', sub: '今日擂台', icon: Flame, bg: '#fff7ed', fg: '#ea580c' },
]

const rows = [
  { to: '/m/subs/new', title: '一句话订刊', icon: Plus },
  { to: '/m/me/settings', title: '推送与设置', icon: Settings },
  { to: '/m/me/push-history', title: '推送历史', icon: History },
]
</script>
