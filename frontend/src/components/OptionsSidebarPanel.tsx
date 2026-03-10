import { X } from 'lucide-react'

import { useStore } from '../store/useStore'
import OptionsChain from './OptionsChain'

export default function OptionsSidebarPanel() {
  const { optionsSidebarOpen, toggleOptionsSidebar } = useStore()

  if (!optionsSidebarOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-black/20"
        style={{ left: '40px', top: '44px' }}
        onClick={toggleOptionsSidebar}
      />
      {/* Panel */}
      <div
        className="fixed z-40 border-r border-border-primary bg-bg-secondary animate-slide-in-left"
        style={{ left: '40px', top: '44px', bottom: 0, width: '420px' }}
      >
        <div className="flex h-full flex-col">
          {/* Close button */}
          <button
            onClick={toggleOptionsSidebar}
            className="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-sm text-text-muted hover:text-text-primary hover:bg-bg-hover transition-colors"
          >
            <X size={14} strokeWidth={1.5} />
          </button>
          <OptionsChain />
        </div>
      </div>
    </>
  )
}
