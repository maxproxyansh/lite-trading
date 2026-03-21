import { useState } from 'react'
import { pulseSetup } from '../lib/api'

function launchApp(path: string) {
  window.location.href = path
}

export default function WidgetPrompt({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState<1 | 2>(1)
  const [claimToken, setClaimToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleDownload = async () => {
    setLoading(true)
    try {
      const { claim_token } = await pulseSetup()
      setClaimToken(claim_token)
      // Download APK directly from Vercel static file
      const link = document.createElement('a')
      link.href = '/lite-pulse.apk'
      link.download = 'lite-pulse.apk'
      link.click()
      setStep(2)
    } catch {
      // setup failed silently
    } finally {
      setLoading(false)
    }
  }

  const handleOpen = () => {
    if (claimToken) {
      launchApp(`litewidget://start?token=${claimToken}`)
    }
    localStorage.setItem('pulse-connected', 'true')
    onClose()
  }

  return (
    <div className="fixed bottom-20 md:bottom-6 right-4 md:right-6 z-50 w-[280px] rounded-lg border border-border-primary bg-bg-secondary shadow-[0_8px_32px_rgba(0,0,0,0.5)] overflow-hidden">
      <div className="px-4 pt-4 pb-3 flex flex-col items-center gap-2">
        {step === 1 ? (
          <>
            <svg
              viewBox="0 0 24 24"
              className="h-7 w-7"
              fill="none"
              stroke="#a3e635"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="2,12 6,12 9,4 12,20 15,8 18,12 22,12" />
            </svg>
            <p className="text-[13px] text-text-primary font-medium text-center">
              Get NIFTY on your screen, always
            </p>
            <p className="text-[11px] text-text-muted text-center leading-relaxed">
              Install Lite Pulse for a floating price overlay visible across all apps.
            </p>
          </>
        ) : (
          <>
            <p className="text-[13px] text-text-primary font-medium text-center">
              Open Lite Pulse
            </p>
            <p className="text-[11px] text-text-muted text-center leading-relaxed">
              It will connect automatically.
            </p>
          </>
        )}
      </div>
      <div className="flex border-t border-border-primary">
        <button
          onClick={onClose}
          className="flex-1 py-2.5 text-[12px] text-text-muted hover:text-text-secondary hover:bg-bg-hover transition-colors"
        >
          {step === 1 ? 'Skip' : 'Later'}
        </button>
        <div className="w-px bg-border-primary" />
        {step === 1 ? (
          <button
            onClick={handleDownload}
            disabled={loading}
            className="flex-1 py-2.5 text-[12px] font-medium text-brand hover:bg-bg-hover transition-colors disabled:opacity-40"
          >
            {loading ? 'Setting up\u2026' : 'Download'}
          </button>
        ) : (
          <button
            onClick={handleOpen}
            className="flex-1 py-2.5 text-[12px] font-medium text-brand hover:bg-bg-hover transition-colors"
          >
            Open
          </button>
        )}
      </div>
    </div>
  )
}
