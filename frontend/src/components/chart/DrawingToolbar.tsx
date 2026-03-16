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
    type: 'hline', label: 'Horizontal Line',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="1" y1="7" x2="13" y2="7" stroke="currentColor" strokeWidth="1.5" /></svg>,
  },
  {
    type: 'vline', label: 'Vertical Line',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="7" y1="1" x2="7" y2="13" stroke="currentColor" strokeWidth="1.5" /></svg>,
  },
  {
    type: 'trendline', label: 'Trend Line',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="2" y1="12" x2="12" y2="2" stroke="currentColor" strokeWidth="1.5" /></svg>,
  },
  {
    type: 'channel', label: 'Channel',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="2" y1="10" x2="12" y2="4" stroke="currentColor" strokeWidth="1.5" /><line x1="2" y1="12" x2="12" y2="6" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2 2" /></svg>,
  },
  {
    type: 'rectangle', label: 'Rectangle',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="2" y="3" width="10" height="8" stroke="currentColor" strokeWidth="1.5" rx="1" /></svg>,
  },
  {
    type: 'fib', label: 'Fib Retracement',
    icon: <span style={{ fontSize: 10, fontWeight: 700 }}>Fib</span>,
  },
  {
    type: 'measure', label: 'Measure',
    icon: <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="3" y1="3" x2="3" y2="11" stroke="currentColor" strokeWidth="1.5" /><line x1="11" y1="3" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" /><line x1="3" y1="7" x2="11" y2="7" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" /></svg>,
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
