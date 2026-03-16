import type { Drawing, IndicatorConfig } from './types'
import { DEFAULT_INDICATOR_CONFIGS } from './types'

const DRAWING_KEY_PREFIX = 'drawings:'
const INDICATOR_KEY = 'indicators:config'

export function loadDrawings(symbol: string): Drawing[] {
  try {
    const raw = localStorage.getItem(`${DRAWING_KEY_PREFIX}${symbol}`)
    return raw ? (JSON.parse(raw) as Drawing[]) : []
  } catch {
    return []
  }
}

export function saveDrawings(symbol: string, drawings: Drawing[]): void {
  localStorage.setItem(`${DRAWING_KEY_PREFIX}${symbol}`, JSON.stringify(drawings))
}

export function loadIndicatorConfigs(): IndicatorConfig[] {
  try {
    const raw = localStorage.getItem(INDICATOR_KEY)
    return raw ? (JSON.parse(raw) as IndicatorConfig[]) : structuredClone(DEFAULT_INDICATOR_CONFIGS)
  } catch {
    return structuredClone(DEFAULT_INDICATOR_CONFIGS)
  }
}

export function saveIndicatorConfigs(configs: IndicatorConfig[]): void {
  localStorage.setItem(INDICATOR_KEY, JSON.stringify(configs))
}

let saveDrawingsTimer: ReturnType<typeof setTimeout> | null = null
export function saveDrawingsDebounced(symbol: string, drawings: Drawing[]): void {
  if (saveDrawingsTimer) clearTimeout(saveDrawingsTimer)
  saveDrawingsTimer = setTimeout(() => saveDrawings(symbol, drawings), 500)
}

let saveIndicatorsTimer: ReturnType<typeof setTimeout> | null = null
export function saveIndicatorConfigsDebounced(configs: IndicatorConfig[]): void {
  if (saveIndicatorsTimer) clearTimeout(saveIndicatorsTimer)
  saveIndicatorsTimer = setTimeout(() => saveIndicatorConfigs(configs), 500)
}
