import { useEffect, useRef } from 'react'

import type { MarketSnapshot, OptionChainResponse, SignalResponse } from '../lib/api'
import { useStore } from '../store/useStore'

function buildWsUrl(token: string) {
  const explicit = import.meta.env.VITE_WS_BASE_URL as string | undefined
  if (explicit) {
    const separator = explicit.includes('?') ? '&' : '?'
    return `${explicit}${separator}token=${encodeURIComponent(token)}`
  }
  const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (apiBase) {
    const wsBase = apiBase.replace(/^http/, 'ws')
    return `${wsBase}/api/v1/ws?token=${encodeURIComponent(token)}`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`
}

export function useWebSocket() {
  const reconnectRef = useRef<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const {
    setWsStatus,
    setSnapshot,
    applyChainEvent,
    upsertSignal,
  } = useStore()
  const accessToken = useStore((state) => state.accessToken)

  useEffect(() => {
    if (!accessToken) {
      setWsStatus('disconnected')
      wsRef.current?.close()
      return undefined
    }

    const connect = () => {
      setWsStatus('connecting')
      const socket = new WebSocket(buildWsUrl(accessToken))
      wsRef.current = socket

      socket.onopen = () => {
        setWsStatus('connected')
        socket.send('hello')
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as { type: string; payload: unknown }
          if (message.type === 'market.snapshot') {
            setSnapshot(message.payload as MarketSnapshot)
          }
          if (message.type === 'option.chain') {
            applyChainEvent(message.payload as OptionChainResponse)
          }
          if (message.type === 'signal.updated') {
            upsertSignal(message.payload as SignalResponse)
          }
        } catch {
          // Ignore malformed push payloads.
        }
      }

      socket.onclose = () => {
        setWsStatus('disconnected')
        reconnectRef.current = window.setTimeout(connect, 4000)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      if (reconnectRef.current) {
        window.clearTimeout(reconnectRef.current)
      }
      wsRef.current?.close()
    }
  }, [accessToken, applyChainEvent, setSnapshot, setWsStatus, upsertSignal])
}
