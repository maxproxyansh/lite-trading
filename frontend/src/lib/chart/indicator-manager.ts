import type { IChartApi, ISeriesApi, Time } from 'lightweight-charts'
import type { Candle } from '../api'
import type { IndicatorConfig } from './types'
import { OVERLAY_INDICATORS } from './types'
import { computeEMA, computeSMA, computeBollinger, computeVWAP, computeSupertrend, computeIchimoku } from './indicators'

const IST_OFFSET_SECONDS = 5.5 * 60 * 60

export class IndicatorManager {
  private _chart: IChartApi
  private _seriesMap: Map<string, ISeriesApi<'Line'>[]> = new Map()

  constructor(chart: IChartApi) {
    this._chart = chart
  }

  /** Recompute and render all enabled overlay indicators */
  update(configs: IndicatorConfig[], candles: Candle[]): void {
    // Remove series for disabled/removed indicators
    for (const [id, seriesList] of this._seriesMap) {
      const config = configs.find((c) => c.id === id)
      if (!config || !config.enabled || !OVERLAY_INDICATORS.includes(config.type)) {
        for (const s of seriesList) this._chart.removeSeries(s)
        this._seriesMap.delete(id)
      }
    }
    // Add/update enabled overlay indicators
    for (const config of configs) {
      if (!config.enabled || !OVERLAY_INDICATORS.includes(config.type)) continue
      try {
        this._renderOverlay(config, candles)
      } catch (err) {
        console.warn(`Failed to render indicator ${config.type}:`, err)
      }
    }
  }

  private _renderOverlay(config: IndicatorConfig, candles: Candle[]): void {
    switch (config.type) {
      case 'ema': return this._renderLine(config, computeEMA(candles, config.params.period))
      case 'sma': return this._renderLine(config, computeSMA(candles, config.params.period))
      case 'vwap': return this._renderLine(config, computeVWAP(candles))
      case 'bb': return this._renderBollinger(config, candles)
      case 'supertrend': return this._renderSupertrend(config, candles)
      case 'ichimoku': return this._renderIchimoku(config, candles)
    }
  }

  private _renderLine(config: IndicatorConfig, data: { time: number; value: number }[]): void {
    const seriesData = data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value }))
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const series = this._chart.addLineSeries({
        color: config.color,
        lineWidth: config.lineWidth,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      seriesList = [series]
      this._seriesMap.set(config.id, seriesList)
    }
    seriesList[0].setData(seriesData)
  }

  private _renderBollinger(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeBollinger(candles, config.params.period, config.params.stdDev)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const upper = this._chart.addLineSeries({ color: config.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const middle = this._chart.addLineSeries({ color: config.color, lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const lower = this._chart.addLineSeries({ color: config.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [upper, middle, lower]
      this._seriesMap.set(config.id, seriesList)
    }
    seriesList[0].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.upper })))
    seriesList[1].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.middle })))
    seriesList[2].setData(data.map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.lower })))
  }

  private _renderSupertrend(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeSupertrend(candles, config.params.period, config.params.multiplier)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const bullLine = this._chart.addLineSeries({ color: '#4caf50', lineWidth: config.lineWidth, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const bearLine = this._chart.addLineSeries({ color: '#e53935', lineWidth: config.lineWidth, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [bullLine, bearLine]
      this._seriesMap.set(config.id, seriesList)
    }
    // Filter out gap points — lightweight-charts doesn't support NaN values in line series
    seriesList[0].setData(data.filter((d) => d.direction === 'up').map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))
    seriesList[1].setData(data.filter((d) => d.direction === 'down').map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.value })))
  }

  private _renderIchimoku(config: IndicatorConfig, candles: Candle[]): void {
    const data = computeIchimoku(candles, config.params.tenkan, config.params.kijun, config.params.senkou)
    let seriesList = this._seriesMap.get(config.id)
    if (!seriesList) {
      const tenkan = this._chart.addLineSeries({ color: '#0ea5e9', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const kijun = this._chart.addLineSeries({ color: '#e53935', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const senkouA = this._chart.addLineSeries({ color: '#4caf50', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const senkouB = this._chart.addLineSeries({ color: '#e53935', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      const chikou = this._chart.addLineSeries({ color: '#8b5cf6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
      seriesList = [tenkan, kijun, senkouA, senkouB, chikou]
      this._seriesMap.set(config.id, seriesList)
    }

    const shift = config.params.kijun
    seriesList[0].setData(data.filter((d) => d.tenkan !== null).map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.tenkan! })))
    seriesList[1].setData(data.filter((d) => d.kijun !== null).map((d) => ({ time: (d.time + IST_OFFSET_SECONDS) as Time, value: d.kijun! })))

    // Senkou lines shifted forward by kijun periods — only include points
    // where the shifted index is still within candle range (no clamping = no duplicate timestamps)
    const timeByIndex = new Map<number, number>()
    for (let i = 0; i < data.length; i++) timeByIndex.set(data[i].time, i)

    const senkouAData: { time: Time; value: number }[] = []
    const senkouBData: { time: Time; value: number }[] = []
    for (const d of data) {
      const origIdx = timeByIndex.get(d.time)
      if (origIdx === undefined) continue
      const shiftedIdx = origIdx + shift
      if (shiftedIdx >= data.length) continue // drop points beyond available timestamps
      const shiftedTime = data[shiftedIdx].time
      if (d.senkouA !== null) senkouAData.push({ time: (shiftedTime + IST_OFFSET_SECONDS) as Time, value: d.senkouA })
      if (d.senkouB !== null) senkouBData.push({ time: (shiftedTime + IST_OFFSET_SECONDS) as Time, value: d.senkouB })
    }
    seriesList[2].setData(senkouAData)
    seriesList[3].setData(senkouBData)

    // Chikou: current close plotted kijun periods in the past
    const chikouData: { time: Time; value: number }[] = []
    for (let i = shift; i < data.length; i++) {
      if (data[i].chikou !== null) {
        chikouData.push({ time: (data[i - shift].time + IST_OFFSET_SECONDS) as Time, value: data[i].chikou! })
      }
    }
    seriesList[4].setData(chikouData)
  }

  destroy(): void {
    for (const [, seriesList] of this._seriesMap) {
      for (const s of seriesList) this._chart.removeSeries(s)
    }
    this._seriesMap.clear()
  }
}
