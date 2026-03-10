import { useEffect, useRef } from 'react'

import type { MarketSnapshot, OptionChainResponse, SignalResponse } from '../lib/api'
import { useStore } from '../store/useStore'

function buildWsUrl() {
  // Auth is handled via cookies (access_cookie) — never pass tokens in the URL.
  const explicit = import.meta.env.VITE_WS_BASE_URL as string | undefined
  if (explicit) {
    return explicit
  }
  const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (apiBase) {
    const wsBase = apiBase.replace(/^http/, 'ws')
    return `${wsBase}/api/v1/ws`
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/ws`
}

export function useWebSocket() {
  const reconnectRef = useRef<number | null>(null)
  const heartbeatRef = useRef<number | null>(null)
  const staleRef = useRef<number | null>(null)
  const attemptRef = useRef(0)
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
      const socket = new WebSocket(buildWsUrl())
      wsRef.current = socket

      const armStaleTimer = () => {
        if (staleRef.current) {
          window.clearTimeout(staleRef.current)
        }
        staleRef.current = window.setTimeout(() => {
          socket.close()
        }, 25000)
      }

      socket.onopen = () => {
        attemptRef.current = 0
        setWsStatus('connected')
        armStaleTimer()
        heartbeatRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping')
          }
        }, 10000)
      }

      socket.onmessage = (event) => {
        armStaleTimer()
        try {
          if (event.data === 'pong') {
            return
          }
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
        if (heartbeatRef.current) {
          window.clearInterval(heartbeatRef.current)
        }
        if (staleRef.current) {
          window.clearTimeout(staleRef.current)
        }
        attemptRef.current += 1
        const delay = Math.min(1000 * 2 ** Math.min(attemptRef.current, 4), 15000)
        reconnectRef.current = window.setTimeout(connect, delay)
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
      if (heartbeatRef.current) {
        window.clearInterval(heartbeatRef.current)
      }
      if (staleRef.current) {
        window.clearTimeout(staleRef.current)
      }
      wsRef.current?.close()
    }
  }, [accessToken, applyChainEvent, setSnapshot, setWsStatus, upsertSignal])
}
