/** Compass logomark: a stylised needle in a ring. Original artwork for the prototype. */
export function CompassMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" aria-hidden className={className}>
      <circle cx="16" cy="16" r="12.5" stroke="currentColor" strokeWidth="2.2" opacity="0.9" />
      <path d="M16 6.5 19.4 16 16 25.5 12.6 16Z" fill="currentColor" opacity="0.35" />
      <path d="M16 6.5 19.4 16h-6.8Z" fill="currentColor" />
      <circle cx="16" cy="16" r="1.9" fill="currentColor" />
    </svg>
  )
}
