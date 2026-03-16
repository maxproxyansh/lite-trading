import { memo, useEffect, useRef } from 'react'
import { Trash2 } from 'lucide-react'
import type { DrawingStyle } from '../../lib/chart/types'

interface Props {
  x: number
  y: number
  style: DrawingStyle
  onChangeStyle: (updates: Partial<DrawingStyle>) => void
  onDelete: () => void
  onClose: () => void
}

const COLORS = ['#6366f1', '#f59e0b', '#4caf50', '#e53935', '#06b6d4', '#ec4899', '#8b5cf6', '#fff']
const WIDTHS: (1 | 2 | 3)[] = [1, 2, 3]

export const DrawingContextMenu = memo(function DrawingContextMenu({ x, y, style, onChangeStyle, onDelete, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  return (
    <div ref={ref} className="absolute z-40 w-[160px] rounded-lg border border-[#3a3a3a] bg-[#222] p-2 shadow-[0_8px_24px_rgba(0,0,0,0.5)]" style={{ left: x, top: y }}>
      <div className="mb-2 flex gap-1">
        {COLORS.map((c) => (
          <button key={c} onClick={() => onChangeStyle({ color: c })}
            className={`h-5 w-5 rounded-full border-2 transition-transform ${style.color === c ? 'scale-110 border-white' : 'border-transparent hover:scale-105'}`}
            style={{ backgroundColor: c }} />
        ))}
      </div>
      <div className="mb-2 flex items-center gap-1">
        {WIDTHS.map((w) => (
          <button key={w} onClick={() => onChangeStyle({ lineWidth: w })}
            className={`flex h-6 flex-1 items-center justify-center rounded text-[10px] transition-colors ${style.lineWidth === w ? 'bg-brand/20 text-brand' : 'bg-[#2a2a2a] text-[#888] hover:text-[#ccc]'}`}>
            {w}px
          </button>
        ))}
      </div>
      <div className="mb-2 flex items-center gap-1">
        {(['solid', 'dashed', 'dotted'] as const).map((s) => (
          <button key={s} onClick={() => onChangeStyle({ lineStyle: s })}
            className={`flex h-6 flex-1 items-center justify-center rounded text-[10px] transition-colors ${style.lineStyle === s ? 'bg-brand/20 text-brand' : 'bg-[#2a2a2a] text-[#888] hover:text-[#ccc]'}`}>
            {s}
          </button>
        ))}
      </div>
      <button onClick={onDelete}
        className="flex w-full items-center justify-center gap-1 rounded bg-[#2a2a2a] py-1 text-[10px] text-[#e53935] transition-colors hover:bg-[#e53935]/10">
        <Trash2 size={10} /> Delete
      </button>
    </div>
  )
})
