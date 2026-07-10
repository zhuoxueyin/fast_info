/**
 * 移动端杂志风 UI 共用工具
 */
import {
  Cpu, Sparkles, TrendingUp, Trophy, Music, Car, HelpCircle, Newspaper, Flame,
} from 'lucide-vue-next'
import dayjs from 'dayjs'

export const L1_PALETTE: Record<string, string> = {
  科技: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
  AI: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
  财经: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
  体育: 'linear-gradient(135deg, #EF4444 0%, #DC2626 100%)',
  娱乐: 'linear-gradient(135deg, #EC4899 0%, #DB2777 100%)',
  汽车: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
  其他: 'linear-gradient(135deg, #64748B 0%, #475569 100%)',
}

export const L1_SOLID: Record<string, string> = {
  科技: '#10B981',
  AI: '#8B5CF6',
  财经: '#F59E0B',
  体育: '#EF4444',
  娱乐: '#EC4899',
  汽车: '#3B82F6',
  其他: '#64748B',
}

const L1_ICONS: Record<string, any> = {
  科技: Cpu,
  AI: Sparkles,
  财经: TrendingUp,
  体育: Trophy,
  娱乐: Music,
  汽车: Car,
  其他: HelpCircle,
}

const SOURCE_LABELS: Record<string, string> = {
  cls: '财联社',
  leiphone: '雷锋网',
  ithome: 'IT之家',
  sina: '新浪',
  qq: '腾讯',
  kr36: '36氪',
  '36kr': '36氪',
  huxiu: '虎嗅',
  sohu: '搜狐',
  weibo_hot: '微博热搜',
  'weibo:hot': '热搜',
  qbitai: '量子位',
  sspai: '少数派',
  infoq: 'InfoQ',
  ifanr: '爱范儿',
  zhihu_hot: '知乎热榜',
  wallstreetcn: '华尔街见闻',
  bilibili: 'B站',
}

export function l1Icon(name?: string) {
  return L1_ICONS[name || ''] || Newspaper
}

export function l1Gradient(name?: string) {
  return L1_PALETTE[name || ''] || L1_PALETTE['其他']
}

export function l1Solid(name?: string) {
  return L1_SOLID[name || ''] || L1_SOLID['其他']
}

export function sourceLabel(src?: string) {
  if (!src) return ''
  return SOURCE_LABELS[src] || src
}

export function formatRelativeTime(t?: string | null) {
  if (!t) return ''
  const d = dayjs(t)
  const now = dayjs()
  const mins = now.diff(d, 'minute')
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = now.diff(d, 'hour')
  if (hours < 24) return `${hours} 小时前`
  const days = now.diff(d, 'day')
  if (days < 7) return `${days} 天前`
  return d.format('MM-DD')
}

export function formatRemain(iso?: string | null): string {
  if (!iso) return '短期'
  const diff = new Date(iso).getTime() - Date.now()
  if (diff <= 0) return '已过期'
  const days = Math.floor(diff / 86400000)
  if (days > 0) return `剩 ${days} 天`
  const hours = Math.floor(diff / 3600000)
  if (hours > 0) return `剩 ${hours}h`
  return `剩 ${Math.floor(diff / 60000)}m`
}

export function formatRelScore(r?: number | null) {
  if (r == null || Number.isNaN(r)) return ''
  return String(Math.round(r * 100))
}

/** 从摘要提炼「一句话」：优先首句，截断到 maxLen */
export function oneLiner(summary?: string | null, maxLen = 48): string {
  if (!summary) return ''
  const cleaned = summary.replace(/\s+/g, ' ').trim()
  const first = cleaned.split(/[。！？\n]/)[0] || cleaned
  if (first.length <= maxLen) return first
  return first.slice(0, maxLen - 1) + '…'
}

/** 杂志封面渐变：按标题 hash 选一组，避免每卡同色 */
const COVER_TONES = [
  'linear-gradient(145deg, #0f766e 0%, #134e4a 55%, #042f2e 100%)',
  'linear-gradient(145deg, #5b21b6 0%, #4c1d95 55%, #1e1b4b 100%)',
  'linear-gradient(145deg, #b45309 0%, #92400e 55%, #451a03 100%)',
  'linear-gradient(145deg, #be123c 0%, #9f1239 55%, #4c0519 100%)',
  'linear-gradient(145deg, #0369a1 0%, #0c4a6e 55%, #082f49 100%)',
  'linear-gradient(145deg, #0f766e 0%, #115e59 40%, #312e81 100%)',
  'linear-gradient(145deg, #7c3aed 0%, #db2777 100%)',
]

export function coverTone(seed?: string) {
  if (!seed) return COVER_TONES[0]
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return COVER_TONES[h % COVER_TONES.length]
}

/** 沉浸阅读：跨页共享 feed id 列表 */
const FEED_KEY = 'fastinfo_m_feed_ids'

export function saveFeedIds(ids: string[]) {
  try {
    sessionStorage.setItem(FEED_KEY, JSON.stringify(ids.filter(Boolean)))
  } catch {
    /* ignore */
  }
}

export function loadFeedIds(): string[] {
  try {
    const raw = sessionStorage.getItem(FEED_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.map(String) : []
  } catch {
    return []
  }
}

export { Flame }
