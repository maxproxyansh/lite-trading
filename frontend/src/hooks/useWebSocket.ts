import { useEffect, useRef } from 'react'

import type {
  MarketSnapshot,
  OptionChainResponse,
  PortfolioRefreshEvent,
  QuoteBatchEvent,
  SignalResponse,
} from '../lib/api'
import { getRuntimeConfig } from '../lib/runtime-config'
import { useStore } from '../store/useStore'

export function useWebSocket() {
  const reconnectRef = useRef<number | null>(null)
  const heartbeatRef = useRef<number | null>(null)
  const staleRef = useRef<number | null>(null)
  const attemptRef = useRef(0)
  const shouldReconnectRef = useRef(false)
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef({
    setSnapshot: useStore.getState().setSnapshot,
    applyChainEvent: useStore.getState().applyChainEvent,
    applyQuoteBatch: useStore.getState().applyQuoteBatch,
    upsertSignal: useStore.getState().upsertSignal,
    requestPortfolioRefresh: useStore.getState().requestPortfolioRefresh,
  })

  const accessToken = useStore((state) => state.accessToken)
  const setWsStatus = useStore((state) => state.setWsStatus)
  const setSnapshot = useStore((state) => state.setSnapshot)
  const applyChainEvent = useStore((state) => state.applyChainEvent)
  const applyQuoteBatch = useStore((state) => state.applyQuoteBatch)
  const upsertSignal = useStore((state) => state.upsertSignal)
  const requestPortfolioRefresh = useStore((state) => state.requestPortfolioRefresh)

  useEffect(() => {
    handlersRef.current = {
      setSnapshot,
      applyChainEvent,
      applyQuoteBatch,
      upsertSignal,
      requestPortfolioRefresh,
    }
  }, [applyChainEvent, applyQuoteBatch, requestPortfolioRefresh, setSnapshot, upsertSignal])

  useEffect(() => {
    const clearTimers = () => {
      if (reconnectRef.current !== null) {
        window.clearTimeout(reconnectRef.current)
        reconnectRef.current = null
      }
      if (heartbeatRef.current !== null) {
        window.clearInterval(heartbeatRef.current)
        heartbeatRef.current = null
      }
      if (staleRef.current !== null) {
        window.clearTimeout(staleRef.current)
        staleRef.current = null
      }
    }

    if (!accessToken) {
      shouldReconnectRef.current = false
      attemptRef.current = 0
      clearTimers()
      setWsStatus('disconnected')
      if (wsRef.current) {
        const socket = wsRef.current
        wsRef.current = null
        socket.close()
      }
      return undefined
    }

    shouldReconnectRef.current = true
    let disposed = false

    const handleMessage = (raw: string) => {
      try {
        if (raw === 'pong') {
          return
        }
        const message = JSON.parse(raw) as { type: string; payload: unknown }
        if (message.type === 'market.snapshot') {
          handlersRef.current.setSnapshot(message.payload as MarketSnapshot)
        }
        if (message.type === 'option.chain') {
          handlersRef.current.applyChainEvent(message.payload as OptionChainResponse)
        }
        if (message.type === 'option.quotes') {
          handlersRef.current.applyQuoteBatch(message.payload as QuoteBatchEvent)
        }
        if (message.type === 'signal.updated') {
          handlersRef.current.upsertSignal(message.payload as SignalResponse)
        }
        if (message.type === 'portfolio.refresh') {
          const payload = message.payload as PortfolioRefreshEvent
          handlersRef.current.requestPortfolioRefresh(payload.portfolio_id)
        }
      } catch {
        // Ignore malformed push payloads.
      }
    }

    const connect = () => {
      if (disposed || !shouldReconnectRef.current) {
        return
      }
      setWsStatus('connecting')
      void getRuntimeConfig()
        .then(({ wsUrl }) => {
          if (disposed || !shouldReconnectRef.current) {
            return
          }

          const socket = new WebSocket(wsUrl)
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
            if (disposed || !shouldReconnectRef.current) {
              socket.close()
              return
            }
            attemptRef.current = 0
            setWsStatus('connected')
            armStaleTimer()
            if (heartbeatRef.current !== null) {
              window.clearInterval(heartbeatRef.current)
            }
            heartbeatRef.current = window.setInterval(() => {
              if (socket.readyState === WebSocket.OPEN) {
                socket.send('ping')
              }
            }, 10000)
          }

          socket.onmessage = (event) => {
            armStaleTimer()
            handleMessage(String(event.data))
          }

          socket.onclose = () => {
            if (wsRef.current === socket) {
              wsRef.current = null
            }
            setWsStatus('disconnected')
            clearTimers()
            if (disposed || !shouldReconnectRef.current) {
              return
            }
            attemptRef.current += 1
            const delay = Math.min(1000 * 2 ** Math.min(attemptRef.current, 4), 15000)
            reconnectRef.current = window.setTimeout(connect, delay)
          }

          socket.onerror = () => {
            if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) {
              socket.close()
            }
          }
        })
        .catch(() => {
          setWsStatus('disconnected')
          attemptRef.current += 1
          const delay = Math.min(1000 * 2 ** Math.min(attemptRef.current, 4), 15000)
          reconnectRef.current = window.setTimeout(connect, delay)
        })
    }

    connect()

    return () => {
      disposed = true
      shouldReconnectRef.current = false
      clearTimers()
      if (wsRef.current) {
        const socket = wsRef.current
        wsRef.current = null
        socket.close()
      }
    }
  }, [accessToken, setWsStatus])
}
