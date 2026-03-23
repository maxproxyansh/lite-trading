import { useState } from 'react'
import WidgetPrompt from './WidgetPrompt'

export default function WidgetButton() {
  const [showPrompt, setShowPrompt] = useState(false)

  const handleTap = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setShowPrompt(true)
  }

  return (
    <>
      <button
        onClick={handleTap}
        className="md:hidden shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-bg-secondary border border-border-primary transition-colors hover:bg-bg-hover"
        title="Lite Pulse"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="#a3e635"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="2,12 6,12 9,4 12,20 15,8 18,12 22,12" />
        </svg>
      </button>
      {showPrompt && (
        <WidgetPrompt onClose={() => {
          setShowPrompt(false)
          localStorage.setItem('pulse-prompt-dismissed', 'true')
        }} />
      )}
    </>
  )
}
