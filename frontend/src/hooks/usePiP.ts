// frontend/src/hooks/usePiP.ts
// Uses Video PiP with canvas rendering — works on Android Chrome natively.
// Renders pill content to an offscreen div, paints it onto a canvas,
// captures as a video stream, and enters PiP via video.requestPictureInPicture().
import { useState, useCallback, useEffect, useRef } from 'react'

export const isPiPSupported = typeof document !== 'undefined' && document.pictureInPictureEnabled === true

interface UsePiPReturn {
  isOpen: boolean
  containerRef: React.RefObject<HTMLDivElement | null>
  open: () => Promise<void>
  close: () => void
}

const PILL_WIDTH = 320
const PILL_HEIGHT = 80
const FPS = 2

export function usePiP(): UsePiPReturn {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPainting = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const close = useCallback(() => {
    stopPainting()
    if (document.pictureInPictureElement) {
      document.exitPictureInPicture().catch(() => {})
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
      videoRef.current.remove()
      videoRef.current = null
    }
    if (canvasRef.current) {
      canvasRef.current.remove()
      canvasRef.current = null
    }
    setIsOpen(false)
  }, [stopPainting])

  const paintFrame = useCallback(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear
    ctx.clearRect(0, 0, PILL_WIDTH, PILL_HEIGHT)

    // Background
    ctx.fillStyle = '#1a1a2e'
    ctx.beginPath()
    ctx.roundRect(0, 0, PILL_WIDTH, PILL_HEIGHT, 20)
    ctx.fill()

    // Read data from the offscreen rendered div
    const label = container.querySelector('.pip-label')?.textContent ?? 'NIFTY'
    const price = container.querySelector('.pip-price')?.textContent ?? '--'
    const changeEl = container.querySelector('.pip-change')
    const changeText = changeEl?.textContent ?? ''
    const isPositive = changeEl?.classList.contains('positive') ?? true
    const isStale = container.querySelector('.pip-pill')?.classList.contains('stale') ?? false

    const pnlValueEl = container.querySelector('.pip-pnl-value')
    const pnlLabel = container.querySelector('.pip-pnl-label')?.textContent ?? ''
    const pnlValue = pnlValueEl?.textContent ?? ''
    const pnlPositive = pnlValueEl?.classList.contains('positive') ?? true

    // Border
    const borderColor = isPositive ? '#22c55e' : '#ef4444'
    ctx.strokeStyle = borderColor
    ctx.lineWidth = 4
    ctx.beginPath()
    ctx.roundRect(2, 2, PILL_WIDTH - 4, PILL_HEIGHT - 4, 18)
    ctx.stroke()

    // Stale overlay
    if (isStale) {
      ctx.globalAlpha = 0.5
    }

    const hasPnL = pnlLabel && pnlValue
    const mainY = hasPnL ? 30 : 46

    // Label
    ctx.font = '600 13px -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
    ctx.fillStyle = '#94a3b8'
    ctx.textBaseline = 'middle'
    ctx.fillText(label, 16, mainY)

    // Price
    const labelWidth = ctx.measureText(label).width
    ctx.font = '700 18px -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
    ctx.fillStyle = '#ffffff'
    ctx.fillText(price, 16 + labelWidth + 8, mainY)

    // Change %
    if (changeText) {
      const priceWidth = ctx.measureText(price).width
      ctx.font = '600 13px -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
      ctx.fillStyle = isPositive ? '#22c55e' : '#ef4444'
      ctx.fillText(changeText, 16 + labelWidth + 8 + priceWidth + 8, mainY)
    }

    // P&L row
    if (hasPnL) {
      ctx.font = '500 12px -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
      ctx.fillStyle = '#94a3b8'
      ctx.fillText(pnlLabel, 16, 54)
      const pnlLabelWidth = ctx.measureText(pnlLabel).width
      ctx.font = '600 14px -apple-system, BlinkMacSystemFont, system-ui, sans-serif'
      ctx.fillStyle = pnlPositive ? '#22c55e' : '#ef4444'
      ctx.fillText(pnlValue, 16 + pnlLabelWidth + 6, 54)
    }

    ctx.globalAlpha = 1
  }, [])

  const open = useCallback(async () => {
    if (!isPiPSupported) return

    // Create offscreen canvas
    const canvas = document.createElement('canvas')
    canvas.width = PILL_WIDTH
    canvas.height = PILL_HEIGHT
    canvas.style.position = 'fixed'
    canvas.style.top = '-9999px'
    canvas.style.left = '-9999px'
    document.body.appendChild(canvas)
    canvasRef.current = canvas

    // Create video from canvas stream
    const stream = canvas.captureStream(FPS)
    const video = document.createElement('video')
    video.srcObject = stream
    video.muted = true
    video.playsInline = true
    video.style.position = 'fixed'
    video.style.top = '-9999px'
    video.style.left = '-9999px'
    video.width = PILL_WIDTH
    video.height = PILL_HEIGHT
    document.body.appendChild(video)
    videoRef.current = video

    await video.play()

    // Start painting frames
    paintFrame()
    intervalRef.current = setInterval(paintFrame, 1000 / FPS)

    // Enter PiP
    await video.requestPictureInPicture()

    video.addEventListener('leavepictureinpicture', () => {
      close()
    }, { once: true })

    setIsOpen(true)
  }, [paintFrame, close])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPainting()
      if (document.pictureInPictureElement) {
        document.exitPictureInPicture().catch(() => {})
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null
        videoRef.current.remove()
      }
      if (canvasRef.current) {
        canvasRef.current.remove()
      }
    }
  }, [stopPainting])

  return { isOpen, containerRef, open, close }
}
