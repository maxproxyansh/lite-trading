import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'

import { useStore } from '../store/useStore'

const config = {
  success: { icon: CheckCircle2, accent: 'text-profit', label: 'Success' },
  error: { icon: TriangleAlert, accent: 'text-loss', label: 'Error' },
  info: { icon: Info, accent: 'text-signal', label: 'Info' },
} as const

export default function Toast() {
  const { toasts, removeToast } = useStore(useShallow((state) => ({
    toasts: state.toasts,
    removeToast: state.removeToast,
  })))

  return (
    <div className="fixed bottom-3 right-3 z-[120] space-y-2">
      {toasts.map((toast) => {
        const { icon: Icon, accent, label } = config[toast.type]
        return (
          <div
            key={toast.id}
            className="w-64 rounded-md border border-border-primary bg-bg-secondary/95 p-3 shadow-xl backdrop-blur animate-slide-in"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Icon size={14} className={accent} />
                <span className="text-[11px] font-medium text-text-primary">{label}</span>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-text-muted hover:text-text-primary transition-colors"
              >
                <X size={12} />
              </button>
            </div>
            <div className="mt-1.5 text-[11px] leading-4 text-text-muted">{toast.message}</div>
          </div>
        )
      })}
    </div>
  )
}
