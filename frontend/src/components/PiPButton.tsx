// frontend/src/components/PiPButton.tsx
import { createPortal } from 'react-dom'
import { usePiP, isPiPSupported } from '../hooks/usePiP'
import PiPWidget from './PiPWidget'

export default function PiPButton() {
  const { isOpen, portalTarget, open, close } = usePiP()

  if (!isPiPSupported) return null

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation() // Prevent bubbling to parent spot price div
    if (isOpen) close()
    else open()
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
      {isOpen && portalTarget && createPortal(<PiPWidget />, portalTarget)}
    </>
  )
}
