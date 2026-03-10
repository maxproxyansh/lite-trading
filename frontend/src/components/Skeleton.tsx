interface SkeletonProps {
  className?: string
}

export function SkeletonLine({ className = '' }: SkeletonProps) {
  return <div className={`skeleton h-4 rounded-sm ${className}`} />
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3 p-4">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          {Array.from({ length: cols }).map((_, j) => (
            <SkeletonLine key={j} className="flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCard({ className = '' }: SkeletonProps) {
  return <div className={`skeleton h-24 rounded-sm ${className}`} />
}
