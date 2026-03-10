import type { ReactNode } from 'react'

import { SkeletonTable } from './Skeleton'

type Props = {
  loading: boolean
  empty: boolean
  emptyText: string
  children: ReactNode
  variant?: 'spinner' | 'skeleton'
}

export default function LoadingState({ loading, empty, emptyText, children, variant = 'spinner' }: Props) {
  if (loading) {
    if (variant === 'skeleton') {
      return <SkeletonTable />
    }
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-5 w-5 rounded-full border-2 border-signal border-t-transparent animate-spin" />
      </div>
    )
  }
  if (empty) {
    return <div className="py-12 text-center text-xs text-text-muted">{emptyText}</div>
  }
  return <>{children}</>
}
