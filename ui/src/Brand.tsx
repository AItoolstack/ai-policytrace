/** ai·toolstack brand primitives shared by every PolicyTrace screen. */

export function Mark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 56 56" aria-hidden="true" focusable="false">
      <rect x="0.5" y="0.5" width="55" height="55" rx="12" fill="#1F2940" stroke="#2C3752" />
      <rect x="12" y="14" width="32" height="6" rx="2" fill="#E0A946" />
      <rect x="16" y="25" width="28" height="6" rx="2" fill="#ECEAE4" />
      <rect x="12" y="36" width="32" height="6" rx="2" fill="#56617A" />
    </svg>
  )
}

export function Lockup({ product = 'PolicyTrace' }: { product?: string }) {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <a
        href="https://www.ai-toolstack.com/"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-2.5 text-ink-100"
        aria-label="ai·toolstack home"
      >
        <Mark size={26} />
        <span className="text-[17px] font-semibold tracking-[-0.035em] hidden sm:inline">
          <span className="font-mono font-medium text-ink-300">ai·</span>toolstack
        </span>
      </a>
      <span className="text-ink-600 select-none hidden sm:inline" aria-hidden="true">/</span>
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-ink-100 truncate">{product}</span>
    </div>
  )
}

export function ExternalIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
    </svg>
  )
}

export function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v3a5 5 0 00-5 5H4z" />
    </svg>
  )
}

export const LINKS = {
  chapters: 'https://www.ai-toolstack.com/projects/policytrace/',
  github: 'https://github.com/AItoolstack/ai-policytrace',
}
