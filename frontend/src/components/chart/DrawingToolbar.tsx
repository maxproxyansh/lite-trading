import { memo } from 'react'
import { Trash2 } from 'lucide-react'
import type { DrawingType } from '../../lib/chart/types'

interface Props {
  activeTool: DrawingType | null
  onSelectTool: (tool: DrawingType | null) => void
  onClearAll: () => void
  isCoarsePointer: boolean
}

const TOOLS: { type: DrawingType; label: string; icon: React.ReactNode }[] = [
  {
    type: 'hline', label: 'Horizontal Line (−)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <line x1="1" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="3" cy="8" r="1.5" fill="currentColor" opacity="0.4" />
        <circle cx="13" cy="8" r="1.5" fill="currentColor" opacity="0.4" />
      </svg>
    ),
  },
  {
    type: 'vline', label: 'Vertical Line (|)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <line x1="8" y1="1" x2="8" y2="15" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="8" cy="3" r="1.5" fill="currentColor" opacity="0.4" />
        <circle cx="8" cy="13" r="1.5" fill="currentColor" opacity="0.4" />
      </svg>
    ),
  },
  {
    type: 'trendline', label: 'Trend Line (T)',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <line x1="2" y1="13" x2="14" y2="3" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="2" cy="13" r="1.5" fill="currentColor" opacity="0.5" />
        <circle cx="14" cy="3" r="1.5" fill="currentColor" opacity="0.5" />
      </svg>
    ),
  },
  {
    type: 'channel', label: 'Parallel Channel',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <line x1="1" y1="11" x2="15" y2="5" stroke="currentColor" strokeWidth="1.2" />
        <line x1="1" y1="6" x2="15" y2="0" stroke="currentColor" strokeWidth="1.2" opacity="0.5" />
        <line x1="1" y1="6" x2="1" y2="11" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1.5" opacity="0.3" />
        <line x1="15" y1="0" x2="15" y2="5" stroke="currentColor" strokeWidth="0.8" strokeDasharray="1.5 1.5" opacity="0.3" />
      </svg>
    ),
  },
  {
    type: 'rectangle', label: 'Rectangle',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="4" width="12" height="8" stroke="currentColor" strokeWidth="1.2" fill="currentColor" fillOpacity="0.08" rx="0.5" />
        <circle cx="2" cy="4" r="1.2" fill="currentColor" opacity="0.5" />
        <circle cx="14" cy="12" r="1.2" fill="currentColor" opacity="0.5" />
      </svg>
    ),
  },
  {
    type: 'fib', label: 'Fibonacci Retracement',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <line x1="1" y1="2" x2="15" y2="2" stroke="currentColor" strokeWidth="1" />
        <line x1="1" y1="5.5" x2="15" y2="5.5" stroke="currentColor" strokeWidth="0.7" opacity="0.5" />
        <line x1="1" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="0.7" strokeDasharray="2 2" opacity="0.4" />
        <line x1="1" y1="10.5" x2="15" y2="10.5" stroke="currentColor" strokeWidth="0.7" opacity="0.5" />
        <line x1="1" y1="14" x2="15" y2="14" stroke="currentColor" strokeWidth="1" />
        <text x="12" y="4.5" fill="currentColor" fontSize="3" opacity="0.6">0.5</text>
      </svg>
    ),
  },
  {
    type: 'measure', label: 'Price Range / Measure',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="3" y="3" width="10" height="10" stroke="currentColor" strokeWidth="1" strokeDasharray="2 1.5" fill="currentColor" fillOpacity="0.06" rx="0.5" />
        <line x1="8" y1="5" x2="8" y2="11" stroke="currentColor" strokeWidth="1" opacity="0.6" />
        <line x1="6" y1="5" x2="10" y2="5" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
        <line x1="6" y1="11" x2="10" y2="11" stroke="currentColor" strokeWidth="0.8" opacity="0.6" />
      </svg>
    ),
  },
]

export const DrawingToolbar = memo(function DrawingToolbar({ activeTool, onSelectTool, onClearAll, isCoarsePointer }: Props) {
  const size = isCoarsePointer ? 'w-[44px] h-[44px]' : 'w-[28px] h-[28px]'
  return (
    <div className="absolute left-0 top-0 z-20 flex h-full w-[36px] flex-col items-center gap-0.5 border-r border-[#2a2a2a] bg-[#1e1e1e]/95 py-1.5 backdrop-blur-sm">
      {TOOLS.map((tool) => (
        <button key={tool.type} onClick={() => onSelectTool(activeTool === tool.type ? null : tool.type)}
          className={`flex ${size} items-center justify-center rounded transition-colors ${activeTool === tool.type ? 'border border-brand/30 bg-brand/15 text-brand' : 'text-[#888] hover:bg-[#2a2a2a] hover:text-[#ccc]'}`}
          title={tool.label}>
          {tool.icon}
        </button>
      ))}
      <div className="flex-1" />
      <button onClick={onClearAll} className={`flex ${size} items-center justify-center rounded text-[#555] transition-colors hover:bg-[#2a2a2a] hover:text-[#e53935]`} title="Delete all drawings">
        <Trash2 size={12} />
      </button>
    </div>
  )
})
