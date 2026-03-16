import { memo, useEffect } from 'react'
import { X } from 'lucide-react'

interface Props {
  onClose: () => void
}

type Shortcut = { keys: string[]; label: string }
type Section = { title: string; shortcuts: Shortcut[] }

const SECTIONS: Section[] = [
  {
    title: 'Timeframes',
    shortcuts: [
      { keys: ['1'], label: '1 minute' },
      { keys: ['1', '5'], label: '15 minutes' },
      { keys: ['5'], label: '5 minutes' },
      { keys: ['H'], label: '1 hour' },
      { keys: ['D'], label: 'Daily' },
      { keys: ['W'], label: 'Weekly' },
      { keys: ['M'], label: 'Monthly' },
    ],
  },
  {
    title: 'Options Chain',
    shortcuts: [
      { keys: ['↑', '↓'], label: 'Navigate strikes' },
      { keys: ['←', '→'], label: 'Switch call / put' },
      { keys: ['B'], label: 'Buy selected option' },
      { keys: ['S'], label: 'Sell selected option' },
      { keys: ['C'], label: 'Toggle option chart' },
      { keys: ['E'], label: 'Expanded / collapsed view' },
      { keys: ['['], label: 'Hide options panel' },
      { keys: [']'], label: 'Show options panel' },
    ],
  },
  {
    title: 'Drawing Tools',
    shortcuts: [
      { keys: ['−'], label: 'Horizontal line' },
      { keys: ['|'], label: 'Vertical line' },
      { keys: ['T'], label: 'Trend line' },
      { keys: ['Del'], label: 'Delete selected drawing' },
    ],
  },
  {
    title: 'Chart & Panels',
    shortcuts: [
      { keys: ['S'], label: 'Show / hide drawings & indicators' },
      { keys: ['A'], label: 'Create alert at crosshair' },
      { keys: ['G', 'M'], label: 'Macro Calendar' },
      { keys: ['G', 'F'], label: 'FII / DII positions' },
      { keys: ['Esc'], label: 'Close modal / cancel' },
      { keys: ['?'], label: 'This help' },
    ],
  },
]

function Key({ children }: { children: string }) {
  const isWide = children.length > 2
  return (
    <kbd
      className={`inline-flex items-center justify-center rounded border border-[#444] bg-[#2a2a2a] font-mono text-[11px] font-medium text-[#ccc] shadow-[0_1px_0_#222,inset_0_1px_0_#3a3a3a] ${
        isWide ? 'min-w-[28px] px-1.5' : 'min-w-[22px]'
      } h-[22px]`}
    >
      {children}
    </kbd>
  )
}

export const KeyboardShortcutsModal = memo(function KeyboardShortcutsModal({ onClose }: Props) {
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-[520px] max-w-[90vw] max-h-[80vh] overflow-y-auto rounded-xl border border-[#333] bg-[#1a1a1a] shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#2a2a2a] bg-[#1a1a1a]/95 px-5 py-3 backdrop-blur-sm">
          <div>
            <h2 className="text-[14px] font-semibold text-[#e0e0e0]">Keyboard Shortcuts</h2>
            <p className="mt-0.5 text-[11px] text-[#666]">Press any shortcut key to use</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-6 w-6 items-center justify-center rounded-md text-[#666] transition-colors hover:bg-[#2a2a2a] hover:text-[#ccc]"
          >
            <X size={14} />
          </button>
        </div>

        {/* Sections */}
        <div className="grid grid-cols-2 gap-0 max-[480px]:grid-cols-1">
          {SECTIONS.map((section, sectionIdx) => (
            <div
              key={section.title}
              className={`px-5 py-3 ${
                sectionIdx < SECTIONS.length - 1 ? 'border-b border-[#222]' : ''
              } ${sectionIdx % 2 === 0 ? 'border-r border-[#222] max-[480px]:border-r-0' : ''}`}
            >
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[1px] text-[#555]">
                {section.title}
              </h3>
              <div className="space-y-1.5">
                {section.shortcuts.map((shortcut) => (
                  <div key={shortcut.label} className="flex items-center justify-between gap-3">
                    <span className="text-[12px] text-[#999]">{shortcut.label}</span>
                    <div className="flex shrink-0 items-center gap-0.5">
                      {shortcut.keys.map((k, i) => (
                        <span key={i} className="flex items-center gap-0.5">
                          {i > 0 && <span className="text-[9px] text-[#555]">then</span>}
                          <Key>{k}</Key>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t border-[#222] px-5 py-2.5">
          <p className="text-center text-[10px] text-[#555]">
            Shortcuts are disabled when typing in input fields
          </p>
        </div>
      </div>
    </div>
  )
})
