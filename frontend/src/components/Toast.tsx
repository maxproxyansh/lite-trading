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
    <div className="fixed bottom-3 right-3 z-[120] space-y-1.5">
      {toasts.map((toast) => {
        const Icon = iconMap[toast.type]
        return (
          <div
            key={toast.id}
            className={`flex min-w-[260px] items-start gap-2.5 rounded border px-3 py-2.5 text-xs shadow-lg ${
              toast.type === 'success'
                ? 'border-profit/30 bg-profit/10 text-profit'
                : toast.type === 'error'
                  ? 'border-loss/30 bg-loss/10 text-loss'
                  : 'border-signal/30 bg-signal/10 text-text-primary'
            }`}
          >
            <Icon size={14} className="mt-0.5 shrink-0" />
            <div className="flex-1 leading-4">{toast.message}</div>
            <button onClick={() => removeToast(toast.id)} className="opacity-50 transition-opacity hover:opacity-100">
              <X size={12} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
