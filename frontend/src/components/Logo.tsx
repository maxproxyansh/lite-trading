interface LogoProps {
  size?: number
  className?: string
  title?: string
}

export default function Logo({ size = 24, className = '', title = 'Lite' }: LogoProps) {
  return (
    <svg
      width={size * 1.5}
      height={size}
      viewBox="0 0 90 60"
      fill="none"
      className={className}
      aria-label={title}
      shapeRendering="geometricPrecision"
    >
      <title>{title}</title>
      <polygon points="60 0 90 30 60 60 30 30 0 0 60 0" fill="#A3E635" />
      <polygon points="60 60 30 30 0 60 60 60" fill="#86BF24" />
    </svg>
  )
}
