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
        className="flex items-center justify-center rounded p-0.5 text-text-muted transition-colors hover:text-text-primary"
        title={isOpen ? 'Close floating price' : 'Float price'}
      >
        <svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {isOpen ? (
            <>
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <line x1="9" y1="9" x2="15" y2="15" />
              <line x1="15" y1="9" x2="9" y2="15" />
            </>
          ) : (
            <>
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <rect x="12" y="10" width="8" height="8" rx="1" />
            </>
          )}
        </svg>
      </button>
      {isOpen && portalTarget && createPortal(<PiPWidget />, portalTarget)}
    </>
  )
}
