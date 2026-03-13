import { useEffect, useEffectEvent, useRef } from 'react'
import { BellRing, X } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

const ALARM_INTERVAL_MS = 1400

type AlarmTone = {
  startAt: number
  frequency: number
  duration: number
  gainValue: number
}

function formatPrice(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) {
    return '--'
  }
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function scheduleTone(context: AudioContext, tone: AlarmTone) {
  const { startAt, frequency, duration, gainValue } = tone
  const oscillator = context.createOscillator()
  const gain = context.createGain()

  oscillator.type = 'square'
  oscillator.frequency.setValueAtTime(frequency, startAt)
  gain.gain.setValueAtTime(0.0001, startAt)
  gain.gain.exponentialRampToValueAtTime(gainValue, startAt + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration)

  oscillator.connect(gain)
  gain.connect(context.destination)
  oscillator.start(startAt)
  oscillator.stop(startAt + duration + 0.03)
}

function getAudioContext() {
  const contextWindow = window as Window & { webkitAudioContext?: typeof AudioContext }
  const AudioContextCtor = window.AudioContext ?? contextWindow.webkitAudioContext
  return AudioContextCtor ? new AudioContextCtor() : null
}

export default function TriggeredAlertModal() {
  const { activeAlert, queueCount, dismissTriggeredAlert } = useStore(useShallow((state) => ({
    activeAlert: state.triggeredAlertQueue[0] ?? null,
    queueCount: state.triggeredAlertQueue.length,
    dismissTriggeredAlert: state.dismissTriggeredAlert,
  })))
  const audioContextRef = useRef<AudioContext | null>(null)
  const intervalRef = useRef<number | null>(null)

  const stopAlarm = useEffectEvent(() => {
    if (intervalRef.current !== null) {
      window.clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    const context = audioContextRef.current
    if (!context || context.state === 'closed') {
      return
    }
    void context.suspend().catch(() => {})
  })

  const playAlarm = useEffectEvent(() => {
    let context = audioContextRef.current
    if (!context || context.state === 'closed') {
      context = getAudioContext()
      audioContextRef.current = context
    }
    if (!context) {
      return
    }

    void context.resume()
      .then(() => {
        const startAt = context!.currentTime + 0.02
        scheduleTone(context!, { startAt, frequency: 960, duration: 0.13, gainValue: 0.045 })
        scheduleTone(context!, { startAt: startAt + 0.24, frequency: 720, duration: 0.15, gainValue: 0.04 })
      })
      .catch(() => {})
  })

  useEffect(() => {
    if (!activeAlert) {
      stopAlarm()
      return undefined
    }

    stopAlarm()
    playAlarm()
    intervalRef.current = window.setInterval(() => {
      playAlarm()
    }, ALARM_INTERVAL_MS)

    return () => {
      stopAlarm()
    }
  }, [activeAlert])

  useEffect(() => {
    if (!activeAlert) {
      return undefined
    }

    const retryAlarm = () => {
      playAlarm()
    }

    window.addEventListener('pointerdown', retryAlarm, true)
    window.addEventListener('keydown', retryAlarm, true)
    return () => {
      window.removeEventListener('pointerdown', retryAlarm, true)
      window.removeEventListener('keydown', retryAlarm, true)
    }
  }, [activeAlert])

  useEffect(() => {
    return () => {
      stopAlarm()
      const context = audioContextRef.current
      if (!context || context.state === 'closed') {
        return
      }
      void context.close().catch(() => {})
    }
  }, [])

  if (!activeAlert) {
    return null
  }

  return (
    <div className="fixed inset-0 z-[140] bg-black/45 backdrop-blur-[1px]">
      <div className="absolute right-4 top-20 w-[290px] rounded-md border border-loss/35 bg-bg-secondary/98 p-3 shadow-[0_22px_60px_rgba(0,0,0,0.45)]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.18em] text-loss">
              <BellRing size={13} />
              <span>Alert hit</span>
            </div>
            <div className="mt-1 truncate text-sm font-medium text-text-primary">{activeAlert.symbol}</div>
          </div>
          <button
            onClick={() => dismissTriggeredAlert(activeAlert.id)}
            className="rounded-sm border border-border-primary/80 p-1 text-text-muted transition-colors hover:border-loss/40 hover:text-text-primary"
            title="Close alert"
          >
            <X size={12} />
          </button>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="rounded-sm border border-border-primary/80 bg-bg-primary/75 px-2 py-1.5">
            <div className="text-[10px] uppercase tracking-wide text-text-muted">Trigger</div>
            <div className="mt-0.5 text-[12px] font-medium tabular-nums text-text-primary">
              {formatPrice(activeAlert.target_price)}
            </div>
          </div>
          <div className="rounded-sm border border-border-primary/80 bg-bg-primary/75 px-2 py-1.5">
            <div className="text-[10px] uppercase tracking-wide text-text-muted">Last price</div>
            <div className="mt-0.5 text-[12px] font-medium tabular-nums text-text-primary">
              {formatPrice(activeAlert.last_price)}
            </div>
          </div>
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-text-muted">
          <span>{activeAlert.direction === 'ABOVE' ? 'Crossed above target' : 'Dropped below target'}</span>
          {queueCount > 1 ? <span>{queueCount} waiting</span> : null}
        </div>

        <button
          onClick={() => dismissTriggeredAlert(activeAlert.id)}
          className="mt-3 w-full rounded-sm bg-loss px-3 py-1.5 text-[11px] font-medium text-white transition-opacity hover:opacity-90"
        >
          Close alert
        </button>
      </div>
    </div>
  )
}
