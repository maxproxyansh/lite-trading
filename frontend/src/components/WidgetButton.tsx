const isAndroid = typeof navigator !== 'undefined' && /android/i.test(navigator.userAgent)

function launchApp(path: string) {
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = path
  document.body.appendChild(iframe)
  setTimeout(() => iframe.remove(), 500)
}

export default function WidgetButton({ onSetupNeeded }: { onSetupNeeded: () => void }) {
  if (!isAndroid) return null

  const handleTap = () => {
    if (localStorage.getItem('pulse-connected') === 'true') {
      launchApp('litewidget://start')
    } else {
      onSetupNeeded()
    }
  }

  return (
    <button
      onClick={handleTap}
      className="md:hidden flex h-7 w-7 items-center justify-center rounded-full bg-bg-hover transition-colors hover:bg-bg-primary"
      title="Lite Pulse"
    >
      <svg
        viewBox="0 0 24 24"
        className="h-4 w-4"
        fill="none"
        stroke="#a3e635"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="2,12 6,12 9,4 12,20 15,8 18,12 22,12" />
      </svg>
    </button>
  )
}
