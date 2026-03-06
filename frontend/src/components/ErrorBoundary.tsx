import type { ReactNode } from 'react'
import { Component } from 'react'

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: unknown) {
    console.error('Unhandled UI error', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="m-4 rounded border border-loss/30 bg-loss/10 px-4 py-3 text-xs text-loss">
          Something went wrong. Please refresh the page.
        </div>
      )
    }
    return this.props.children
  }
}
