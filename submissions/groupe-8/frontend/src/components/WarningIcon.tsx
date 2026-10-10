/** The only icon in the header: shown when a value is abnormal (never colour alone). */
export function WarningIcon({ tone }: { tone: 'critical' | 'waiting' }) {
  return (
    <svg className="warn-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke={`var(--${tone})`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" role="img" aria-label="Alerte">
      <path d="M12 3.5 2.5 20h19L12 3.5Z" />
      <path d="M12 10v4.5M12 17.2v.1" />
    </svg>
  );
}
