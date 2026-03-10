interface LogoProps {
  size?: number
  className?: string
}

export default function Logo({ size = 24, className = '' }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      className={className}
      aria-label="Lite"
    >
      {/* Right-pointing chevron/arrow — reversed Kite logo */}
      {/* Top half — lighter green */}
      <polygon points="6,16 28,16 52,32 28,32 6,32" fill="#a3e635" />
      {/* Bottom half — darker green */}
      <polygon points="6,32 28,32 52,32 28,48 6,48" fill="#7cad2a" />
    </svg>
  )
}
