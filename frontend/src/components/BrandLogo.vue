<template>
  <div class="inline-flex items-center" :class="gapClass">
    <svg
      :class="iconClass"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="brand-bg" x1="10" y1="8" x2="54" y2="56" gradientUnits="userSpaceOnUse">
          <stop stop-color="#20C997" />
          <stop offset="1" stop-color="#17B47F" />
        </linearGradient>
        <linearGradient id="brand-bolt" x1="25" y1="12" x2="43" y2="47" gradientUnits="userSpaceOnUse">
          <stop stop-color="#FFB15B" />
          <stop offset="1" stop-color="#FF5D5D" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#brand-bg)" />
      <path
        d="M34.82 10.5L21.1 33.77H30.07L27.61 53.5L42.9 28.83H34.09L34.82 10.5Z"
        fill="url(#brand-bolt)"
      />
    </svg>

    <div v-if="showText" class="leading-none">
      <div class="font-black tracking-tight" :class="textClass">
        <span class="text-slate-950">fast</span><span class="text-slate-900">Info</span>
      </div>
      <div v-if="showTagline" class="mt-1 text-[11px] font-medium tracking-[0.24em] uppercase text-slate-400">
        AI Intel Hub
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type BrandSize = 'sm' | 'md' | 'lg'

const props = withDefaults(defineProps<{
  size?: BrandSize
  showText?: boolean
  showTagline?: boolean
}>(), {
  size: 'md',
  showText: true,
  showTagline: false,
})

const iconClass = computed(() => {
  if (props.size === 'sm') return 'w-8 h-8 shrink-0'
  if (props.size === 'lg') return 'w-12 h-12 shrink-0'
  return 'w-10 h-10 shrink-0'
})

const textClass = computed(() => {
  if (props.size === 'sm') return 'text-xl'
  if (props.size === 'lg') return 'text-4xl'
  return 'text-[30px]'
})

const gapClass = computed(() => {
  if (props.size === 'sm') return 'gap-2.5'
  if (props.size === 'lg') return 'gap-3.5'
  return 'gap-3'
})
</script>
