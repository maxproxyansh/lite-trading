// frontend/src/components/PiPButton.tsx
import { usePiP, isPiPSupported } from '../hooks/usePiP'
import PiPWidget from './PiPWidget'
import { useStore } from '../store/useStore'

export default function PiPButton() {
  const { isOpen, containerRef, open, close } = usePiP()
  const addToast = useStore((s) => s.addToast)

  if (!isPiPSupported) return null

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (isOpen) {
      close()
    } else {
      open().then(() => {
        addToast('success', 'PiP opened')
      }).catch((err) => {
        addToast('error', `PiP failed: ${err}`)
      })
    }
  }

  return (
    <>
      <button
        onClick={handleClick}
        className="flex items-center justify-center rounded p-1 text-brand transition-colors hover:bg-bg-hover"
        title={isOpen ? 'Close floating price' : 'Float price'}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4.5 w-4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {isOpen ? (
            <>
              <rect x="2" y="2" width="20" height="20" rx="3" />
              <line x1="9" y1="9" x2="15" y2="15" />
              <line x1="15" y1="9" x2="9" y2="15" />
            </>
          ) : (
            <>
              <rect x="1" y="1" width="22" height="14" rx="3" />
              <rect x="11" y="11" width="12" height="10" rx="2" />
            </>
          )}
        </svg>
      </button>
      {/* Hidden offscreen container — PiPWidget renders here so the canvas can read DOM values */}
      <div
        ref={containerRef}
        style={{ position: 'fixed', top: -9999, left: -9999, pointerEvents: 'none' }}
      >
        <PiPWidget />
      </div>
    </>
  )
}
