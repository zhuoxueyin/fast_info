/**
 * fastInfo · 设备类型检测
 * =========================
 * 用于"同一访问地址、手机自动渲染移动版"。
 *
 * 判定策略:
 *   - User-Agent 含 mobile / android / iphone / ipad / ipod 等关键词
 *   - 触屏优先 (maxTouchPoints > 0)
 *   - 屏幕宽度 ≤ 768px 也算 mobile（覆盖 iPad Pro / 横屏手机等）
 *
 * 注意:
 *   - 仅在客户端运行（typeof navigator !== 'undefined'）
 *   - SSR 兼容:服务端默认 desktop
 *   - 用户可在 Settings 手动切换覆盖（localStorage 持久化）
 */

export type DeviceType = 'mobile' | 'desktop'

const STORAGE_KEY = 'fastinfo.device-override'

/** 从 User-Agent 检测设备类型
 * 注意:iPad 现代 UA 不带 "iPad" 字样,靠 maxTouchPoints + macintosh 辅助
 */
export function detectFromUA(ua: string): DeviceType {
  if (!ua) return 'desktop'
  const lower = ua.toLowerCase()
  // 平板/手机关键词
  if (/mobile|android|iphone|ipod|blackberry|iemobile|opera mini|webos/.test(lower)) {
    return 'mobile'
  }
  // iPad 现代 UA 伪装成 desktop,用 maxTouchPoints 识别
  if (typeof navigator !== 'undefined' && /macintosh/.test(lower) && navigator.maxTouchPoints > 1) {
    return 'mobile'
  }
  return 'desktop'
}

/** 综合检测:UA 优先 + 屏幕/触屏兜底
 * 原则:UA 明确是 desktop 的设备,不再因窗口缩小或带触屏而被切到 mobile,
 * 避免 PC 浏览器缩窗、触屏笔记本被误判为移动端。
 */
export function detectDevice(): DeviceType {
  if (typeof navigator === 'undefined') return 'desktop'

  // 用户手动覆盖
  try {
    const override = localStorage.getItem(STORAGE_KEY)
    if (override === 'mobile' || override === 'desktop') return override
  } catch {
    // localStorage 可能被禁用（隐私模式）,忽略
  }

  const uaType = detectFromUA(navigator.userAgent || '')

  // UA 明确判断为 desktop:直接返回 desktop,不再受窗口大小/触屏影响
  if (uaType === 'desktop') return 'desktop'

  // UA 明确判断为 mobile:直接返回 mobile
  if (uaType === 'mobile') return 'mobile'

  // 未知 UA 兜底:触屏 + 小屏才算 mobile
  const touchPoints = navigator.maxTouchPoints || 0
  const screenW = typeof window !== 'undefined' ? window.innerWidth : 1024
  const isSmallScreen = screenW <= 768
  if (isSmallScreen && touchPoints > 0) return 'mobile'
  return 'desktop'
}

/** 写入用户手动覆盖 */
export function setDeviceOverride(type: DeviceType | null) {
  try {
    if (type === null) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, type)
    }
  } catch {
    // ignore
  }
}

/** 当前设备类型（响应式 ref，窗口大小变化时自动更新）*/
import { ref, onMounted, onUnmounted } from 'vue'

const _device = ref<DeviceType>('desktop')

export function useDevice() {
  if (typeof window !== 'undefined') {
    onMounted(() => {
      _device.value = detectDevice()
      window.addEventListener('resize', handleResize, { passive: true })
    })
    onUnmounted(() => {
      window.removeEventListener('resize', handleResize)
    })
  }
  return _device
}

function handleResize() {
  const newType = detectDevice()
  if (newType !== _device.value) {
    _device.value = newType
  }
}