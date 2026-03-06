import { CheckCircle2, Info, TriangleAlert, X } from 'lucide-react'

import { useStore } from '../store/useStore'

const iconMap = {
  success: CheckCircle2,
  error: TriangleAlert,
  info: Info,
}

export default function Toast() {
  const { toasts, removeToast } = useStore()

  return (
    <div className="fixed bottom-4 right-4 z-[120] space-y-2">
      {toasts.map((toast) => {
        const Icon = iconMap[toast.type]
        return (
          <div
            key={toast.id}
            className={`flex min-w-[280px] items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${
              toast.type === 'success'
                ? 'border-profit/40 bg-profit/10 text-profit'
                : toast.type === 'error'
                  ? 'border-loss/40 bg-loss/10 text-loss'
                  : 'border-signal/40 bg-signal/10 text-text-primary'
            }`}
          >
            <Icon size={16} className="mt-0.5 shrink-0" />
            <div className="flex-1 text-xs leading-5">{toast.message}</div>
            <button onClick={() => removeToast(toast.id)} className="opacity-60 transition hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
