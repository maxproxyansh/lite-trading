import type { ReactNode } from 'react'

type Props = {
  loading: boolean
  empty: boolean
  emptyText: string
  children: ReactNode
}

export default function LoadingState({ loading, empty, emptyText, children }: Props) {
  if (loading) {
    return <div className="px-4 py-12 text-center text-text-muted">Loading…</div>
  }
  if (empty) {
    return <div className="px-4 py-12 text-center text-text-muted">{emptyText}</div>
  }
  return <>{children}</>
}
